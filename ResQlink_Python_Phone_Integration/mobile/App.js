import React, { useEffect, useRef, useState } from 'react';
import * as Location from 'expo-location';
import * as ImagePicker from 'expo-image-picker';
import { WebView } from 'react-native-webview';
import {
  ActivityIndicator,
  Alert,
  Image,
  Linking,
  KeyboardAvoidingView,
  Modal,
  Platform,
  ScrollView,
  Share,
  StatusBar,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  Vibration,
  View,
} from 'react-native';

const API_BASE = 'http://10.245.206.88:8001';
const OVERPASS_URL = 'https://overpass-api.de/api/interpreter';
const PHOTON_URL = 'https://photon.komoot.io/api/';
const OSRM_URL = 'https://router.project-osrm.org';
const DEFAULT_LAT = 14.41;
const DEFAULT_LNG = 120.945;
const emergencyHotlines = [
  { agency: 'National Emergency Hotline', label: '911', number: '911' },
  { agency: 'NDRRMC Operations Center', label: '(02) 8911-5061 to 65, local 100', number: '0289115061' },
  { agency: 'NDRRMC Operations Center', label: '(02) 8911-1406', number: '0289111406' },
  { agency: 'NDRRMC Operations Center', label: '(02) 8912-2665', number: '0289122665' },
  { agency: 'NDRRMC Operations Center', label: '(02) 8912-5668', number: '0289125668' },
  { agency: 'Philippine National Police', label: '117', number: '117' },
  { agency: 'Philippine National Police', label: '(02) 8722-0650', number: '0287220650' },
  { agency: 'Bureau of Fire Protection', label: '(02) 8426-0219', number: '0284260219' },
  { agency: 'Bureau of Fire Protection', label: '(02) 8426-0246', number: '0284260246' },
  { agency: 'Philippine Red Cross', label: '143', number: '143' },
  { agency: 'Philippine Coast Guard', label: '(02) 8527-8481', number: '0285278481' },
  { agency: 'MMDA Metrobase', label: '136', number: '136' },
  { agency: 'PAGASA Weather Info', label: '(02) 8284-0800', number: '0282840800' },
];

const quickPrompts = [
  'How to respond during a fire?',
  'Nearest evacuation center?',
  'Call 911?',
  'My location status',
];

async function fetchJson(url, options = {}, timeoutMs = 8000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, { ...options, signal: controller.signal });
    if (!response.ok) {
      throw new Error(`Server responded with ${response.status}`);
    }
    return await response.json();
  } finally {
    clearTimeout(timer);
  }
}

async function fetchPublicEmergencyPlaces(lat = DEFAULT_LAT, lng = DEFAULT_LNG, radius = 8000) {
  const query = `
    [out:json][timeout:25];
    (
      node["amenity"~"^(shelter|community_centre|school)$"](around:${radius},${lat},${lng});
      way["amenity"~"^(shelter|community_centre|school)$"](around:${radius},${lat},${lng});
      node["emergency"="assembly_point"](around:${radius},${lat},${lng});
      way["emergency"="assembly_point"](around:${radius},${lat},${lng});
    );
    out center tags;
  `;

  const response = await fetch(OVERPASS_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8' },
    body: `data=${encodeURIComponent(query)}`,
  });

  if (!response.ok) {
    throw new Error(`Overpass API responded with ${response.status}`);
  }

  const data = await response.json();

  return (data.elements || [])
    .filter((element) => element.tags && (element.tags.name || element.tags.amenity))
    .map((element, index) => {
      const name = element.tags.name || element.tags.amenity || 'Evacuation point';
      const latValue = Number(element.lat ?? element.center?.lat);
      const lngValue = Number(element.lon ?? element.center?.lon);

      return {
        id: element.id || `${name}-${index}`,
        type: element.tags.emergency === 'assembly_point' ? 'Assembly point' : (element.tags.amenity || 'Evacuation point'),
        description: name,
        status: 'OpenStreetMap destination',
        lat: latValue,
        lng: lngValue,
      };
    })
    .filter((place) => Number.isFinite(place.lat) && Number.isFinite(place.lng))
    .slice(0, 10);
}

async function fetchNearbyServices(service, lat, lng) {
  const isHospital = service === 'hospital';
  const radiusKm = 8;
  const latitudeDelta = radiusKm / 111;
  const longitudeDelta = radiusKm / (111 * Math.cos((lat * Math.PI) / 180));
  const params = new URLSearchParams({
    q: isHospital ? 'hospital' : 'police station',
    lat: String(lat),
    lon: String(lng),
    bbox: `${lng - longitudeDelta},${lat - latitudeDelta},${lng + longitudeDelta},${lat + latitudeDelta}`,
    limit: '50',
    location_bias_scale: '0.1',
  });
  const tags = isHospital
    ? ['amenity:hospital', 'amenity:clinic', 'amenity:doctors', 'amenity:health_centre', 'healthcare:hospital', 'healthcare:clinic']
    : ['amenity:police', 'office:police'];
  tags.forEach((tag) => params.append('osm_tag', tag));

  try {
    const response = await fetch(`${PHOTON_URL}?${params.toString()}`);
    if (!response.ok) {
      throw new Error(`Nearby search returned ${response.status}`);
    }
    const data = await response.json();
    const places = (data.features || []).map((feature) => {
      const [longitude, latitude] = feature.geometry?.coordinates || [];
      const props = feature.properties || {};
      return {
        id: props.osm_id || `${props.name}-${latitude}-${longitude}`,
        name: props.name || (isHospital ? 'Nearby medical facility' : 'Nearby police station'),
        latitude: Number(latitude),
        longitude: Number(longitude),
        distance: distanceKm(lat, lng, Number(latitude), Number(longitude)),
      };
    }).filter((place) => Number.isFinite(place.latitude)
      && Number.isFinite(place.longitude)
      && place.distance <= radiusKm);

    if (places.length > 0) {
      return Array.from(new Map(places.map((place) => [String(place.id), place])).values())
        .sort((first, second) => first.distance - second.distance)
        .slice(0, 12);
    }
  } catch {
    // Retry with Overpass when Photon is unavailable.
  }

  const query = isHospital
    ? `[out:json][timeout:18];(nwr["amenity"~"^(hospital|clinic|doctors|health_centre)$"](around:8000,${lat},${lng});nwr["healthcare"~"^(hospital|clinic|doctor|centre)$"](around:8000,${lat},${lng}););out center tags 80;`
    : `[out:json][timeout:18];(nwr["amenity"="police"](around:8000,${lat},${lng});nwr["office"="police"](around:8000,${lat},${lng}););out center tags 80;`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 20000);

  try {
    const response = await fetch(OVERPASS_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8' },
      body: `data=${encodeURIComponent(query)}`,
      signal: controller.signal,
    });
    if (!response.ok) {
      throw new Error(`Map search returned ${response.status}`);
    }
    const data = await response.json();
    return (data.elements || []).map((element) => ({
      id: element.id,
      name: element.tags?.name || (isHospital ? 'Nearby medical facility' : 'Nearby police station'),
      latitude: Number(element.lat ?? element.center?.lat),
      longitude: Number(element.lon ?? element.center?.lon),
    })).filter((place) => Number.isFinite(place.latitude) && Number.isFinite(place.longitude))
      .map((place) => ({ ...place, distance: distanceKm(lat, lng, place.latitude, place.longitude) }))
      .filter((place) => place.distance <= radiusKm)
      .sort((first, second) => first.distance - second.distance)
      .slice(0, 12);
  } finally {
    clearTimeout(timer);
  }
}

function distanceKm(lat1, lng1, lat2, lng2) {
  const toRadians = (degrees) => (degrees * Math.PI) / 180;
  const deltaLat = toRadians(lat2 - lat1);
  const deltaLng = toRadians(lng2 - lng1);
  const value = Math.sin(deltaLat / 2) ** 2
    + Math.cos(toRadians(lat1)) * Math.cos(toRadians(lat2)) * Math.sin(deltaLng / 2) ** 2;
  return 6371 * 2 * Math.atan2(Math.sqrt(value), Math.sqrt(1 - value));
}

function openExternalFacilitySearch(service, coords) {
  const label = service === 'hospital' ? 'hospital' : 'police station';
  const query = `${label} near ${coords.latitude},${coords.longitude}`;
  return Linking.openURL(`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`);
}

function localAgencyPlace(agency) {
  return {
    id: `agency-${agency.id}`,
    name: agency.name,
    description: agency.name,
    type: agency.type,
    kind: agency.type === 'hospital' ? 'Hospital' : agency.type,
    status: 'Database directory',
    address: agency.address,
    hotline: agency.hotline,
    lat: Number(agency.lat),
    lng: Number(agency.lng),
    latitude: Number(agency.lat),
    longitude: Number(agency.lng),
    distance: Number(agency.distance_km || 0),
  };
}

async function fetchLocalAgencies(service, lat, lng) {
  try {
    const query = new URLSearchParams({ type: service, lat: String(lat), lng: String(lng) });
    const data = await fetchJson(`${API_BASE}/api/agencies?${query.toString()}`);
    return (data.items || []).map(localAgencyPlace);
  } catch {
    return [];
  }
}

async function findFastestRoadRoute(origin, destinations) {
  const candidates = destinations.slice(0, 10);
  const coordinates = [
    `${origin.longitude},${origin.latitude}`,
    ...candidates.map((place) => `${place.lng},${place.lat}`),
  ].join(';');
  const destinationIndexes = candidates.map((_, index) => index + 1).join(';');
  const table = await fetchJson(
    `${OSRM_URL}/table/v1/driving/${coordinates}?sources=0&destinations=${destinationIndexes}&annotations=duration,distance`,
    {},
    20000,
  );

  if (table.code !== 'Ok' || !table.durations?.[0]) {
    throw new Error('No road travel times are available for these destinations.');
  }

  const ranked = candidates.map((place, index) => ({
    place,
    duration: table.durations[0][index],
    distance: table.distances?.[0]?.[index],
  })).filter((route) => Number.isFinite(route.duration))
    .sort((first, second) => first.duration - second.duration);

  if (ranked.length === 0) {
    throw new Error('No drivable route was found to the nearby destinations.');
  }

  const fastest = ranked[0];
  const route = await fetchJson(
    `${OSRM_URL}/route/v1/driving/${origin.longitude},${origin.latitude};${fastest.place.lng},${fastest.place.lat}?overview=full&geometries=geojson&steps=false`,
    {},
    20000,
  );
  const bestRoute = route.routes?.[0];
  if (route.code !== 'Ok' || !bestRoute?.geometry?.coordinates?.length) {
    throw new Error('Could not load the selected road route.');
  }

  return {
    ...fastest,
    geometry: bestRoute.geometry.coordinates,
    duration: bestRoute.duration,
    distance: bestRoute.distance,
  };
}

function buildMapHtml(location, centers, routeTarget, routeGeometry) {
  const latitude = location?.latitude ?? DEFAULT_LAT;
  const longitude = location?.longitude ?? DEFAULT_LNG;
  const places = centers.map((center) => ({
    id: String(center.id),
    name: center.description || center.type || 'Evacuation point',
    kind: center.kind || 'Evacuation point',
    lat: Number(center.lat),
    lng: Number(center.lng),
  })).filter((center) => Number.isFinite(center.lat) && Number.isFinite(center.lng));
  const placesJson = JSON.stringify(places).replace(/</g, '\\u003c');
  const routeJson = JSON.stringify((routeGeometry || []).map(([lng, lat]) => [lat, lng])).replace(/</g, '\\u003c');
  const targetJson = JSON.stringify(routeTarget ? {
    lat: Number(routeTarget.lat),
    lng: Number(routeTarget.lng),
    name: routeTarget.description || routeTarget.type || 'Destination',
  } : null).replace(/</g, '\\u003c');

  return `<!doctype html>
<html><head><meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>html,body,#map{height:100%;width:100%;margin:0;background:#e2e8f0} .leaflet-control-attribution{font-size:9px}</style>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script></head>
<body><div id="map"></div><script>
const user=[${latitude},${longitude}];
const places=${placesJson};
const route=${routeJson};
const target=${targetJson};
const map=L.map('map',{zoomControl:true}).setView(user,14);
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; OpenStreetMap contributors'}).addTo(map);
const bounds=[user];
L.circleMarker(user,{radius:9,color:'#fff',weight:3,fillColor:'#ef4444',fillOpacity:1}).addTo(map).bindPopup('You are here');
places.forEach((place,index)=>{
  const color=place.kind==='Hospital'?'#2563eb':'#15803d';
  const marker=L.circleMarker([place.lat,place.lng],{radius:8,color:color,weight:2,fillColor:color,fillOpacity:0.9}).addTo(map);
  const popup=document.createElement('span'); popup.textContent=place.kind+': '+place.name; marker.bindPopup(popup);
  marker.on('click',()=>window.ReactNativeWebView.postMessage(String(index)));
  bounds.push([place.lat,place.lng]);
});
if(target && Number.isFinite(target.lat) && Number.isFinite(target.lng)){
  L.marker([target.lat,target.lng]).addTo(map).bindPopup(target.name).openPopup();
  bounds.push([target.lat,target.lng]);
}
if(route.length>1){
  const routeLine=L.polyline(route,{color:'#16a34a',weight:5,opacity:0.9}).addTo(map);
  map.fitBounds(routeLine.getBounds(),{padding:[32,32],maxZoom:16});
}
else if(target && Number.isFinite(target.lat) && Number.isFinite(target.lng)){
  map.setView([target.lat,target.lng],17);
}
else if(bounds.length>1) map.fitBounds(bounds,{padding:[28,28],maxZoom:15});
</script></body></html>`;
}

function buildBotReply(message) {
  const q = (message || '').toLowerCase();

  if (q.includes('fire') || q.includes('smoke') || q.includes('burn')) {
    return '🔥 Fire Safety Guidance:\n1. Stay low to the ground to avoid inhaling dense smoke.\n2. Feel doors with the back of your hand before opening.\n3. Never use elevators during a fire evacuation.\n4. If trapped, seal doors with a wet cloth and signal at a window.';
  }

  if (q.includes('evacuat') || q.includes('center') || q.includes('route') || q.includes('safe')) {
    return '🧭 Evacuation Tip:\nSwitch to Rescue Me and press Find Safe Route. I will calculate the safer route away from hazards.';
  }

  if (q.includes('location') || q.includes('gps') || q.includes('where am i')) {
    return '📍 Location Status:\nYour GPS is active and live-tracking. Share your location from the emergency menu to update responders.';
  }

  if (q.includes('911') || q.includes('call') || q.includes('hotline') || q.includes('number')) {
    return '🚨 Emergency Numbers:\n• National emergency: 911\n• BFP: (02) 8426-0219\n• Tap Emergency Call in the app to dial immediately.';
  }

  if (q.includes('first aid') || q.includes('injury') || q.includes('bleed') || q.includes('hurt')) {
    return '🩹 First Aid Basics:\n• Burns: cool under running water for 10–20 minutes.\n• Bleeding: apply direct pressure with a clean cloth.\n• Breathing issues: keep the person seated upright and clear smoke.';
  }

  if (q.includes('hello') || q.includes('hi') || q.includes('hey') || q.includes('help')) {
    return 'Hello! I am your AI Emergency Assistant. I can help with fire safety, evacuation info, first aid, and emergency contacts. How can I help?';
  }

  return '🤖 I am standing by to assist. Ask me about fire safety, evacuation centers, first aid, or emergency contacts.';
}

export default function App() {
  const [authMode, setAuthMode] = useState('login');
  const [currentUser, setCurrentUser] = useState(null);
  const [hazards, setHazards] = useState([]);
  const [reports, setReports] = useState([]);
  const [reportsLoading, setReportsLoading] = useState(false);
  const [reportsError, setReportsError] = useState('');
  const [systemLogs, setSystemLogs] = useState([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [logsError, setLogsError] = useState('');
  const [databaseSection, setDatabaseSection] = useState('reports');
  const [evacuationCenters, setEvacuationCenters] = useState([]);
  const [hospitalCenters, setHospitalCenters] = useState([]);
  const [location, setLocation] = useState(null);
  const [locationStatus, setLocationStatus] = useState('Location not available');
  const [selectedCenter, setSelectedCenter] = useState(null);
  const [routeTarget, setRouteTarget] = useState(null);
  const [routeGeometry, setRouteGeometry] = useState([]);
  const [routeInfo, setRouteInfo] = useState(null);
  const [routeLoading, setRouteLoading] = useState(false);
  const [sosActive, setSosActive] = useState(false);
  const [alarmActive, setAlarmActive] = useState(false);
  const [mapHtml, setMapHtml] = useState(() => buildMapHtml(null, [], null));
  const [reportPhoto, setReportPhoto] = useState(null);
  const sosSubscription = useRef(null);
  const alarmTimeout = useRef(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [type, setType] = useState('Flooding');
  const [description, setDescription] = useState('Street is flooding near the main highway and vehicles are struggling to pass.');
  const [status, setStatus] = useState('Connecting to backend...');
  const [activeTab, setActiveTab] = useState('home');
  const [chatOpen, setChatOpen] = useState(false);
  const [reportOpen, setReportOpen] = useState(false);
  const [hotlineOpen, setHotlineOpen] = useState(false);
  const [localHotlines, setLocalHotlines] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [chatThinking, setChatThinking] = useState(false);
  const [chatMessages, setChatMessages] = useState([
    { id: 1, from: 'bot', text: 'Hello! I am your AI Emergency Assistant. How can I assist you right now?' },
  ]);
  const [announcements, setAnnouncements] = useState([]);
  const [announcementsLoading, setAnnouncementsLoading] = useState(false);
  const [announcementsError, setAnnouncementsError] = useState('');
  const [profile, setProfile] = useState({
    full_name: 'Guest User',
    phone_number: '09000000000',
    home_address: 'Bacoor, Cavite',
  });
  const [emergencyContacts, setEmergencyContacts] = useState([]);
  const [newContactName, setNewContactName] = useState('');
  const [newContactPhone, setNewContactPhone] = useState('');
  const [newContactRelationship, setNewContactRelationship] = useState('');

  const loadHazards = async (coords = location) => {
    const lat = coords?.latitude ?? DEFAULT_LAT;
    const lng = coords?.longitude ?? DEFAULT_LNG;
    let backendAvailable = false;
    let databaseShelters = [];
    setLoading(true);

    try {
      const health = await fetchJson(`${API_BASE}/api/health`);
      if (!health || health.ok !== true) {
        throw new Error('Backend health check failed');
      }
      const [data, shelters] = await Promise.all([
        fetchJson(`${API_BASE}/api/hazards`),
        fetchJson(`${API_BASE}/api/shelters?lat=${lat}&lng=${lng}`).catch(() => ({ items: [] })),
      ]);
      setHazards(data.items || []);
      databaseShelters = shelters.items || [];
      backendAvailable = true;
      setStatus('Connected');
    } catch {
      setStatus('Backend offline; showing public evacuation points');
    }

    if (databaseShelters.length > 0) {
      setEvacuationCenters(databaseShelters);
      setLoading(false);
      return databaseShelters;
    }

    try {
      const places = await fetchPublicEmergencyPlaces(lat, lng);
      setEvacuationCenters(places);
      if (!backendAvailable) {
        setHazards(places);
      }
      if (places.length === 0) {
        setStatus('No mapped evacuation points found nearby');
      }
      return places;
    } catch {
      setEvacuationCenters([]);
      setStatus('Map data unavailable. Check your internet connection.');
      return [];
    } finally {
      setLoading(false);
    }
  };

  const loadReports = async () => {
    setReportsLoading(true);
    setReportsError('');
    try {
      const data = await fetchJson(`${API_BASE}/api/hazards`);
      setReports(data.items || []);
    } catch {
      setReportsError('Could not load database records. Check that the backend is running and try again.');
    } finally {
      setReportsLoading(false);
    }
  };

  const loadSystemLogs = async () => {
    setLogsLoading(true);
    setLogsError('');
    try {
      const data = await fetchJson(`${API_BASE}/api/logs?limit=100`);
      setSystemLogs(data.items || []);
    } catch {
      setLogsError('Could not load system logs. Check that the backend is running and try again.');
    } finally {
      setLogsLoading(false);
    }
  };

  const openDatabase = () => {
    setActiveTab('database');
    setDatabaseSection('reports');
    loadReports();
    loadSystemLogs();
  };

  const locateMe = async () => {
    try {
      setLocationStatus('Requesting location permission…');
      const permission = await Location.requestForegroundPermissionsAsync();
      if (permission.status !== 'granted') {
        setLocationStatus('Location permission denied');
        Alert.alert('Location permission needed', 'Allow location access in your phone settings to show your position on the map.');
        return null;
      }

      const position = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
      const coords = position.coords;
      setLocation(coords);
      setLocationStatus('GPS location found');
      await loadHazards(coords);
      return coords;
    } catch {
      setLocationStatus('Could not get GPS location');
      Alert.alert('Location unavailable', 'Turn on your phone location services and try again.');
      return null;
    }
  };

  const shareLocation = async () => {
    const coords = location || await locateMe();
    if (!coords) return;

    const mapUrl = `https://maps.google.com/?q=${coords.latitude},${coords.longitude}`;
    try {
      await Share.share({
        title: 'My emergency location',
        message: `My current location: ${mapUrl}`,
      });
    } catch {
      Alert.alert('Share unavailable', `Your coordinates are ${coords.latitude.toFixed(5)}, ${coords.longitude.toFixed(5)}.`);
    }
  };

  const findNearbyService = async (service) => {
    const coords = location || await locateMe();
    if (!coords) return;

    try {
      const localPlaces = await fetchLocalAgencies(service, coords.latitude, coords.longitude);
      const places = localPlaces.length > 0
        ? localPlaces
        : await fetchNearbyServices(service, coords.latitude, coords.longitude);
      if (places.length === 0) {
        Alert.alert(`No ${service} found nearby`, 'No matching OpenStreetMap listings were found within 8 km.', [
          { text: 'Close', style: 'cancel' },
          { text: 'Search Google Maps', onPress: () => openExternalFacilitySearch(service, coords).catch(() => {}) },
        ]);
        return;
      }

      if (service === 'hospital') {
        setHospitalCenters(places.map((place) => ({
          ...place,
          lat: place.lat ?? place.latitude,
          lng: place.lng ?? place.longitude,
        })));
      }

      Alert.alert(
        `Nearest ${service === 'hospital' ? 'hospitals' : 'police stations'}`,
        places.slice(0, 3).map((place, index) => `${index + 1}. ${place.name} · ${place.distance.toFixed(1)} km`).join('\n'),
        [
          { text: 'Close', style: 'cancel' },
          {
            text: 'Directions to nearest',
            onPress: () => Linking.openURL(`https://www.google.com/maps/dir/?api=1&destination=${places[0].latitude},${places[0].longitude}`).catch(() => Alert.alert('Directions unavailable', 'Could not open a maps app.')),
          },
        ],
      );
    } catch {
      Alert.alert('Search unavailable', 'The public map services did not respond.', [
        { text: 'Close', style: 'cancel' },
        { text: 'Search Google Maps', onPress: () => openExternalFacilitySearch(service, coords).catch(() => {}) },
      ]);
    }
  };

  const callEmergency = async () => {
    setHotlineOpen(true);
    try {
      const data = await fetchJson(`${API_BASE}/api/agencies`);
      const agencies = (data.items || [])
        .filter((agency) => agency.hotline)
        .map((agency) => ({
          agency: agency.name,
          label: agency.hotline,
          number: String(agency.hotline).replace(/[^\d+]/g, ''),
        }))
        .filter((agency) => agency.number.length > 2);
      setLocalHotlines(agencies);
    } catch {
      setLocalHotlines([]);
    }
  };

  const dialHotline = async (number) => {
    try {
      await Linking.openURL(`tel:${number}`);
      setHotlineOpen(false);
    } catch {
      Alert.alert('Call unavailable', 'Your device could not open the phone dialer.');
    }
  };

  const loadAnnouncements = async () => {
    setAnnouncementsLoading(true);
    setAnnouncementsError('');
    try {
      const data = await fetchJson(`${API_BASE}/api/announcements`);
      setAnnouncements(Array.isArray(data.items) ? data.items : []);
    } catch {
      setAnnouncementsError('Could not load announcements. Check the API connection and try again.');
    } finally {
      setAnnouncementsLoading(false);
    }
  };

  const openAnnouncements = () => {
    setActiveTab('announcement');
    loadAnnouncements();
  };

  const loadProfile = async () => {
    try {
      const data = await fetchJson(`${API_BASE}/api/user/profile`);
      setProfile({
        full_name: data.full_name || 'Guest User',
        phone_number: data.phone_number || '09000000000',
        home_address: data.home_address || 'Bacoor, Cavite',
      });
    } catch {
      setProfile({
        full_name: 'Guest User',
        phone_number: '09000000000',
        home_address: 'Bacoor, Cavite',
      });
    }
  };

  const loadEmergencyContacts = async () => {
    try {
      const data = await fetchJson(`${API_BASE}/api/emergency-contacts`);
      setEmergencyContacts(Array.isArray(data.items) ? data.items : []);
    } catch {
      setEmergencyContacts([]);
    }
  };

  const saveProfile = async () => {
    try {
      const data = await fetchJson(`${API_BASE}/api/user/profile`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(profile),
      });
      setProfile(data.profile || profile);
      Alert.alert('Profile saved', 'Your profile information has been updated.');
    } catch {
      Alert.alert('Profile unavailable', 'The backend is offline right now. Your profile is still stored locally in this app session.');
    }
  };

  const saveEmergencyContact = async () => {
    if (!newContactName.trim() || !newContactPhone.trim()) {
      Alert.alert('Missing contact info', 'Add a name and phone number before saving an emergency contact.');
      return;
    }

    try {
      const payload = {
        contact_name: newContactName.trim(),
        contact_phone: newContactPhone.trim(),
        relationship: newContactRelationship.trim() || 'Emergency contact',
      };
      const data = await fetchJson(`${API_BASE}/api/emergency-contacts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const nextContact = data.item || payload;
      setEmergencyContacts((prev) => [nextContact, ...prev]);
      setNewContactName('');
      setNewContactPhone('');
      setNewContactRelationship('');
      Alert.alert('Emergency contact saved', `${nextContact.name || nextContact.contact_name} was added to your contact list.`);
    } catch {
      Alert.alert('Contact not saved', 'The server could not save this emergency contact right now.');
    }
  };

  const toggleEmergencyAlarm = () => {
    if (alarmActive) {
      Vibration.cancel();
      clearTimeout(alarmTimeout.current);
      setAlarmActive(false);
      return;
    }

    Vibration.vibrate([0, 120, 120, 120, 120, 120, 200, 200, 200, 200], true);
    setAlarmActive(true);
    alarmTimeout.current = setTimeout(() => {
      Vibration.cancel();
      setAlarmActive(false);
    }, 10000);
  };

  const triggerMedicalSos = async () => {
    const coords = location || await locateMe();
    if (!coords) return;

    try {
      await fetchJson(`${API_BASE}/api/sos/medical`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          lat: coords.latitude,
          lng: coords.longitude,
          label: 'Medical / Ambulance assistance',
        }),
      });
      setActiveTab('rescue');
      Alert.alert('Ambulance priority alert sent', 'Medical responders were alerted with your current GPS location.');
    } catch {
      Alert.alert('Rescue Me unavailable', 'The ambulance alert server is currently unavailable. Please call emergency services immediately.');
    }
  };

  const postSosLocation = (coords) => fetchJson(`${API_BASE}/api/sos`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      lat: coords.latitude,
      lng: coords.longitude,
      label: 'Live SOS from ResQLink mobile app',
    }),
  });

  const toggleLiveSos = async () => {
    if (sosActive) {
      sosSubscription.current?.remove();
      sosSubscription.current = null;
      setSosActive(false);
      try {
        await fetchJson(`${API_BASE}/api/sos`, { method: 'DELETE' });
        Alert.alert('SOS stopped', 'Live SOS sharing has been stopped.');
      } catch {
        Alert.alert('Could not reach the server', 'Location tracking stopped on this phone, but the server may still show the last SOS as active.');
      }
      return;
    }

    const coords = location || await locateMe();
    if (!coords) return;

    try {
      await postSosLocation(coords);
      setSosActive(true);
      sosSubscription.current = await Location.watchPositionAsync(
        { accuracy: Location.Accuracy.Balanced, timeInterval: 15000, distanceInterval: 25 },
        (position) => {
          const nextCoords = position.coords;
          setLocation(nextCoords);
          postSosLocation(nextCoords).catch(() => setStatus('SOS active; last location update failed'));
        },
      );
      Alert.alert('Live SOS active', 'Your location is being sent to the ResQLink server. Keep this app open and connected.');
    } catch {
      Alert.alert('SOS server unavailable', 'The app could not send an SOS to the backend. You can still share your location manually.', [
        { text: 'Close', style: 'cancel' },
        { text: 'Share location', onPress: shareLocation },
      ]);
    }
  };

  const findFastestRoute = async (destinationType = 'evacuation') => {
    const coords = location || await locateMe();
    if (!coords) return;

    setActiveTab('rescue');
    setRouteLoading(true);
    setRouteInfo(null);
    setRouteGeometry([]);

    try {
      let destinations;
      if (destinationType === 'hospital') {
        const localPlaces = await fetchLocalAgencies('hospital', coords.latitude, coords.longitude);
        const places = localPlaces.length > 0
          ? localPlaces
          : await fetchNearbyServices('hospital', coords.latitude, coords.longitude);
        destinations = places.map((place) => ({
          id: `hospital-${place.id}`,
          description: place.name,
          type: 'Hospital',
          kind: 'Hospital',
          status: 'OpenStreetMap destination',
          lat: place.latitude,
          lng: place.longitude,
        }));
        setHospitalCenters(destinations);
      } else {
        destinations = await loadHazards(coords);
      }

      if (destinations.length === 0) {
        Alert.alert(
          destinationType === 'hospital' ? 'No hospitals found' : 'No evacuation points found',
          'No mapped destinations were found nearby.',
          destinationType === 'hospital' ? [
            { text: 'Close', style: 'cancel' },
            { text: 'Search Google Maps', onPress: () => openExternalFacilitySearch('hospital', coords).catch(() => {}) },
          ] : undefined,
        );
        return;
      }

      const fastest = await findFastestRoadRoute(coords, destinations);
      setSelectedCenter(fastest.place);
      setRouteTarget(fastest.place);
      setRouteGeometry(fastest.geometry);
      setRouteInfo({
        durationMinutes: Math.round(fastest.duration / 60),
        distanceKm: fastest.distance / 1000,
        type: destinationType,
      });
    } catch (error) {
      Alert.alert('Route unavailable', `${error?.message || 'Could not calculate a road route.'} Check your internet connection and try again.`, [
        { text: 'Close', style: 'cancel' },
        ...(destinationType === 'hospital' ? [{
          text: 'Search Google Maps',
          onPress: () => openExternalFacilitySearch('hospital', coords).catch(() => {}),
        }] : []),
      ]);
    } finally {
      setRouteLoading(false);
    }
  };

  const openFireReport = () => {
    setType('Fire');
    if (!description.trim() || description.toLowerCase().includes('flood')) {
      setDescription('Fire reported near my current location.');
    }
    setReportOpen(true);
  };

  const pickReportPhoto = async (source) => {
    try {
      const permission = source === 'camera'
        ? await ImagePicker.requestCameraPermissionsAsync()
        : await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (!permission.granted) {
        Alert.alert('Permission needed', `Allow ${source === 'camera' ? 'camera' : 'photo library'} access to attach a report photo.`);
        return;
      }

      const result = source === 'camera'
        ? await ImagePicker.launchCameraAsync({ mediaTypes: ['images'], allowsEditing: true, quality: 0.65, base64: true })
        : await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], allowsEditing: true, quality: 0.65, base64: true });
      if (!result.canceled && result.assets?.[0]) {
        setReportPhoto(result.assets[0]);
      }
    } catch {
      Alert.alert('Photo unavailable', 'Could not open the camera or photo gallery.');
    }
  };

  const chooseReportPhoto = () => Alert.alert('Add a report photo', 'Take a new photo or choose one from your gallery.', [
    { text: 'Take photo', onPress: () => pickReportPhoto('camera') },
    { text: 'Choose from gallery', onPress: () => pickReportPhoto('gallery') },
    { text: 'Cancel', style: 'cancel' },
  ]);

  useEffect(() => {
    if (currentUser) {
      locateMe();
      loadAnnouncements();
      loadProfile();
      loadEmergencyContacts();
    }
  }, [currentUser]);

  useEffect(() => {
    setMapHtml(buildMapHtml(location, [...evacuationCenters, ...hospitalCenters], routeTarget, routeGeometry));
  }, [location, evacuationCenters, hospitalCenters, routeTarget, routeGeometry]);

  const handleSubmit = async () => {
    if (!type.trim() || description.trim().length < 10) {
      Alert.alert('Missing details', 'Add an incident description of at least 10 characters.');
      return;
    }

    try {
      setSubmitting(true);
      const submittedType = type.trim();
      if (reportPhoto && !reportPhoto.base64) {
        throw new Error('The selected photo could not be read. Please retake it or choose another image.');
      }
      const res = await fetch(`${API_BASE}/api/reports/json`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type: submittedType,
          description: description.trim(),
          lat: location?.latitude ?? DEFAULT_LAT,
          lng: location?.longitude ?? DEFAULT_LNG,
          image_base64: reportPhoto?.base64 || null,
          image_mime: reportPhoto?.mimeType || null,
        }),
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail = Array.isArray(data.detail) ? data.detail.map((item) => item.msg).join(', ') : data.detail;
        throw new Error(detail || `Report failed (${res.status})`);
      }

      setStatus('Hazard report sent successfully');
      setType('');
      setDescription('');
      setReportPhoto(null);
      setReportOpen(false);
      if (submittedType.toLowerCase() === 'fire') {
        setActiveTab('rescue');
      }
      await loadHazards(location);
      loadReports();
      loadSystemLogs();
      Alert.alert('Report sent', reportPhoto ? 'Your incident report and photo were submitted.' : 'Your incident report was submitted.');
    } catch (error) {
      const message = error?.message || 'Could not reach the report server.';
      setStatus(`Submission failed: ${message}`);
      Alert.alert('Report not sent', `${message}\n\nCheck that the backend is running and your phone is on the same Wi-Fi network.`);
    } finally {
      setSubmitting(false);
    }
  };

  const askAssistant = async (text) => {
   if (chatThinking) {
     return;
   }
   const history = chatMessages.slice(-6).map((m) => ({
     role: m.from === 'user' ? 'user' : 'bot',
     text: m.text,
   }));
   setChatMessages((prev) => [...prev, { id: Date.now(), from: 'user', text }]);
   setChatThinking(true);

   let replyText;
   try {
     const data = await fetchJson(
       `${API_BASE}/api/chat`,
       {
         method: 'POST',
         headers: { 'Content-Type': 'application/json' },
         body: JSON.stringify({
           message: text,
           history,
           lat: location?.latitude ?? null,
           lng: location?.longitude ?? null,
           centers: evacuationCenters
             .slice(0, 3)
             .map((c) => c.description || c.type || 'Evacuation point'),
         }),
       },
       20000,
     );
     replyText = data.reply;
   } catch {
     replyText = buildBotReply(text); // offline fallback
   } finally {
     setChatThinking(false);
  }
   setChatMessages((prev) => [...prev, { id: Date.now() + 1, from: 'bot', text: replyText }]);
 };

 const sendChat = () => {
   const value = chatInput.trim();
   if (!value) {
     return;
   }
   setChatInput('');
   askAssistant(value);
};

  const quickSend = (text) => askAssistant(text);

  const doLogin = () => {
    const email = 'guest@resqlink.app';
    if (!email) {
      Alert.alert('Missing email', 'Please enter your email.');
      return;
    }

    setCurrentUser({ name: 'Guest User', email });
  };

  const continueAsGuest = () => {
    setCurrentUser({ name: 'Guest', email: 'guest@local' });
  };

  const toggleAuthMode = () => {
    setAuthMode((prev) => (prev === 'login' ? 'register' : 'login'));
  };

  const topStatusColor = status.startsWith('Connection failed') ? '#b91c1c' : '#0f766e';

  if (!currentUser) {
    return (
      <KeyboardAvoidingView
        style={styles.loginScreen}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <StatusBar barStyle="dark-content" />
        <View style={styles.loginWrap}>
          <View style={styles.logoCircle}><Text style={styles.logoIcon}>🔥</Text></View>
          <Text style={styles.loginTitle}>ResQLink AI</Text>
          <Text style={styles.loginSub}>Emergency help at your fingertips</Text>

          {authMode === 'register' && (
            <View style={styles.fieldWrap}>
              <Text style={styles.fieldLabel}>Full name</Text>
              <TextInput style={styles.fieldInput} placeholder="Juan Dela Cruz" />
            </View>
          )}

          <View style={styles.fieldWrap}>
            <Text style={styles.fieldLabel}>Email</Text>
            <TextInput style={styles.fieldInput} placeholder="juan@example.com" keyboardType="email-address" />
          </View>

          <View style={styles.fieldWrap}>
            <Text style={styles.fieldLabel}>Password</Text>
            <TextInput style={styles.fieldInput} placeholder="••••••••" secureTextEntry />
          </View>

          <TouchableOpacity style={styles.submitButton} onPress={doLogin}>
            <Text style={styles.submitButtonText}>{authMode === 'login' ? 'Log in' : 'Create account'}</Text>
          </TouchableOpacity>

          <View style={styles.toggleRow}>
            <Text style={styles.toggleText}>{authMode === 'login' ? 'No account? ' : 'Have an account? '}</Text>
            <TouchableOpacity onPress={toggleAuthMode}>
              <Text style={styles.toggleLink}>{authMode === 'login' ? 'Register' : 'Log in'}</Text>
            </TouchableOpacity>
          </View>

          <Text style={styles.orLine}>or</Text>
          <TouchableOpacity onPress={continueAsGuest}>
            <Text style={styles.guestLink}>Continue as guest</Text>
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    );
  }

  return (
    <KeyboardAvoidingView
      style={styles.appContainer}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <StatusBar barStyle="dark-content" />

      <View style={styles.topBar}>
        <TouchableOpacity style={styles.chatHeadButton} onPress={() => setChatOpen(true)}>
          <Text style={styles.chatHeadText}>🤖 AI Chat</Text>
        </TouchableOpacity>

        <Text style={styles.topBarTitle}>Emergency Help</Text>

        <TouchableOpacity onPress={() => {
          setAnnouncementAdminToken('');
          setCurrentUser(null);
        }}>
          <Text style={styles.logoutText}>⎋</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.subHeader}>
        <Text style={styles.subHeaderText}>Be Ready with Emergency Preparedness</Text>
      </View>

      {activeTab === 'home' && (
        <ScrollView style={styles.screen} contentContainerStyle={styles.screenContent}>
          <View style={styles.grid}>
            <TouchableOpacity style={styles.tile} onPress={shareLocation}>
              <View style={styles.tileCircle}><Text style={styles.tileIcon}>📍</Text></View>
              <Text style={styles.tileLabel}>Share Location</Text>
            </TouchableOpacity>

            <TouchableOpacity style={styles.tile} onPress={() => setActiveTab('rescue')}>
              <View style={styles.tileCircle}><Text style={styles.tileIcon}>🚑</Text></View>
              <Text style={styles.tileLabel}>Rescue Me</Text>
            </TouchableOpacity>

            <TouchableOpacity style={styles.tile} onPress={() => findFastestRoute('hospital')}>
              <View style={styles.tileCircle}><Text style={styles.tileIcon}>🏥</Text></View>
              <Text style={styles.tileLabel}>Nearest Hospital</Text>
            </TouchableOpacity>

            <TouchableOpacity style={styles.tile} onPress={() => findNearbyService('police')}>
              <View style={styles.tileCircle}><Text style={styles.tileIcon}>🚓</Text></View>
              <Text style={styles.tileLabel}>Nearest Police Station</Text>
            </TouchableOpacity>

            <TouchableOpacity style={styles.tile} onPress={callEmergency}>
              <View style={styles.tileCircle}><Text style={styles.tileIcon}>📞</Text></View>
              <Text style={styles.tileLabel}>Emergency Call</Text>
            </TouchableOpacity>

            <TouchableOpacity style={styles.tile} onPress={toggleEmergencyAlarm}>
              <View style={styles.tileCircle}><Text style={styles.tileIcon}>🔔</Text></View>
              <Text style={styles.tileLabel}>Emergency Sound</Text>
            </TouchableOpacity>

            <TouchableOpacity style={styles.tile} onPress={openAnnouncements}>
              <View style={styles.tileCircle}><Text style={styles.tileIcon}>📣</Text></View>
              <Text style={styles.tileLabel}>Announcements</Text>
            </TouchableOpacity>

            <TouchableOpacity style={styles.tile} onPress={() => setActiveTab('settings')}>
              <View style={styles.tileCircle}><Text style={styles.tileIcon}>⚙️</Text></View>
              <Text style={styles.tileLabel}>Settings</Text>
            </TouchableOpacity>
          </View>
        </ScrollView>
      )}

      {activeTab === 'fire' && (
        <ScrollView style={styles.screen} contentContainerStyle={styles.fireScreen}>
          <View style={styles.fireHeader}>
            <View style={styles.locationPill}><Text style={styles.locationIcon}>📍</Text><Text style={styles.locationText}>{locationStatus}</Text></View>
            <View style={styles.avatar}><Text style={styles.avatarText}>{currentUser?.name?.charAt(0) || 'G'}</Text></View>
          </View>

          <Text style={styles.fireTitle}>{'Need emergency fire\nservice?'}</Text>

          <View style={styles.fireButtonWrap}>
            <View style={styles.fireRing}>
              <TouchableOpacity style={styles.fireButton} onPress={openFireReport}>
                <Text style={styles.fireIcon}>🔥</Text>
                <Text style={styles.fireButtonText}>Report fire</Text>
              </TouchableOpacity>
            </View>
            <Text style={styles.orText}>or</Text>
            <TouchableOpacity onPress={callEmergency}>
              <Text style={styles.emergencyCallText}>Emergency call</Text>
            </TouchableOpacity>
          </View>
        </ScrollView>
      )}

      {activeTab === 'report' && (
        <ScrollView style={styles.screen} contentContainerStyle={styles.reportScreen}>
          <Text style={styles.reportHeading}>Report an incident</Text>

          <View style={styles.fieldWrapReport}>
            <Text style={styles.fieldLabel}>Incident type</Text>
            <TextInput
              style={styles.fieldInput}
              value={type}
              onChangeText={setType}
              placeholder="e.g. Flood, fire, road hazard"
              maxLength={80}
            />
          </View>

          <View style={styles.fieldWrapReport}>
            <Text style={styles.fieldLabel}>Describe the emergency</Text>
            <TextInput
              style={[styles.fieldInput, styles.textArea]}
              value={description}
              onChangeText={setDescription}
              maxLength={280}
              multiline
              placeholder="e.g. Big fire near Molino Market, people trapped"
            />
          </View>

          <TouchableOpacity style={styles.photoPickerButton} onPress={chooseReportPhoto}>
            <Text style={styles.photoPickerText}>{reportPhoto ? 'Change attached photo' : '📷 Add photo'}</Text>
          </TouchableOpacity>
          {reportPhoto && (
            <View style={styles.reportPhotoRow}>
              <Image source={{ uri: reportPhoto.uri }} style={styles.reportPhotoPreview} />
              <Text style={styles.reportPhotoName} numberOfLines={2}>{reportPhoto.fileName || 'Photo attached'}</Text>
              <TouchableOpacity onPress={() => setReportPhoto(null)}>
                <Text style={styles.removePhotoText}>Remove</Text>
              </TouchableOpacity>
            </View>
          )}

          <TouchableOpacity style={styles.submitButton} onPress={handleSubmit}>
            <Text style={styles.submitButtonText}>Submit report</Text>
          </TouchableOpacity>

          <View style={styles.aiCard}>
            <Text style={styles.aiCardTitle}>🤖 AI Emergency Assessment:</Text>
            <Text style={styles.aiCardText}>Incident categorized as High Priority Incident. Dispatching report to the nearest responder station.</Text>
          </View>
        </ScrollView>
      )}

      {activeTab === 'announcement' && (
        <ScrollView style={styles.screen} contentContainerStyle={styles.databaseScreen}>
          <View style={styles.centerHeader}>
            <Text style={styles.reportHeading}>Official public announcements</Text>
            <TouchableOpacity style={styles.locateButton} onPress={loadAnnouncements} disabled={announcementsLoading}>
              <Text style={styles.locateButtonText}>{announcementsLoading ? 'Loading…' : '↻ Refresh'}</Text>
            </TouchableOpacity>
          </View>
          {announcementsError ? <Text style={styles.errorText}>{announcementsError}</Text> : null}
          {!announcementsLoading && !announcementsError && announcements.length === 0 ? (
            <Text style={styles.emptyText}>No announcements have been published yet.</Text>
          ) : null}
          {announcements.map((item) => (
            <View key={String(item.id)} style={styles.announcementCard}>
              <View style={[styles.announcementBadge, item.level === 'critical' ? styles.announcementCritical : item.level === 'warning' ? styles.announcementWarning : styles.announcementInfo]}>
                <Text style={styles.announcementBadgeText}>{item.level || 'info'}</Text>
              </View>
              <Text style={styles.announcementTitle}>{item.title}</Text>
              <Text style={styles.announcementMessage}>{item.message}</Text>
              <Text style={styles.announcementMeta}>{item.audience || 'all'} · {item.created_at ? new Date(item.created_at).toLocaleString() : ''}</Text>
            </View>
          ))}
        </ScrollView>
      )}

      {activeTab === 'settings' && (
        <ScrollView style={styles.screen} contentContainerStyle={styles.reportScreen}>
          <Text style={styles.reportHeading}>Settings + User Info</Text>

          <View style={styles.fieldWrapReport}>
            <Text style={styles.fieldLabel}>Full name</Text>
            <TextInput
              style={styles.fieldInput}
              value={profile.full_name}
              onChangeText={(value) => setProfile((prev) => ({ ...prev, full_name: value }))}
            />
          </View>

          <View style={styles.fieldWrapReport}>
            <Text style={styles.fieldLabel}>Phone number</Text>
            <TextInput
              style={styles.fieldInput}
              value={profile.phone_number}
              keyboardType="phone-pad"
              onChangeText={(value) => setProfile((prev) => ({ ...prev, phone_number: value }))}
            />
          </View>

          <View style={styles.fieldWrapReport}>
            <Text style={styles.fieldLabel}>Home address</Text>
            <TextInput
              style={[styles.fieldInput, styles.textArea]}
              value={profile.home_address}
              multiline
              onChangeText={(value) => setProfile((prev) => ({ ...prev, home_address: value }))}
            />
          </View>

          <TouchableOpacity style={styles.submitButton} onPress={saveProfile}>
            <Text style={styles.submitButtonText}>Save profile</Text>
          </TouchableOpacity>

          <Text style={[styles.reportHeading, { marginTop: 20 }]}>Emergency contacts</Text>
          <View style={styles.fieldWrapReport}>
            <Text style={styles.fieldLabel}>Contact name</Text>
            <TextInput style={styles.fieldInput} value={newContactName} onChangeText={setNewContactName} placeholder="Maria Dela Cruz" />
          </View>
          <View style={styles.fieldWrapReport}>
            <Text style={styles.fieldLabel}>Phone number</Text>
            <TextInput style={styles.fieldInput} value={newContactPhone} keyboardType="phone-pad" onChangeText={setNewContactPhone} placeholder="0917-123-4567" />
          </View>
          <View style={styles.fieldWrapReport}>
            <Text style={styles.fieldLabel}>Relationship</Text>
            <TextInput style={styles.fieldInput} value={newContactRelationship} onChangeText={setNewContactRelationship} placeholder="Mother" />
          </View>

          <TouchableOpacity style={styles.photoPickerButton} onPress={saveEmergencyContact}>
            <Text style={styles.photoPickerText}>Add emergency contact</Text>
          </TouchableOpacity>

          {emergencyContacts.length > 0 && (
            <View style={{ marginTop: 16 }}>
              {emergencyContacts.map((contact) => (
                <View key={String(contact.id)} style={styles.recordCard}>
                  <Text style={styles.recordTitle}>{contact.name || contact.contact_name}</Text>
                  <Text style={styles.recordMeta}>{contact.relationship || 'Emergency contact'}</Text>
                  <Text style={styles.recordDescription}>{contact.phone || contact.contact_phone}</Text>
                </View>
              ))}
            </View>
          )}
        </ScrollView>
      )}

      {activeTab === 'database' && (
        <ScrollView style={styles.screen} contentContainerStyle={styles.databaseScreen}>
          <View style={styles.databaseSections}>
            <TouchableOpacity
              style={[styles.databaseSectionButton, databaseSection === 'reports' && styles.databaseSectionActive]}
              onPress={() => setDatabaseSection('reports')}
            >
              <Text style={[styles.databaseSectionText, databaseSection === 'reports' && styles.databaseSectionTextActive]}>Reports</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.databaseSectionButton, databaseSection === 'logs' && styles.databaseSectionActive]}
              onPress={() => setDatabaseSection('logs')}
            >
              <Text style={[styles.databaseSectionText, databaseSection === 'logs' && styles.databaseSectionTextActive]}>System logs</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.databaseHeader}>
            <View>
              <Text style={styles.reportHeading}>{databaseSection === 'reports' ? 'Incident reports' : 'System logs'}</Text>
              <Text style={styles.databaseCount}>
                {databaseSection === 'reports' ? `${reports.length} saved reports` : `${systemLogs.length} log entries`}
              </Text>
            </View>
            <TouchableOpacity
              style={styles.databaseRefreshButton}
              onPress={databaseSection === 'reports' ? loadReports : loadSystemLogs}
              disabled={databaseSection === 'reports' ? reportsLoading : logsLoading}
            >
              <Text style={styles.databaseRefreshText}>
                {(databaseSection === 'reports' ? reportsLoading : logsLoading) ? 'Loading…' : '↻ Refresh'}
              </Text>
            </TouchableOpacity>
          </View>

          {databaseSection === 'reports' ? (reportsLoading && reports.length === 0 ? (
            <ActivityIndicator style={{ marginTop: 28 }} color="#b91c1c" />
          ) : reportsError ? (
            <View style={styles.databaseMessage}>
              <Text style={styles.databaseMessageText}>{reportsError}</Text>
              <TouchableOpacity style={styles.submitButton} onPress={loadReports}>
                <Text style={styles.submitButtonText}>Retry</Text>
              </TouchableOpacity>
            </View>
          ) : reports.length === 0 ? (
            <Text style={styles.emptyText}>No incident reports have been saved yet.</Text>
          ) : (
            reports.map((report) => (
              <View key={String(report.id)} style={styles.recordCard}>
                <View style={styles.recordHeader}>
                  <Text
 style={styles.recordTitle}>{report.type}</Text>                  <Text style={[
                    styles.recordStatus,
                    report.status === 'Community verified' ? styles.recordStatusVerified : styles.recordStatusPending,
                  ]}>{report.status || 'Saved'}</Text>
                </View>
                <Text style={styles.recordDescription}>{report.description}</Text>
                <Text style={styles.recordMeta}>
                  {report.time ? new Date(report.time).toLocaleString() : 'Date unavailable'}
                </Text>
                <Text style={styles.recordMeta}>
                  {Number(report.lat).toFixed(5)}, {Number(report.lng).toFixed(5)}
                </Text>
                {report.photo_url && (
                  <Image
                    source={{ uri: `${API_BASE}${report.photo_url}` }}
                    style={styles.recordPhoto}
                    resizeMode="cover"
                  />
                )}
              </View>
            ))
          )) : (logsLoading && systemLogs.length === 0 ? (
            <ActivityIndicator style={{ marginTop: 28 }} color="#b91c1c" />
          ) : logsError ? (
            <View style={styles.databaseMessage}>
              <Text style={styles.databaseMessageText}>{logsError}</Text>
              <TouchableOpacity style={styles.submitButton} onPress={loadSystemLogs}>
                <Text style={styles.submitButtonText}>Retry</Text>
              </TouchableOpacity>
            </View>
          ) : systemLogs.length === 0 ? (
            <Text style={styles.emptyText}>No system events have been logged yet.</Text>
          ) : (
            systemLogs.map((entry) => (
              <View key={String(entry.id)} style={styles.recordCard}>
                <Text style={styles.recordTitle}>{entry.action}</Text>
                <Text style={styles.recordMeta}>{entry.time ? new Date(entry.time).toLocaleString() : 'Date unavailable'}</Text>
              </View>
            ))
          ))}
        </ScrollView>
      )}

      {activeTab === 'rescue' && (
        <ScrollView style={styles.screen} contentContainerStyle={styles.rescueScreen}>
          <View style={styles.rescueHeader}>
            <Text style={styles.rescueTitle}>Rescue Status & Safe Evacuation</Text>
            <Text style={styles.rescueMeta}>Fire service team is on the way (~5 mins)</Text>
            <Text style={styles.statusBadge}>
              {sosActive ? '🚨 Live SOS active' : location ? '📍 GPS location active' : '📍 Waiting for GPS'}
            </Text>
          </View>

          <View style={styles.mapCard}>
            <WebView
              style={styles.map}
              source={{ html: mapHtml }}
              originWhitelist={['*']}
              javaScriptEnabled
              domStorageEnabled
              scrollEnabled={false}
              onError={() => setStatus('Map tiles could not load. Check your internet connection.')}
              onMessage={(event) => {
                const center = [...evacuationCenters, ...hospitalCenters][Number(event.nativeEvent.data)];
                if (center) {
                  setSelectedCenter(center);
                  setRouteTarget(center);
                  setRouteGeometry([]);
                  setRouteInfo(null);
                }
              }}
            />
          </View>
          <View style={styles.mapInfoRow}>
            <Text style={styles.mapSubText}>
              {location ? `${location.latitude.toFixed(5)}, ${location.longitude.toFixed(5)}` : locationStatus}
            </Text>
            <TouchableOpacity onPress={locateMe} style={styles.locateButton}>
              <Text style={styles.locateButtonText}>◎ Locate me</Text>
            </TouchableOpacity>
          </View>
          {selectedCenter && (
            <View style={styles.selectedCenter}>
              <View style={styles.selectedCenterCopy}>
                <Text style={styles.selectedCenterName}>{selectedCenter.description || selectedCenter.type}</Text>
                <Text style={styles.centerMeta}>Evacuation point · {selectedCenter.type}</Text>
              </View>
              <TouchableOpacity
                style={styles.directionsButton}
                onPress={() => Linking.openURL(`https://www.google.com/maps/dir/?api=1&destination=${selectedCenter.lat},${selectedCenter.lng}&travelmode=walking`).catch(() => Alert.alert('Directions unavailable', 'Could not open a maps app.'))}
              >
                <Text style={styles.directionsButtonText}>Directions</Text>
              </TouchableOpacity>
            </View>
          )}

          <View style={styles.actionRow}>
            <TouchableOpacity style={styles.actionButton} onPress={toggleLiveSos}>
              <Text style={styles.actionButtonText}>{sosActive ? '🛑 Stop Live SOS' : '📡 Share Live SOS'}</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.actionButton} onPress={toggleEmergencyAlarm}>
              <Text style={styles.actionButtonText}>{alarmActive ? '🔕 Stop Alarm' : '📢 Alarm Sound'}</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.routeActionRow}>
            <TouchableOpacity
              style={[styles.routeChoiceButton, styles.routeEvacuationButton]}
              onPress={() => findFastestRoute('evacuation')}
              disabled={routeLoading}
            >
              <Text style={styles.routeChoiceText}>Fastest evacuation</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.routeChoiceButton, styles.routeHospitalButton]}
              onPress={() => findFastestRoute('hospital')}
              disabled={routeLoading}
            >
              <Text style={styles.routeChoiceText}>Fastest hospital</Text>
            </TouchableOpacity>
          </View>
          {routeLoading && <ActivityIndicator style={{ marginBottom: 12 }} color="#b91c1c" />}

          <View style={styles.routeCard}>
            <Text style={styles.routeTitle}>{routeInfo?.type === 'hospital' ? 'Fastest hospital route' : 'Fastest evacuation route'}</Text>
            <Text style={styles.routeText}>{routeTarget?.description || 'Choose an evacuation or hospital route'}</Text>
            <Text style={styles.routeMeta}>
              {routeInfo
                ? `Driving · ${routeInfo.durationMinutes} min · ${routeInfo.distanceKm.toFixed(1)} km · not hazard-verified`
                : 'Fastest route is calculated from public road data'}
            </Text>
          </View>

          <TouchableOpacity style={[styles.primaryActionButton, { backgroundColor: '#dc2626', marginBottom: 12 }]} onPress={triggerMedicalSos}>
            <Text style={styles.primaryActionButtonText}>Emergency ambulance / Rescue Me</Text>
          </TouchableOpacity>

          <View style={styles.responderCard}>
            <View style={styles.responderAvatar}><Text style={styles.responderIcon}>👨‍🚒</Text></View>
            <View style={styles.responderInfo}>
              <Text style={styles.responderName}>Robert William</Text>
              <Text style={styles.responderMeta}>Fireman · En route</Text>
            </View>
            <TouchableOpacity style={styles.callButton} onPress={callEmergency}>
              <Text style={styles.callIcon}>📞</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.centerHeader}>
            <Text style={styles.centerHeaderText}>Nearby Evacuation Centers</Text>
            <TouchableOpacity onPress={loadHazards}>
              <Text style={styles.centerRefreshText}>🔄 Refresh</Text>
            </TouchableOpacity>
          </View>

          {loading ? (
            <ActivityIndicator style={{ marginTop: 12 }} />
          ) : evacuationCenters.length === 0 ? (
            <Text style={styles.emptyText}>No nearby evacuation centers found.</Text>
          ) : (
            evacuationCenters.map((center) => (
              <TouchableOpacity key={String(center.id)} style={styles.centerCard} onPress={() => {
                setSelectedCenter(center);
                setRouteTarget(center);
                setRouteGeometry([]);
                setRouteInfo(null);
              }}>
                <Text style={styles.centerName}>{center.description || center.type}</Text>
                <Text style={styles.centerMeta}>{center.type} · {center.status}</Text>
                {center.address ? <Text style={styles.centerMeta}>{center.address}</Text> : null}
                <Text style={styles.centerMeta}>
                  Map pin: {Number(center.lat).toFixed(5)}, {Number(center.lng).toFixed(5)}
                </Text>
              </TouchableOpacity>
            ))
          )}
        </ScrollView>
      )}

      <View style={styles.tabBar}>
        <TouchableOpacity style={[styles.tabItem, activeTab === 'home' && styles.tabItemActive]} onPress={() => setActiveTab('home')}>
          <Text style={styles.tabIcon}>🏠</Text>
          <Text style={[styles.tabText, activeTab === 'home' && styles.tabTextActive]}>Emergency</Text>
        </TouchableOpacity>

        <TouchableOpacity style={[styles.tabItem, activeTab === 'fire' && styles.tabItemActive]} onPress={() => setActiveTab('fire')}>
          <Text style={styles.tabIcon}>🔥</Text>
          <Text style={[styles.tabText, activeTab === 'fire' && styles.tabTextActive]}>Fire</Text>
        </TouchableOpacity>

        <TouchableOpacity style={[styles.tabItem, activeTab === 'report' && styles.tabItemActive]} onPress={() => setActiveTab('report')}>
          <Text style={styles.tabIcon}>⚠️</Text>
          <Text style={[styles.tabText, activeTab === 'report' && styles.tabTextActive]}>Report</Text>
        </TouchableOpacity>

        <TouchableOpacity style={[styles.tabItem, activeTab === 'database' && styles.tabItemActive]} onPress={openDatabase}>
          <Text style={styles.tabIcon}>🗂️</Text>
          <Text style={[styles.tabText, activeTab === 'database' && styles.tabTextActive]}>Database</Text>
        </TouchableOpacity>

        <TouchableOpacity style={[styles.tabItem, activeTab === 'rescue' && styles.tabItemActive]} onPress={() => setActiveTab('rescue')}>
          <Text style={styles.tabIcon}>🚑</Text>
          <Text style={[styles.tabText, activeTab === 'rescue' && styles.tabTextActive]}>Rescue Me</Text>
        </TouchableOpacity>
      </View>

      <Modal transparent visible={hotlineOpen} animationType="slide" onRequestClose={() => setHotlineOpen(false)}>
        <View style={styles.hotlineModal}>
          <TouchableOpacity style={styles.hotlineBackdrop} activeOpacity={1} onPress={() => setHotlineOpen(false)} />
          <View style={styles.hotlineSheet}>
            <View style={styles.sheetHandle} />
            <View style={styles.sheetTitleRow}>
              <Text style={styles.sheetTitle}>Emergency hotlines</Text>
              <TouchableOpacity onPress={() => setHotlineOpen(false)}>
                <Text style={styles.closeText}>✕</Text>
              </TouchableOpacity>
            </View>
            <Text style={styles.hotlineNote}>Tap a number to open your phone dialer.</Text>
            <ScrollView style={styles.hotlineList}>
              {[...emergencyHotlines, ...localHotlines].map((hotline, index) => (
                <TouchableOpacity key={`${hotline.agency}-${hotline.label}-${index}`} style={styles.hotlineRow} onPress={() => dialHotline(hotline.number)}>
                  <View style={styles.hotlineCopy}>
                    <Text style={styles.hotlineAgency}>{hotline.agency}</Text>
                    <Text style={styles.hotlineNumber}>{hotline.label}</Text>
                  </View>
                  <Text style={styles.hotlineCall}>Call</Text>
                </TouchableOpacity>
              ))}
            </ScrollView>
            <TouchableOpacity onPress={() => Linking.openURL('https://ehotlines.e.gov.ph/').catch(() => {})}>
              <Text style={styles.hotlineSource}>Philippine government hotline directory</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      <Modal transparent visible={reportOpen} animationType="slide" onRequestClose={() => setReportOpen(false)}>
        <TouchableOpacity style={styles.sheetOverlay} activeOpacity={1} onPress={() => setReportOpen(false)} />
        <View style={styles.sheetCard}>
          <View style={styles.sheetHandle} />
          <View style={styles.sheetTitleRow}>
            <Text style={styles.sheetTitle}>Send {type || 'incident'} report</Text>
            <TouchableOpacity onPress={() => setReportOpen(false)}>
              <Text style={styles.closeText}>✕</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.fieldWrapReport}>
            <Text style={styles.fieldLabel}>Any casualties</Text>
            <TextInput style={styles.fieldInput} value="no" editable={false} />
          </View>

          <View style={styles.fieldWrapReport}>
            <Text style={styles.fieldLabel}>Location</Text>
            <TextInput
              style={styles.fieldInput}
              value={location ? `${location.latitude.toFixed(5)}, ${location.longitude.toFixed(5)}` : 'Waiting for GPS location'}
              editable={false}
            />
          </View>

          <View style={styles.fieldWrapReport}>
            <Text style={styles.fieldLabel}>Description</Text>
            <TextInput
              style={[styles.fieldInput, styles.textArea]}
              value={description}
              onChangeText={setDescription}
              multiline
              placeholder="What happened?"
            />
          </View>

          <TouchableOpacity style={styles.photoPickerButton} onPress={chooseReportPhoto}>
            <Text style={styles.photoPickerText}>{reportPhoto ? 'Change attached photo' : '📷 Add photo'}</Text>
          </TouchableOpacity>
          {reportPhoto && (
            <View style={styles.reportPhotoRow}>
              <Image source={{ uri: reportPhoto.uri }} style={styles.reportPhotoPreview} />
              <Text style={styles.reportPhotoName} numberOfLines={2}>{reportPhoto.fileName || 'Photo attached'}</Text>
              <TouchableOpacity onPress={() => setReportPhoto(null)}>
                <Text style={styles.removePhotoText}>Remove</Text>
              </TouchableOpacity>
            </View>
          )}

          <TouchableOpacity style={styles.submitButton} onPress={handleSubmit} disabled={submitting}>
            {submitting ? <ActivityIndicator color="#fff" /> : <Text style={styles.submitButtonText}>{reportPhoto ? 'Send report with photo' : 'Send report'}</Text>}
          </TouchableOpacity>
        </View>
      </Modal>

      <Modal transparent visible={chatOpen} animationType="slide" onRequestClose={() => setChatOpen(false)}>
        <TouchableOpacity style={styles.chatOverlay} activeOpacity={1} onPress={() => setChatOpen(false)} />
        <View style={styles.chatModal}>
          <View style={styles.chatHeader}>
            <Text style={styles.chatHeaderText}>🤖 ResQLink Assistant</Text>
            <TouchableOpacity onPress={() => setChatOpen(false)}>
              <Text style={styles.closeTextWhite}>✕</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.quickRow}>
            {quickPrompts.map((prompt) => (
              <TouchableOpacity key={prompt} style={styles.quickChip} onPress={() => quickSend(prompt)}>
                <Text style={styles.quickChipText}>{prompt}</Text>
              </TouchableOpacity>
            ))}
          </View>

          <ScrollView style={styles.chatBody} contentContainerStyle={styles.chatBodyContent}>
            {chatMessages.map((message) => (
              <View
                key={message.id}
                style={[
                  styles.chatBubble,
                  message.from === 'user' ? styles.userBubble : styles.botBubble,
                ]}
              >
                <Text style={[styles.chatText, message.from === 'user' && styles.chatTextUser]}>{message.text}</Text>
              </View>
            ))}
            {chatThinking && (
                <View style={[styles.chatBubble, styles.botBubble]}>
                  <Text style={styles.chatText}>Typing…</Text>
                </View>
              )}
          </ScrollView>

          <View style={styles.chatFooter}>
            <TextInput
              style={styles.chatInput}
              value={chatInput}
              onChangeText={setChatInput}
              placeholder="Ask about fire safety, evacuation..."
              onSubmitEditing={sendChat}
            />
            <TouchableOpacity style={styles.chatSendButton} onPress={sendChat}>
              <Text style={styles.chatSendText}>➤</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  loginScreen: {
    flex: 1,
    backgroundColor: '#f4f6f8',
    justifyContent: 'center',
  },
  loginWrap: {
    paddingHorizontal: 26,
    paddingVertical: 50,
    maxWidth: 480,
    alignSelf: 'center',
    width: '100%',
  },
  logoCircle: {
    width: 92,
    height: 92,
    borderRadius: 46,
    backgroundColor: '#ef4444',
    justifyContent: 'center',
    alignItems: 'center',
    alignSelf: 'center',
    marginBottom: 20,
    shadowColor: '#ef4444',
    shadowOpacity: 0.35,
    shadowRadius: 15,
    elevation: 6,
  },
  logoIcon: {
    fontSize: 46,
  },
  loginTitle: {
    fontSize: 24,
    fontWeight: '700',
    textAlign: 'center',
    marginBottom: 6,
    color: '#1f2937',
  },
  loginSub: {
    fontSize: 13,
    color: '#6b7280',
    textAlign: 'center',
    marginBottom: 36,
  },
  fieldWrap: {
    marginBottom: 16,
  },
  fieldWrapReport: {
    marginBottom: 14,
  },
  fieldLabel: {
    fontSize: 13,
    color: '#1f2937',
    fontWeight: '600',
    marginBottom: 8,
  },
  fieldInput: {
    width: '100%',
    paddingHorizontal: 14,
    paddingVertical: 12,
    borderRadius: 10,
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: '#e5e7eb',
    fontSize: 14,
    color: '#1f2937',
  },
  textArea: {
    minHeight: 90,
    textAlignVertical: 'top',
  },
  photoPickerButton: {
    alignItems: 'center',
    paddingVertical: 12,
    marginBottom: 10,
    backgroundColor: '#fff7ed',
    borderWidth: 1,
    borderColor: '#fed7aa',
    borderRadius: 10,
  },
  photoPickerText: {
    color: '#c2410c',
    fontSize: 14,
    fontWeight: '700',
  },
  reportPhotoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 10,
  },
  reportPhotoPreview: {
    width: 58,
    height: 58,
    borderRadius: 8,
    backgroundColor: '#e5e7eb',
  },
  reportPhotoName: {
    flex: 1,
    marginHorizontal: 10,
    color: '#374151',
    fontSize: 12,
  },
  removePhotoText: {
    color: '#b91c1c',
    fontWeight: '700',
    fontSize: 12,
  },
  submitButton: {
    width: '100%',
    paddingVertical: 15,
    backgroundColor: '#ef4444',
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 6,
  },
  submitButtonText: {
    color: '#fff',
    fontSize: 15,
    fontWeight: '700',
  },
  toggleRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginTop: 14,
  },
  toggleText: {
    color: '#6b7280',
    fontSize: 13,
  },
  toggleLink: {
    color: '#ef4444',
    fontWeight: '700',
    fontSize: 13,
  },
  orLine: {
    textAlign: 'center',
    marginVertical: 22,
    fontSize: 12,
    color: '#6b7280',
  },
  guestLink: {
    textAlign: 'center',
    color: '#ef4444',
    fontWeight: '700',
    fontSize: 13,
  },
  appContainer: {
    flex: 1,
    backgroundColor: '#f8fafc',
  },
  topBar: {
    backgroundColor: '#ef4444',
    paddingHorizontal: 18,
    paddingVertical: 14,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  chatHeadButton: {
    backgroundColor: 'rgba(255,255,255,0.2)',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 18,
  },
  chatHeadText: {
    color: '#fff',
    fontSize: 12,
    fontWeight: '700',
  },
  topBarTitle: {
    color: '#fff',
    fontSize: 17,
    fontWeight: '700',
  },
  logoutText: {
    color: '#fff',
    fontSize: 24,
    fontWeight: '700',
  },
  subHeader: {
    backgroundColor: '#ffffff',
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#e5e7eb',
    alignItems: 'center',
  },
  subHeaderText: {
    color: '#6b7280',
    fontSize: 13,
  },
  screen: {
    flex: 1,
    backgroundColor: '#f8fafc',
    paddingHorizontal: 18,
    paddingBottom: 90,
  },
  screenContent: {
    paddingTop: 20,
    paddingBottom: 30,
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    marginTop: 6,
  },
  tile: {
    width: '46%',
    alignItems: 'center',
    marginBottom: 28,
  },
  tileCircle: {
    width: 96,
    height: 96,
    borderRadius: 48,
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: '#e5e7eb',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 12,
  },
  tileIcon: {
    fontSize: 42,
  },
  tileLabel: {
    fontSize: 13,
    color: '#1f2937',
    fontWeight: '600',
    textAlign: 'center',
  },
  fireScreen: {
    paddingTop: 18,
    paddingBottom: 30,
  },
  fireHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 20,
  },
  locationPill: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  locationIcon: {
    fontSize: 16,
    marginRight: 6,
  },
  locationText: {
    color: '#1f2937',
    fontSize: 13,
    fontWeight: '600',
  },
  avatar: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: '#fbbf24',
    justifyContent: 'center',
    alignItems: 'center',
  },
  avatarText: {
    color: '#fff',
    fontWeight: '700',
  },
  fireTitle: {
    fontSize: 26,
    fontWeight: '700',
    lineHeight: 32,
    textAlign: 'center',
    marginBottom: 30,
    color: '#1f2937',
  },
  fireButtonWrap: {
    alignItems: 'center',
  },
  fireRing: {
    width: 220,
    height: 220,
    borderRadius: 110,
    borderWidth: 2,
    borderColor: '#fee2e2',
    justifyContent: 'center',
    alignItems: 'center',
  },
  fireButton: {
    width: 180,
    height: 180,
    borderRadius: 90,
    backgroundColor: '#ef4444',
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#ef4444',
    shadowOpacity: 0.35,
    shadowRadius: 18,
    elevation: 5,
  },
  fireIcon: {
    fontSize: 52,
  },
  fireButtonText: {
    color: '#fff',
    fontSize: 15,
    fontWeight: '700',
    marginTop: 4,
  },
  orText: {
    marginVertical: 28,
    fontSize: 12,
    color: '#6b7280',
  },
  emergencyCallText: {
    color: '#ef4444',
    fontSize: 14,
    fontWeight: '700',
  },
  reportScreen: {
    paddingTop: 20,
    paddingBottom: 30,
  },
  databaseScreen: {
    paddingTop: 16,
    paddingBottom: 30,
  },
  databaseSections: {
    flexDirection: 'row',
    backgroundColor: '#e5e7eb',
    borderRadius: 10,
    padding: 3,
    marginBottom: 16,
  },
  databaseSectionButton: {
    flex: 1,
    minHeight: 40,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 8,
  },
  databaseSectionActive: {
    backgroundColor: '#fff',
  },
  databaseSectionText: {
    color: '#6b7280',
    fontSize: 13,
    fontWeight: '600',
  },
  databaseSectionTextActive: {
    color: '#b91c1c',
  },
  databaseHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  databaseCount: {
    color: '#6b7280',
    fontSize: 12,
    marginTop: 2,
  },
  databaseRefreshButton: {
    paddingHorizontal: 12,
    paddingVertical: 9,
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: '#e5e7eb',
    borderRadius: 8,
  },
  databaseRefreshText: {
    color: '#b91c1c',
    fontSize: 12,
    fontWeight: '700',
  },
  databaseMessage: {
    padding: 14,
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: '#e5e7eb',
    borderRadius: 10,
  },
  databaseMessageText: {
    color: '#475569',
    fontSize: 13,
    lineHeight: 19,
  },
  recordCard: {
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: '#e5e7eb',
    borderRadius: 10,
    padding: 14,
    marginBottom: 10,
  },
  recordHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  recordTitle: {
    flex: 1,
    color: '#1f2937',
    fontSize: 14,
    fontWeight: '700',
    paddingRight: 8,
  },
  recordStatus: {
    overflow: 'hidden',
    borderRadius: 12,
    paddingHorizontal: 8,
    paddingVertical: 4,
    fontSize: 10,
    fontWeight: '700',
  },
  recordStatusVerified: {
    color: '#166534',
    backgroundColor: '#dcfce7',
  },
  recordStatusPending: {
    color: '#92400e',
    backgroundColor: '#fef3c7',
  },
  recordDescription: {
    color: '#374151',
    fontSize: 13,
    lineHeight: 19,
    marginBottom: 8,
  },
  recordMeta: {
    color: '#6b7280',
    fontSize: 11,
    marginTop: 3,
  },
  recordPhoto: {
    width: '100%',
    height: 180,
    marginTop: 10,
    borderRadius: 8,
    backgroundColor: '#e5e7eb',
  },
  reportHeading: {
    fontSize: 16,
    fontWeight: '700',
    color: '#1f2937',
    marginBottom: 14,
  },
  aiCard: {
    backgroundColor: '#fee2e2',
    borderLeftWidth: 4,
    borderLeftColor: '#ef4444',
    borderRadius: 10,
    padding: 14,
    marginTop: 18,
  },
  aiCardTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: '#991b1b',
    marginBottom: 4,
  },
  aiCardText: {
    fontSize: 13,
    color: '#1f2937',
    lineHeight: 18,
  },
  rescueScreen: {
    paddingTop: 0,
    paddingBottom: 30,
  },
  rescueHeader: {
    backgroundColor: '#ef4444',
    paddingHorizontal: 20,
    paddingVertical: 18,
    borderBottomLeftRadius: 18,
    borderBottomRightRadius: 18,
    marginBottom: 18,
  },
  rescueTitle: {
    color: '#fff',
    fontSize: 18,
    fontWeight: '700',
    marginBottom: 4,
  },
  rescueMeta: {
    color: '#fff',
    fontSize: 12,
    opacity: 0.9,
  },
  statusBadge: {
    marginTop: 10,
    fontSize: 12,
    fontWeight: '700',
    color: '#111827',
    backgroundColor: '#fef3c7',
    borderRadius: 20,
    paddingHorizontal: 10,
    paddingVertical: 6,
    alignSelf: 'flex-start',
  },
  mapCard: {
    backgroundColor: '#e2e8f0',
    borderRadius: 14,
    height: 280,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: '#cbd5e1',
    overflow: 'hidden',
  },
  map: {
    width: '100%',
    height: '100%',
  },
  mapSubText: {
    color: '#475569',
    fontSize: 12,
  },
  mapAttribution: {
    position: 'absolute',
    right: 6,
    bottom: 6,
    backgroundColor: 'rgba(255,255,255,0.88)',
    paddingHorizontal: 5,
    paddingVertical: 3,
    borderRadius: 3,
  },
  mapAttributionText: {
    color: '#334155',
    fontSize: 9,
  },
  mapInfoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 14,
    paddingHorizontal: 2,
  },
  locateButton: {
    paddingHorizontal: 10,
    paddingVertical: 7,
    borderRadius: 8,
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: '#cbd5e1',
  },
  locateButtonText: {
    color: '#b91c1c',
    fontSize: 12,
    fontWeight: '700',
  },
  selectedCenter: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 12,
    marginBottom: 14,
    backgroundColor: '#fff',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#bbf7d0',
  },
  selectedCenterCopy: {
    flex: 1,
    paddingRight: 8,
  },
  selectedCenterName: {
    color: '#1f2937',
    fontWeight: '700',
    fontSize: 13,
  },
  directionsButton: {
    backgroundColor: '#15803d',
    paddingHorizontal: 12,
    paddingVertical: 9,
    borderRadius: 8,
  },
  directionsButtonText: {
    color: '#fff',
    fontSize: 12,
    fontWeight: '700',
  },
  actionRow: {
    flexDirection: 'row',
    marginBottom: 14,
  },
  actionButton: {
    flex: 1,
    backgroundColor: '#f3f4f6',
    borderRadius: 10,
    paddingVertical: 12,
    marginHorizontal: 4,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#e5e7eb',
  },
  actionButtonText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#1f2937',
  },
  routeActionRow: {
    flexDirection: 'row',
    marginBottom: 12,
  },
  routeChoiceButton: {
    flex: 1,
    minHeight: 52,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 8,
    marginHorizontal: 4,
    borderRadius: 10,
  },
  routeEvacuationButton: {
    backgroundColor: '#15803d',
  },
  routeHospitalButton: {
    backgroundColor: '#1d4ed8',
  },
  routeChoiceText: {
    color: '#fff',
    fontSize: 12,
    fontWeight: '700',
    textAlign: 'center',
  },
  primaryActionButton: {
    backgroundColor: '#ef4444',
    borderRadius: 10,
    paddingVertical: 14,
    alignItems: 'center',
    marginBottom: 16,
  },
  primaryActionButtonText: {
    color: '#fff',
    fontSize: 13,
    fontWeight: '700',
  },
  routeCard: {
    backgroundColor: '#fff',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#e5e7eb',
    padding: 12,
    marginBottom: 12,
  },
  routeTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#1f2937',
    marginBottom: 4,
  },
  routeText: {
    fontSize: 13,
    color: '#475569',
  },
  routeMeta: {
    fontSize: 12,
    color: '#6b7280',
    marginTop: 4,
  },
  responderCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#fff',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#e5e7eb',
    padding: 12,
    marginBottom: 16,
  },
  responderAvatar: {
    width: 46,
    height: 46,
    borderRadius: 23,
    backgroundColor: '#fde68a',
    justifyContent: 'center',
    alignItems: 'center',
  },
  responderIcon: {
    fontSize: 20,
  },
  responderInfo: {
    flex: 1,
    marginLeft: 12,
  },
  responderName: {
    fontSize: 14,
    fontWeight: '700',
    color: '#1f2937',
  },
  responderMeta: {
    fontSize: 12,
    color: '#6b7280',
    marginTop: 2,
  },
  callButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#fee2e2',
    justifyContent: 'center',
    alignItems: 'center',
  },
  callIcon: {
    fontSize: 18,
  },
  centerHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  centerHeaderText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#1f2937',
  },
  centerRefreshText: {
    fontSize: 11,
    color: '#6b7280',
  },
  centerCard: {
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: '#e5e7eb',
    borderRadius: 12,
    padding: 14,
    marginBottom: 10,
  },
  centerName: {
    fontSize: 13,
    fontWeight: '700',
    color: '#1f2937',
  },
  centerMeta: {
    fontSize: 12,
    color: '#6b7280',
    marginTop: 4,
  },
  emptyText: {
    fontSize: 13,
    color: '#6b7280',
    textAlign: 'center',
    marginTop: 10,
  },
  tabBar: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    flexDirection: 'row',
    backgroundColor: '#fff',
    borderTopWidth: 1,
    borderTopColor: '#e5e7eb',
    paddingBottom: Platform.OS === 'ios' ? 18 : 10,
    paddingTop: 8,
  },
  tabItem: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 8,
  },
  tabItemActive: {
    borderTopWidth: 2,
    borderTopColor: '#ef4444',
  },
  tabIcon: {
    fontSize: 22,
  },
  tabText: {
    fontSize: 10,
    color: '#6b7280',
    marginTop: 4,
  },
  tabTextActive: {
    color: '#ef4444',
    fontWeight: '700',
  },
  announcementCard: {
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: '#e5e7eb',
    borderRadius: 12,
    padding: 14,
    marginBottom: 12,
  },
  announcementBadge: {
    alignSelf: 'flex-start',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 999,
    marginBottom: 8,
  },
  announcementInfo: {
    backgroundColor: '#dbeafe',
  },
  announcementWarning: {
    backgroundColor: '#fef3c7',
  },
  announcementCritical: {
    backgroundColor: '#fee2e2',
  },
  errorText: {
    color: '#b91c1c',
    fontSize: 13,
    marginBottom: 12,
  },
  announcementBadgeText: {
    textTransform: 'uppercase',
    fontSize: 10,
    fontWeight: '700',
    color: '#1f2937',
  },
  announcementTitle: {
    color: '#111827',
    fontSize: 16,
    fontWeight: '700',
    marginBottom: 4,
  },
  announcementMessage: {
    color: '#374151',
    fontSize: 13,
    lineHeight: 20,
  },
  announcementMeta: {
    color: '#6b7280',
    fontSize: 11,
    marginTop: 8,
  },
  sheetOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.35)',
  },
  sheetCard: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: '#fff',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    paddingHorizontal: 22,
    paddingTop: 8,
    paddingBottom: 24,
  },
  hotlineModal: {
    flex: 1,
    justifyContent: 'flex-end',
  },
  hotlineBackdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0,0,0,0.4)',
  },
  hotlineSheet: {
    maxHeight: '86%',
    backgroundColor: '#fff',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    paddingHorizontal: 20,
    paddingTop: 10,
    paddingBottom: Platform.OS === 'ios' ? 26 : 16,
  },
  hotlineNote: {
    color: '#6b7280',
    fontSize: 12,
    marginBottom: 10,
  },
  hotlineList: {
    flexShrink: 1,
  },
  hotlineRow: {
    minHeight: 56,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 9,
    borderTopWidth: 1,
    borderTopColor: '#e5e7eb',
  },
  hotlineCopy: {
    flex: 1,
    paddingRight: 10,
  },
  hotlineAgency: {
    color: '#1f2937',
    fontSize: 12,
    fontWeight: '600',
  },
  hotlineNumber: {
    color: '#b91c1c',
    fontSize: 14,
    fontWeight: '700',
    marginTop: 2,
  },
  hotlineCall: {
    color: '#fff',
    backgroundColor: '#b91c1c',
    borderRadius: 7,
    paddingHorizontal: 14,
    paddingVertical: 8,
    overflow: 'hidden',
    fontSize: 12,
    fontWeight: '700',
  },
  hotlineSource: {
    color: '#6b7280',
    fontSize: 11,
    textAlign: 'center',
    marginTop: 10,
  },
  sheetHandle: {
    width: 40,
    height: 4,
    borderRadius: 2,
    backgroundColor: '#d1d5db',
    alignSelf: 'center',
    marginBottom: 18,
  },
  sheetTitleRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 20,
  },
  sheetTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#1f2937',
  },
  closeText: {
    fontSize: 22,
    color: '#6b7280',
  },
  chatOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.4)',
  },
  chatModal: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    height: '80%',
    backgroundColor: '#fff',
    borderTopLeftRadius: 22,
    borderTopRightRadius: 22,
    overflow: 'hidden',
  },
  chatHeader: {
    backgroundColor: '#ef4444',
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 18,
    paddingVertical: 14,
  },
  chatHeaderText: {
    color: '#fff',
    fontSize: 15,
    fontWeight: '700',
  },
  closeTextWhite: {
    color: '#fff',
    fontSize: 22,
  },
  quickRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    paddingHorizontal: 12,
    paddingTop: 12,
    paddingBottom: 6,
    backgroundColor: '#f8fafc',
    borderBottomWidth: 1,
    borderBottomColor: '#edf2f7',
  },
  quickChip: {
    backgroundColor: '#fee2e2',
    borderRadius: 16,
    paddingHorizontal: 10,
    paddingVertical: 8,
    marginRight: 6,
    marginBottom: 6,
  },
  quickChipText: {
    color: '#991b1b',
    fontSize: 11,
    fontWeight: '700',
  },
  chatBody: {
    flex: 1,
    backgroundColor: '#f8fafc',
    paddingHorizontal: 14,
  },
  chatBodyContent: {
    paddingVertical: 12,
  },
  chatBubble: {
    maxWidth: '85%',
    borderRadius: 14,
    paddingHorizontal: 12,
    paddingVertical: 10,
    marginBottom: 12,
  },
  botBubble: {
    backgroundColor: '#fff',
    alignSelf: 'flex-start',
    borderWidth: 1,
    borderColor: '#e5e7eb',
  },
  userBubble: {
    alignSelf: 'flex-end',
    backgroundColor: '#ef4444',
  },
  chatText: {
    color: '#1f2937',
    fontSize: 13,
    lineHeight: 18,
  },
  chatTextUser: {
    color: '#fff',
  },
  chatFooter: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#fff',
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderTopWidth: 1,
    borderTopColor: '#e5e7eb',
  },
  chatInput: {
    flex: 1,
    backgroundColor: '#f8fafc',
    borderWidth: 1,
    borderColor: '#e5e7eb',
    borderRadius: 20,
    paddingHorizontal: 14,
    paddingVertical: 10,
    fontSize: 13,
  },
  chatSendButton: {
    marginLeft: 10,
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: '#ef4444',
    justifyContent: 'center',
    alignItems: 'center',
  },
  chatSendText: {
    color: '#fff',
    fontSize: 18,
    fontWeight: '700',
  },
});