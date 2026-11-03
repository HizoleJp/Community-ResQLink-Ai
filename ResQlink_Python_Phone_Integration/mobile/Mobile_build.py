"""
Community ResQLink AI — Mobile (React Native / Expo) Builder
Run: python build_mobile.py
Creates: ./resqlink-ai/mobile/ fully populated.
"""
import os

ROOT = "resqlink-ai/mobile"

FILES = {}

# ============================================================
# CONFIG FILES
# ============================================================
FILES["package.json"] = '''{
  "name": "resqlink-mobile",
  "version": "1.0.0",
  "main": "node_modules/expo/AppEntry.js",
  "scripts": {
    "start": "expo start",
    "android": "expo start --android",
    "ios": "expo start --ios",
    "web": "expo start --web"
  },
  "dependencies": {
    "expo": "~51.0.0",
    "expo-location": "~17.0.1",
    "expo-image-picker": "~15.0.7",
    "expo-status-bar": "~1.12.1",
    "expo-linking": "~6.3.1",
    "react": "18.2.0",
    "react-native": "0.74.5",
    "react-native-maps": "1.14.0",
    "react-native-gesture-handler": "~2.16.1",
    "react-native-safe-area-context": "4.10.5",
    "react-native-screens": "3.31.1",
    "@react-native-async-storage/async-storage": "^1.23.1",
    "axios": "^1.7.7"
  },
  "devDependencies": {
    "@babel/core": "^7.24.0"
  },
  "private": true
}
'''

FILES["app.json"] = '''{
  "expo": {
    "name": "ResQLink AI",
    "slug": "resqlink-ai",
    "version": "1.0.0",
    "orientation": "portrait",
    "userInterfaceStyle": "light",
    "splash": {
      "resizeMode": "contain",
      "backgroundColor": "#ef4444"
    },
    "ios": {
      "supportsTablet": true,
      "infoPlist": {
        "NSLocationWhenInUseUsageDescription": "ResQLink needs your location to send emergency reports and find nearby evacuation centers.",
        "NSCameraUsageDescription": "ResQLink needs camera access to attach photos to emergency reports."
      }
    },
    "android": {
      "permissions": [
        "ACCESS_FINE_LOCATION",
        "ACCESS_COARSE_LOCATION",
        "CAMERA"
      ]
    },
    "plugins": [
      [
        "expo-location",
        {
          "locationAlwaysAndWhenInUsePermission": "Allow ResQLink to use your location."
        }
      ],
      [
        "expo-image-picker",
        {
          "photosPermission": "Allow ResQLink to attach photos."
        }
      ]
    ]
  }
}
'''

FILES["babel.config.js"] = '''module.exports = function (api) {
  api.cache(true);
  return {
    presets: ['babel-preset-expo'],
  };
};
'''

# ============================================================
# THEME
# ============================================================
FILES["src/theme.js"] = '''export const colors = {
  red: '#ef4444',
  redDark: '#dc2626',
  redLight: '#fee2e2',
  text: '#1f2937',
  muted: '#6b7280',
  bg: '#f8fafc',
  card: '#ffffff',
  border: '#e5e7eb',
  white: '#ffffff',
  black: '#000000',
  green: '#22c55e',
  amber: '#f59e0b',
  blue: '#3b82f6',
};

export const shadow = {
  shadowColor: '#000',
  shadowOffset: { width: 0, height: 2 },
  shadowOpacity: 0.08,
  shadowRadius: 6,
  elevation: 3,
};

export const shadowRed = {
  shadowColor: colors.red,
  shadowOffset: { width: 0, height: 6 },
  shadowOpacity: 0.35,
  shadowRadius: 12,
  elevation: 8,
};
'''

# ============================================================
# API CLIENT
# ============================================================
FILES["src/api/client.js"] = '''import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';

/**
 * Auto-detect the backend URL:
 *  - On a physical phone via Expo Go, uses the same IP as the Metro bundler (your PC).
 *  - Falls back to localhost for web / emulator.
 * The Python backend runs on port 8000.
 */
function getBaseUrl() {
  const hostUri = Constants.expoConfig?.hostUri || Constants.manifest?.debuggerHost;
  if (hostUri) {
    const host = hostUri.split(':')[0];
    return `http://${host}:8000`;
  }
  return 'http://localhost:8000';
}

export const BASE_URL = getBaseUrl();

const api = axios.create({ baseURL: BASE_URL, timeout: 20000 });

api.interceptors.request.use(async (config) => {
  const token = await AsyncStorage.getItem('resqlink_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export default api;
'''

# ============================================================
# AUTH CONTEXT
# ============================================================
FILES["src/context/AuthContext.js"] = '''import React, { createContext, useState, useEffect } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import api from '../api/client';

export const AuthContext = createContext();

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const token = await AsyncStorage.getItem('resqlink_token');
      const saved = await AsyncStorage.getItem('resqlink_user');
      if (token && saved) setUser({ token, ...JSON.parse(saved) });
      setLoading(false);
    })();
  }, []);

  const login = async (email, password) => {
    const body = new URLSearchParams();
    body.append('username', email);
    body.append('password', password);
    const { data } = await api.post('/users/login', body.toString(), {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
    await AsyncStorage.setItem('resqlink_token', data.access_token);
    const info = { email, name: email.split('@')[0] };
    await AsyncStorage.setItem('resqlink_user', JSON.stringify(info));
    setUser({ token: data.access_token, ...info });
    return data;
  };

  const register = async (full_name, email, password) => {
    await api.post('/users/register', { full_name, email, password });
    await login(email, password);
    const info = { email, name: full_name };
    await AsyncStorage.setItem('resqlink_user', JSON.stringify(info));
    setUser((u) => ({ ...u, ...info }));
  };

  const loginAsGuest = async () => {
    // Auto-register a unique guest account so backend accepts reports
    const email = `guest${Date.now()}@resqlink.local`;
    const password = 'guest1234';
    try {
      await api.post('/users/register', {
        full_name: 'Guest',
        email,
        password,
      });
    } catch (_) {}
    const body = new URLSearchParams();
    body.append('username', email);
    body.append('password', password);
    const { data } = await api.post('/users/login', body.toString(), {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
    await AsyncStorage.setItem('resqlink_token', data.access_token);
    const info = { email, name: 'Guest' };
    await AsyncStorage.setItem('resqlink_user', JSON.stringify(info));
    setUser({ token: data.access_token, ...info });
  };

  const logout = async () => {
    await AsyncStorage.removeItem('resqlink_token');
    await AsyncStorage.removeItem('resqlink_user');
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, loginAsGuest, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
'''

# ============================================================
# APP ENTRY
# ============================================================
FILES["App.js"] = '''import 'react-native-gesture-handler';
import React from 'react';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { AuthProvider, AuthContext } from './src/context/AuthContext';

import LoginScreen from './src/screens/LoginScreen';
import HomeScreen from './src/screens/HomeScreen';
import FireScreen from './src/screens/FireScreen';
import ResponderScreen from './src/screens/ResponderScreen';
import ReportScreen from './src/screens/ReportScreen';

/**
 * Extremely lightweight screen router so we don't need react-navigation.
 * Uses a simple state-based stack + a bottom tab bar rendered by MainTabs.
 */
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { colors } from './src/theme';

function MainTabs() {
  const [tab, setTab] = React.useState('home');

  const screens = {
    home: <HomeScreen goTab={setTab} />,
    fire: <FireScreen goTab={setTab} />,
    report: <ReportScreen />,
    responder: <ResponderScreen />,
  };

  return (
    <View style={{ flex: 1 }}>
      <View style={{ flex: 1 }}>{screens[tab]}</View>
      <View style={styles.tabbar}>
        {[
          { key: 'home', label: 'Emergency', icon: '🆘' },
          { key: 'fire', label: 'Fire', icon: '🔥' },
          { key: 'report', label: 'Report', icon: '⚠️' },
          { key: 'responder', label: 'Rescue', icon: '🚒' },
        ].map((t) => (
          <TouchableOpacity
            key={t.key}
            style={styles.tab}
            onPress={() => setTab(t.key)}
          >
            <Text style={{ fontSize: 20 }}>{t.icon}</Text>
            <Text style={[styles.tabLabel, tab === t.key && { color: colors.red, fontWeight: '700' }]}>
              {t.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );
}

function Root() {
  const { user, loading } = React.useContext(AuthContext);
  if (loading) return null;
  return user ? <MainTabs /> : <LoginScreen />;
}

export default function App() {
  return (
    <SafeAreaProvider>
      <AuthProvider>
        <StatusBar style="light" />
        <Root />
      </AuthProvider>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  tabbar: {
    flexDirection: 'row',
    height: 68,
    backgroundColor: colors.white,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingBottom: 8,
    paddingTop: 8,
  },
  tab: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  tabLabel: { fontSize: 10, color: colors.muted, marginTop: 2, fontWeight: '500' },
});
'''

# ============================================================
# SCREENS
# ============================================================
FILES["src/screens/LoginScreen.js"] = '''import React, { useContext, useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  KeyboardAvoidingView, Platform, Alert, ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { AuthContext } from '../context/AuthContext';
import { colors, shadowRed } from '../theme';

export default function LoginScreen() {
  const { login, register, loginAsGuest } = useContext(AuthContext);
  const [mode, setMode] = useState('login');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!email || !password) return Alert.alert('Missing info', 'Enter email and password');
    if (mode === 'register' && !name) return Alert.alert('Missing info', 'Enter your name');
    setBusy(true);
    try {
      if (mode === 'register') await register(name, email, password);
      else await login(email, password);
    } catch (e) {
      Alert.alert('Error', e?.response?.data?.detail || e.message || 'Login failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.white }}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={{ flex: 1 }}
      >
        <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
          <View style={styles.logoWrap}>
            <View style={styles.logoCircle}>
              <Text style={{ fontSize: 42 }}>🔥</Text>
            </View>
            <Text style={styles.title}>ResQLink AI</Text>
            <Text style={styles.subtitle}>Emergency help at your fingertips</Text>
          </View>

          {mode === 'register' && (
            <View style={styles.field}>
              <Text style={styles.label}>Full name</Text>
              <TextInput
                style={styles.input}
                placeholder="Juan Dela Cruz"
                value={name}
                onChangeText={setName}
              />
            </View>
          )}

          <View style={styles.field}>
            <Text style={styles.label}>Email</Text>
            <TextInput
              style={styles.input}
              placeholder="juan@example.com"
              autoCapitalize="none"
              keyboardType="email-address"
              value={email}
              onChangeText={setEmail}
            />
          </View>

          <View style={styles.field}>
            <Text style={styles.label}>Password</Text>
            <TextInput
              style={styles.input}
              placeholder="••••••••"
              secureTextEntry
              value={password}
              onChangeText={setPassword}
            />
          </View>

          <TouchableOpacity style={styles.primaryBtn} onPress={submit} disabled={busy}>
            <Text style={styles.primaryBtnText}>
              {busy ? 'Please wait…' : mode === 'login' ? 'Log in' : 'Create account'}
            </Text>
          </TouchableOpacity>

          <View style={styles.toggleRow}>
            <Text style={{ color: colors.muted, fontSize: 13 }}>
              {mode === 'login' ? 'No account? ' : 'Have an account? '}
            </Text>
            <TouchableOpacity onPress={() => setMode(mode === 'login' ? 'register' : 'login')}>
              <Text style={{ color: colors.red, fontWeight: '700', fontSize: 13 }}>
                {mode === 'login' ? 'Register' : 'Log in'}
              </Text>
            </TouchableOpacity>
          </View>

          <Text style={styles.or}>or</Text>

          <TouchableOpacity onPress={loginAsGuest}>
            <Text style={{ color: colors.red, fontWeight: '700', textAlign: 'center', fontSize: 14 }}>
              Continue as guest
            </Text>
          </TouchableOpacity>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { padding: 26, paddingTop: 40 },
  logoWrap: { alignItems: 'center', marginBottom: 34 },
  logoCircle: {
    width: 92, height: 92, borderRadius: 46,
    backgroundColor: colors.red,
    alignItems: 'center', justifyContent: 'center',
    marginBottom: 18,
    ...shadowRed,
  },
  title: { fontSize: 24, fontWeight: '700', color: colors.text, marginBottom: 6 },
  subtitle: { fontSize: 13, color: colors.muted },
  field: { marginBottom: 16 },
  label: { fontSize: 13, color: colors.text, fontWeight: '500', marginBottom: 8 },
  input: {
    borderWidth: 1, borderColor: colors.border, borderRadius: 10,
    paddingVertical: 12, paddingHorizontal: 14, fontSize: 14,
    color: colors.text, backgroundColor: colors.white,
  },
  primaryBtn: {
    backgroundColor: colors.red, padding: 15, borderRadius: 10,
    alignItems: 'center', marginTop: 6,
  },
  primaryBtnText: { color: '#fff', fontSize: 15, fontWeight: '700' },
  toggleRow: { flexDirection: 'row', justifyContent: 'center', marginTop: 16 },
  or: { textAlign: 'center', color: colors.muted, marginTop: 22, marginBottom: 12, fontSize: 12 },
});
'''

FILES["src/screens/HomeScreen.js"] = '''import React, { useEffect, useState, useContext } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, ScrollView, Alert, Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as Location from 'expo-location';
import api from '../api/client';
import { AuthContext } from '../context/AuthContext';
import { colors } from '../theme';

const TILES = [
  { key: 'share',     icon: '📍', label: 'Share Location' },
  { key: 'track',     icon: '🚗', label: 'Track Me' },
  { key: 'hospital',  icon: '🚑', label: 'Nearest Hospital' },
  { key: 'police',    icon: '🚓', label: 'Nearest Police Station' },
  { key: 'call',      icon: '📞', label: 'Emergency Call' },
  { key: 'sound',     icon: '🚨', label: 'Emergency Sound' },
];

export default function HomeScreen({ goTab }) {
  const { logout, user } = useContext(AuthContext);
  const [loc, setLoc] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const { status } = await Location.requestForegroundPermissionsAsync();
        if (status === 'granted') {
          const pos = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.High });
          setLoc({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        }
      } catch (e) {
        console.warn('Location error', e);
      }
    })();
  }, []);

  const onPress = async (key) => {
    if (key === 'share') {
      if (!loc) return Alert.alert('Getting GPS…');
      Alert.alert('Your location', `${loc.lat.toFixed(5)}, ${loc.lng.toFixed(5)}`);
    } else if (key === 'track') {
      goTab('responder');
    } else if (key === 'hospital' || key === 'police') {
      if (!loc) return Alert.alert('Getting GPS…');
      try {
        const { data } = await api.get(
          `/services/nearby?amenity=${key}&lat=${loc.lat}&lon=${loc.lng}`
        );
        if (!data.results?.length) return Alert.alert(`No ${key} found within 5 km`);
        Alert.alert(
          `Nearest ${key}`,
          data.results
            .slice(0, 3)
            .map((r) => `• ${r.name}`)
            .join('\\n')
        );
      } catch (e) {
        Alert.alert('Error', 'Backend offline or search failed');
      }
    } else if (key === 'call') {
      Linking.openURL('tel:911');
    } else if (key === 'sound') {
      Alert.alert('🔊 Emergency sound', 'This would play a loud siren alert.');
    }
  };

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Emergency Help</Text>
        <TouchableOpacity onPress={logout}>
          <Text style={{ color: '#fff', fontSize: 13 }}>Log out</Text>
        </TouchableOpacity>
      </View>

      <ScrollView contentContainerStyle={{ padding: 20, paddingBottom: 30 }}>
        <Text style={styles.subhead}>Be Ready with Emergency Preparedness</Text>

        <View style={styles.grid}>
          {TILES.map((t) => (
            <TouchableOpacity key={t.key} style={styles.tile} onPress={() => onPress(t.key)}>
              <View style={styles.circle}>
                <Text style={{ fontSize: 36 }}>{t.icon}</Text>
              </View>
              <Text style={styles.tileLabel}>{t.label}</Text>
            </TouchableOpacity>
          ))}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.white },
  header: {
    backgroundColor: colors.red,
    paddingHorizontal: 18,
    paddingVertical: 14,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  headerTitle: { color: '#fff', fontSize: 17, fontWeight: '700' },
  subhead: {
    textAlign: 'center', color: colors.muted, fontSize: 13,
    marginBottom: 22, marginTop: 4,
  },
  grid: {
    flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between',
  },
  tile: { width: '48%', alignItems: 'center', marginBottom: 26 },
  circle: {
    width: 96, height: 96, borderRadius: 48,
    backgroundColor: '#fff',
    borderWidth: 1.5, borderColor: colors.border,
    alignItems: 'center', justifyContent: 'center',
    marginBottom: 10,
  },
  tileLabel: { fontSize: 13, color: colors.text, textAlign: 'center', fontWeight: '500' },
});
'''

FILES["src/screens/FireScreen.js"] = '''import React, { useEffect, useState, useContext } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as Location from 'expo-location';
import ReportSheet from './ReportSheet';
import { AuthContext } from '../context/AuthContext';
import { colors, shadowRed } from '../theme';

export default function FireScreen({ goTab }) {
  const { user } = useContext(AuthContext);
  const [locLabel, setLocLabel] = useState('Locating…');
  const [coords, setCoords] = useState(null);
  const [sheetOpen, setSheetOpen] = useState(false);

  useEffect(() => {
    (async () => {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') return setLocLabel('Location denied');
      const pos = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.High });
      const { latitude, longitude, accuracy } = pos.coords;
      setCoords({ lat: latitude, lng: longitude });
      setLocLabel(`±${accuracy.toFixed(0)} m · ${latitude.toFixed(4)}, ${longitude.toFixed(4)}`);
    })();
  }, []);

  const initials = (user?.name || 'U')
    .split(' ').map((w) => w[0]).slice(0, 2).join('').toUpperCase();

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.top}>
        <Text style={styles.locText}>📍 {locLabel}</Text>
        <View style={styles.avatar}>
          <Text style={{ color: '#fff', fontWeight: '700', fontSize: 13 }}>{initials}</Text>
        </View>
      </View>

      <Text style={styles.title}>Need emergency fire{'\n'}service?</Text>

      <View style={{ alignItems: 'center', flex: 1, justifyContent: 'center' }}>
        <View style={styles.ring}>
          <TouchableOpacity style={styles.fireBtn} onPress={() => setSheetOpen(true)}>
            <Text style={{ fontSize: 52 }}>🔥</Text>
            <Text style={styles.fireBtnLabel}>Report fire</Text>
          </TouchableOpacity>
        </View>

        <Text style={styles.or}>or</Text>
        <TouchableOpacity onPress={() => Alert.alert('Call 911?', '', [
          { text: 'Cancel' },
          { text: 'Call', onPress: () => {} },
        ])}>
          <Text style={styles.callText}>Emergency call</Text>
        </TouchableOpacity>
      </View>

      <ReportSheet
        visible={sheetOpen}
        onClose={() => setSheetOpen(false)}
        coords={coords}
        onSent={() => {
          setSheetOpen(false);
          goTab('responder');
        }}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.white, paddingHorizontal: 20 },
  top: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingTop: 8, paddingBottom: 20,
  },
  locText: { color: colors.text, fontSize: 13, fontWeight: '500', flex: 1 },
  avatar: {
    width: 34, height: 34, borderRadius: 17,
    backgroundColor: colors.amber,
    alignItems: 'center', justifyContent: 'center',
  },
  title: {
    fontSize: 26, fontWeight: '700', color: colors.text,
    textAlign: 'center', marginTop: 8, marginBottom: 30, lineHeight: 34,
  },
  ring: {
    width: 220, height: 220, borderRadius: 110,
    borderWidth: 2, borderColor: colors.redLight,
    alignItems: 'center', justifyContent: 'center',
    marginBottom: 20,
  },
  fireBtn: {
    width: 180, height: 180, borderRadius: 90,
    backgroundColor: colors.red,
    alignItems: 'center', justifyContent: 'center',
    ...shadowRed,
  },
  fireBtnLabel: { color: '#fff', fontSize: 15, fontWeight: '700', marginTop: 4 },
  or: { color: colors.muted, fontSize: 12, marginBottom: 12 },
  callText: { color: colors.red, fontSize: 14, fontWeight: '700' },
});
'''

FILES["src/screens/ReportSheet.js"] = '''import React, { useState, useContext } from 'react';
import {
  Modal, View, Text, TextInput, TouchableOpacity, StyleSheet,
  Alert, ScrollView, Platform, ActivityIndicator,
} from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import api from '../api/client';
import { AuthContext } from '../context/AuthContext';
import { colors } from '../theme';

export default function ReportSheet({ visible, onClose, coords, onSent }) {
  const { user, loginAsGuest } = useContext(AuthContext);
  const [casualties, setCasualties] = useState('no');
  const [description, setDescription] = useState('');
  const [photo, setPhoto] = useState(null);
  const [sending, setSending] = useState(false);
  const [aiResult, setAiResult] = useState(null);

  const pickPhoto = async () => {
    const perm = await ImagePicker.requestCameraPermissionsAsync();
    if (perm.status !== 'granted') return Alert.alert('Camera permission needed');
    const res = await ImagePicker.launchCameraAsync({ quality: 0.5 });
    if (!res.canceled) setPhoto(res.assets[0].uri);
  };

  const send = async () => {
    if (!description.trim()) return Alert.alert('Please describe the emergency');
    if (!coords) return Alert.alert('Waiting for GPS…');
    setSending(true);
    try {
      if (!user) await loginAsGuest();
      const { data } = await api.post('/reports/', {
        description,
        latitude: coords.lat,
        longitude: coords.lng,
        image_url: photo,
      });
      setAiResult(data);
      setTimeout(() => {
        onSent?.();
        setAiResult(null);
        setDescription('');
        setPhoto(null);
      }, 1500);
    } catch (e) {
      Alert.alert('Error', 'Backend offline or report failed');
    } finally {
      setSending(false);
    }
  };

  const casualtyOptions = ['no', 'yes', 'unknown'];

  return (
    <Modal
      visible={visible}
      animationType="slide"
      transparent
      onRequestClose={onClose}
    >
      <View style={styles.overlay}>
        <TouchableOpacity style={{ flex: 1 }} activeOpacity={1} onPress={onClose} />
        <View style={styles.sheet}>
          <View style={styles.handle} />
          <View style={styles.headerRow}>
            <Text style={styles.title}>Send report</Text>
            <TouchableOpacity onPress={onClose}>
              <Text style={{ fontSize: 22, color: colors.muted }}>✕</Text>
            </TouchableOpacity>
          </View>

          <ScrollView showsVerticalScrollIndicator={false}>
            <Text style={styles.label}>Any casualties</Text>
            <View style={styles.segment}>
              {casualtyOptions.map((opt) => (
                <TouchableOpacity
                  key={opt}
                  style={[styles.segmentItem, casualties === opt && styles.segmentActive]}
                  onPress={() => setCasualties(opt)}
                >
                  <Text
                    style={[
                      styles.segmentText,
                      casualties === opt && { color: '#fff', fontWeight: '700' },
                    ]}
                  >
                    {opt}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            <Text style={styles.label}>Location</Text>
            <View style={styles.locBox}>
              <Text style={{ fontSize: 13, color: colors.text, flex: 1 }}>
                {coords ? `${coords.lat.toFixed(5)}, ${coords.lng.toFixed(5)}` : 'Auto-detect'}
              </Text>
              <Text style={{ color: colors.red }}>📍</Text>
            </View>

            <Text style={styles.label}>
              Upload photo <Text style={{ color: colors.muted }}>(optional)</Text>
            </Text>
            <TouchableOpacity style={styles.uploadBox} onPress={pickPhoto}>
              <Text style={{ fontSize: 24, color: colors.red }}>⬆️</Text>
              <Text style={{ color: colors.red, fontSize: 12, marginTop: 4, fontWeight: '600' }}>
                {photo ? 'Photo attached ✓' : 'Upload photo'}
              </Text>
            </TouchableOpacity>

            <Text style={styles.label}>Description</Text>
            <TextInput
              style={[styles.input, { height: 90, textAlignVertical: 'top' }]}
              multiline
              placeholder="e.g. Big fire near Molino Market, people trapped"
              value={description}
              onChangeText={setDescription}
            />

            {aiResult && (
              <View style={styles.aiBox}>
                <Text style={styles.aiText}>
                  ✅ Sent to server{'\n'}
                  AI: <Text style={{ fontWeight: '700' }}>{aiResult.category.toUpperCase()}</Text>{'\n'}
                  Severity: <Text style={{ fontWeight: '700' }}>{aiResult.severity}</Text>{'\n'}
                  Confidence: {aiResult.ai_confidence}
                </Text>
              </View>
            )}

            <TouchableOpacity
              style={[styles.sendBtn, sending && { opacity: 0.7 }]}
              onPress={send}
              disabled={sending}
            >
              {sending ? (
                <ActivityIndicator color="#fff" />
              ) : (
                <Text style={styles.sendText}>Send report</Text>
              )}
            </TouchableOpacity>

            <View style={{ height: 24 }} />
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.35)', justifyContent: 'flex-end' },
  sheet: {
    backgroundColor: '#fff',
    borderTopLeftRadius: 22, borderTopRightRadius: 22,
    paddingHorizontal: 22, paddingTop: 8, paddingBottom: 10,
    maxHeight: '90%',
  },
  handle: {
    width: 40, height: 4, borderRadius: 2, backgroundColor: '#d1d5db',
    alignSelf: 'center', marginBottom: 16,
  },
  headerRow: {
    flexDirection: 'row', justifyContent: 'space-between',
    alignItems: 'center', marginBottom: 20,
  },
  title: { fontSize: 20, fontWeight: '700', color: colors.text },
  label: { fontSize: 13, color: colors.text, fontWeight: '500', marginBottom: 8, marginTop: 8 },
  segment: {
    flexDirection: 'row', borderWidth: 1, borderColor: colors.border,
    borderRadius: 10, overflow: 'hidden', marginBottom: 8,
  },
  segmentItem: { flex: 1, paddingVertical: 10, alignItems: 'center', backgroundColor: '#fff' },
  segmentActive: { backgroundColor: colors.red },
  segmentText: { fontSize: 13, color: colors.text, textTransform: 'capitalize' },
  locBox: {
    flexDirection: 'row', alignItems: 'center',
    borderWidth: 1, borderColor: colors.border,
    borderRadius: 10, padding: 12, marginBottom: 8,
  },
  uploadBox: {
    borderWidth: 1.5, borderColor: colors.border, borderStyle: 'dashed',
    borderRadius: 10, paddingVertical: 20, alignItems: 'center', marginBottom: 8,
  },
  input: {
    borderWidth: 1, borderColor: colors.border, borderRadius: 10,
    padding: 12, fontSize: 14, color: colors.text, backgroundColor: '#fff',
  },
  aiBox: {
    backgroundColor: colors.redLight, borderLeftWidth: 4,
    borderLeftColor: colors.red, borderRadius: 10,
    padding: 14, marginTop: 14,
  },
  aiText: { color: colors.text, fontSize: 13, lineHeight: 20 },
  sendBtn: {
    backgroundColor: colors.red, padding: 15, borderRadius: 10,
    alignItems: 'center', marginTop: 16,
  },
  sendText: { color: '#fff', fontSize: 15, fontWeight: '700' },
});
'''

FILES["src/screens/ResponderScreen.js"] = '''import React, { useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, ScrollView, Alert, Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import MapView, { Marker, Polyline, Circle } from 'react-native-maps';
import * as Location from 'expo-location';
import api from '../api/client';
import { colors } from '../theme';

export default function ResponderScreen() {
  const [user, setUser] = useState(null);
  const [centers, setCenters] = useState([]);
  const [routes, setRoutes] = useState([]);
  const [loadingRoutes, setLoadingRoutes] = useState(false);

  useEffect(() => {
    (async () => {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') return;
      const pos = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.High });
      setUser({ lat: pos.coords.latitude, lng: pos.coords.longitude });
      loadCenters();
    })();
  }, []);

  const loadCenters = async () => {
    try {
      const { data } = await api.get('/evacuation/centers');
      setCenters(data);
    } catch (e) {
      console.warn('centers load failed', e);
    }
  };

  const findSafeRoute = async () => {
    if (!user) return Alert.alert('Waiting for GPS…');
    setLoadingRoutes(true);
    try {
      const { data } = await api.get(
        `/evacuation/plan?lat=${user.lat}&lon=${user.lng}`
      );
      setRoutes(data.routes || []);
    } catch (e) {
      Alert.alert('Error', 'Could not fetch routes. Backend offline?');
    } finally {
      setLoadingRoutes(false);
    }
  };

  const region = user
    ? {
        latitude: user.lat,
        longitude: user.lng,
        latitudeDelta: 0.05,
        longitudeDelta: 0.05,
      }
    : {
        latitude: 14.4591,
        longitude: 120.9490,
        latitudeDelta: 0.1,
        longitudeDelta: 0.1,
      };

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Fire service team is on the way</Text>
        <Text style={styles.headerSub}>Arriving in ~5 minutes</Text>
      </View>

      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 40 }}>
        <View style={styles.mapWrap}>
          <MapView style={styles.map} region={region} showsUserLocation>
            {user && (
              <>
                <Marker coordinate={{ latitude: user.lat, longitude: user.lng }}
                        title="You are here" pinColor={colors.red} />
                <Circle
                  center={{ latitude: user.lat, longitude: user.lng }}
                  radius={50}
                  fillColor="rgba(239,68,68,0.12)"
                  strokeColor="rgba(239,68,68,0.6)"
                />
              </>
            )}
            {centers.map((c) => (
              <Marker
                key={c.id}
                coordinate={{ latitude: c.latitude, longitude: c.longitude }}
                title={c.name}
                description={`Capacity: ${c.capacity - c.occupancy} free`}
                pinColor="blue"
              />
            ))}
            {routes.map((r, i) =>
              user ? (
                <Polyline
                  key={r.center_id}
                  coordinates={[
                    { latitude: user.lat, longitude: user.lng },
                    { latitude: r.latitude, longitude: r.longitude },
                  ]}
                  strokeColor={i === 0 ? colors.green : i === 1 ? colors.amber : colors.blue}
                  strokeWidth={i === 0 ? 5 : 3}
                  lineDashPattern={[10, 6]}
                />
              ) : null
            )}
          </MapView>
        </View>

        <TouchableOpacity
          style={[styles.findBtn, loadingRoutes && { opacity: 0.7 }]}
          onPress={findSafeRoute}
          disabled={loadingRoutes}
        >
          <Text style={styles.findText}>
            {loadingRoutes ? 'AI computing…' : '🧭 Find Safe Route (AI Evacuation)'}
          </Text>
        </TouchableOpacity>

        {routes.length > 0 && (
          <View>
            <Text style={styles.sectionTitle}>🧭 AI-Ranked Safe Routes</Text>
            {routes.map((r, i) => (
              <View
                key={r.center_id}
                style={[
                  styles.card,
                  { borderLeftColor: i === 0 ? colors.green : i === 1 ? colors.amber : colors.blue, borderLeftWidth: 4 },
                ]}
              >
                <Text style={styles.cardName}>
                  {i === 0 ? '⭐ ' : ''}{r.name}
                </Text>
                <Text style={styles.cardMeta}>
                  {r.distance_km} km · safety {r.safe_distance_km} · {r.capacity_left} free
                  {r.penalty > 1 ? ` · ⚠️ hazard ×${r.penalty}` : ''}
                </Text>
              </View>
            ))}
          </View>
        )}

        <View style={styles.responder}>
          <View style={styles.pic}><Text style={{ fontSize: 22 }}>👨‍🚒</Text></View>
          <View style={{ flex: 1 }}>
            <Text style={{ fontWeight: '700', fontSize: 14 }}>Robert William</Text>
            <Text style={{ fontSize: 12, color: colors.muted }}>Fireman · En route</Text>
          </View>
          <TouchableOpacity
            style={styles.callBtn}
            onPress={() => Linking.openURL('tel:911')}
          >
            <Text style={{ color: colors.red, fontSize: 18 }}>📞</Text>
          </TouchableOpacity>
        </View>

        <Text style={styles.sectionTitle}>Nearby Evacuation Centers</Text>
        {centers.map((c) => (
          <View key={c.id} style={styles.card}>
            <Text style={styles.cardName}>{c.name}</Text>
            <Text style={styles.cardMeta}>
              Capacity: {c.capacity - c.occupancy} free · {c.latitude.toFixed(4)}, {c.longitude.toFixed(4)}
            </Text>
          </View>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  header: {
    backgroundColor: colors.red, padding: 20,
    borderBottomLeftRadius: 18, borderBottomRightRadius: 18,
  },
  headerTitle: { color: '#fff', fontSize: 18, fontWeight: '700', marginBottom: 4 },
  headerSub: { color: '#fff', fontSize: 12, opacity: 0.9 },
  mapWrap: {
    borderRadius: 14, overflow: 'hidden', marginBottom: 14,
    backgroundColor: '#fff',
  },
  map: { width: '100%', height: 320 },
  findBtn: {
    backgroundColor: colors.red, padding: 15, borderRadius: 10,
    alignItems: 'center', marginBottom: 14,
  },
  findText: { color: '#fff', fontSize: 15, fontWeight: '700' },
  sectionTitle: {
    fontSize: 14, fontWeight: '700', color: colors.text,
    marginTop: 10, marginBottom: 10,
  },
  card: {
    backgroundColor: '#fff', borderRadius: 12, padding: 14,
    marginBottom: 10, borderWidth: 1, borderColor: colors.border,
  },
  cardName: { fontSize: 14, fontWeight: '600', color: colors.text },
  cardMeta: { fontSize: 12, color: colors.muted, marginTop: 4 },
  responder: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    backgroundColor: '#fff', borderRadius: 14, padding: 14,
    marginVertical: 14, borderWidth: 1, borderColor: colors.border,
  },
  pic: {
    width: 46, height: 46, borderRadius: 23,
    backgroundColor: '#fde68a',
    alignItems: 'center', justifyContent: 'center',
  },
  callBtn: {
    width: 40, height: 40, borderRadius: 20,
    backgroundColor: colors.redLight,
    alignItems: 'center', justifyContent: 'center',
  },
});
'''

FILES["src/screens/ReportScreen.js"] = '''import React, { useState, useEffect, useContext } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  Alert, ScrollView, ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as Location from 'expo-location';
import api from '../api/client';
import { AuthContext } from '../context/AuthContext';
import { colors } from '../theme';

export default function ReportScreen() {
  const { user, loginAsGuest } = useContext(AuthContext);
  const [coords, setCoords] = useState(null);
  const [text, setText] = useState('');
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    (async () => {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') return;
      const pos = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.High });
      setCoords({ lat: pos.coords.latitude, lng: pos.coords.longitude });
    })();
  }, []);

  const submit = async () => {
    if (!text.trim()) return Alert.alert('Please describe the emergency');
    if (!coords) return Alert.alert('Waiting for GPS…');
    setBusy(true);
    try {
      if (!user) await loginAsGuest();
      const { data } = await api.post('/reports/', {
        description: text,
        latitude: coords.lat,
        longitude: coords.lng,
      });
      setResult(data);
      setText('');
    } catch (e) {
      Alert.alert('Error', 'Could not send. Is the backend running?');
    } finally {
      setBusy(false);
    }
  };

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={{ padding: 20 }}>
        <Text style={styles.title}>Report an incident</Text>
        <Text style={styles.subtitle}>
          {coords
            ? `📍 ${coords.lat.toFixed(5)}, ${coords.lng.toFixed(5)}`
            : 'Locating…'}
        </Text>

        <Text style={styles.label}>Describe the emergency</Text>
        <TextInput
          style={[styles.input, { height: 130, textAlignVertical: 'top' }]}
          multiline
          placeholder="e.g. Big fire near Molino Market, people trapped"
          value={text}
          onChangeText={setText}
        />

        <TouchableOpacity
          style={[styles.btn, busy && { opacity: 0.7 }]}
          onPress={submit}
          disabled={busy}
        >
          {busy ? <ActivityIndicator color="#fff" /> : <Text style={styles.btnText}>Submit report</Text>}
        </TouchableOpacity>

        {result && (
          <View style={styles.aiBox}>
            <Text style={styles.aiText}>
              ✅ Report submitted{'\n'}
              AI: <Text style={{ fontWeight: '700' }}>{result.category.toUpperCase()}</Text>{'\n'}
              Severity: <Text style={{ fontWeight: '700' }}>{result.severity}</Text>{'\n'}
              Confidence: {result.ai_confidence}
            </Text>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.white },
  title: { fontSize: 20, fontWeight: '700', color: colors.text, marginBottom: 6 },
  subtitle: { fontSize: 13, color: colors.muted, marginBottom: 20 },
  label: { fontSize: 13, fontWeight: '500', color: colors.text, marginBottom: 8 },
  input: {
    borderWidth: 1, borderColor: colors.border, borderRadius: 10,
    padding: 12, fontSize: 14, color: colors.text, marginBottom: 16,
  },
  btn: {
    backgroundColor: colors.red, padding: 15, borderRadius: 10,
    alignItems: 'center',
  },
  btnText: { color: '#fff', fontSize: 15, fontWeight: '700' },
  aiBox: {
    backgroundColor: colors.redLight, borderLeftWidth: 4,
    borderLeftColor: colors.red, borderRadius: 10,
    padding: 14, marginTop: 18,
  },
  aiText: { color: colors.text, fontSize: 13, lineHeight: 20 },
});
'''