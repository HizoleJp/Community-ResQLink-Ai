"""
Community ResQLink AI — Project Bootstrap
Run:  python bootstrap.py
Then: code resqlink-ai
"""
import os
import textwrap

ROOT = "resqlink-ai"

FILES = {}

# ============================================================
# BACKEND FILES
# ============================================================
FILES["backend/requirements.txt"] = """
fastapi==0.115.0
uvicorn[standard]==0.32.0
sqlalchemy==2.0.35
pydantic==2.9.2
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.12
scikit-learn==1.5.2
joblib==1.4.2
numpy==2.1.1
networkx==3.4.1
geopy==2.4.1
email-validator==2.2.0
"""

FILES["backend/.env"] = """
SECRET_KEY=change-me-in-production
DATABASE_URL=sqlite:///./resqlink.db
"""

FILES["backend/database.py"] = '''
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "sqlite:///./resqlink.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
'''

FILES["backend/models.py"] = '''
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="citizen")
    created_at = Column(DateTime, default=datetime.utcnow)
    reports = relationship("Report", back_populates="owner")

class Report(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    category = Column(String)
    description = Column(Text)
    latitude = Column(Float)
    longitude = Column(Float)
    severity = Column(String)
    ai_confidence = Column(Float)
    status = Column(String, default="pending")
    image_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    owner = relationship("User", back_populates="reports")

class EvacuationCenter(Base):
    __tablename__ = "evacuation_centers"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    capacity = Column(Integer, default=0)
    occupancy = Column(Integer, default=0)
    contact = Column(String, nullable=True)
    is_open = Column(Boolean, default=True)

class ServiceRequest(Base):
    __tablename__ = "service_requests"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    service_type = Column(String)
    details = Column(Text)
    latitude = Column(Float)
    longitude = Column(Float)
    status = Column(String, default="open")
    created_at = Column(DateTime, default=datetime.utcnow)
'''

FILES["backend/schemas.py"] = '''
from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional

class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    role: str
    class Config: from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class ReportCreate(BaseModel):
    description: str
    latitude: float
    longitude: float
    image_url: Optional[str] = None

class ReportOut(BaseModel):
    id: int
    category: str
    description: str
    latitude: float
    longitude: float
    severity: str
    ai_confidence: float
    status: str
    created_at: datetime
    class Config: from_attributes = True

class EvacOut(BaseModel):
    id: int
    name: str
    latitude: float
    longitude: float
    capacity: int
    occupancy: int
    is_open: bool
    class Config: from_attributes = True

class ServiceCreate(BaseModel):
    service_type: str
    details: str
    latitude: float
    longitude: float
'''

FILES["backend/auth.py"] = '''
from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from database import get_db
from models import User

SECRET_KEY = "CHANGE_ME_IN_PRODUCTION"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/login")

def hash_password(p): return pwd_context.hash(p)
def verify_password(p, h): return pwd_context.verify(p, h)

def create_token(data: dict):
    to_encode = data.copy()
    to_encode["exp"] = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user
'''

FILES["backend/main.py"] = '''
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import Base, engine
from routers import users, reports, evacuation, services

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Community ResQLink AI", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)
app.include_router(reports.router)
app.include_router(evacuation.router)
app.include_router(services.router)

@app.get("/")
def root(): return {"status": "ok", "service": "ResQLink AI"}
'''

FILES["backend/seed.py"] = '''
"""Run once to populate evacuation centers in Bacoor, Cavite."""
from database import SessionLocal, Base, engine
from models import EvacuationCenter

Base.metadata.create_all(bind=engine)
db = SessionLocal()

SAMPLE = [
    {"name": "Bacoor City Hall Evac Center", "latitude": 14.4591, "longitude": 120.9490, "capacity": 500, "occupancy": 120},
    {"name": "Molino Elementary School",     "latitude": 14.4141, "longitude": 120.9780, "capacity": 300, "occupancy": 45},
    {"name": "St. Dominic College",          "latitude": 14.4426, "longitude": 120.9647, "capacity": 250, "occupancy": 60},
    {"name": "Bacoor National High School",  "latitude": 14.4508, "longitude": 120.9523, "capacity": 400, "occupancy": 80},
]

for s in SAMPLE:
    if not db.query(EvacuationCenter).filter(EvacuationCenter.name == s["name"]).first():
        db.add(EvacuationCenter(**s))

db.commit()
print(f"✅ Seeded {len(SAMPLE)} evacuation centers.")
'''

FILES["backend/routers/__init__.py"] = ""

FILES["backend/routers/users.py"] = '''
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from database import get_db
from models import User
from schemas import UserCreate, UserOut, Token
from auth import hash_password, verify_password, create_token

router = APIRouter(prefix="/users", tags=["users"])

@router.post("/register", response_model=UserOut)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(400, "Email already registered")
    user = User(full_name=payload.full_name, email=payload.email,
                hashed_password=hash_password(payload.password))
    db.add(user); db.commit(); db.refresh(user)
    return user

@router.post("/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form.username).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(401, "Invalid credentials")
    return {"access_token": create_token({"sub": user.email})}
'''

FILES["backend/routers/reports.py"] = '''
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from database import get_db
from models import Report, User
from schemas import ReportCreate, ReportOut
from auth import current_user
from ai.classifier import classify, severity

router = APIRouter(prefix="/reports", tags=["reports"])

@router.post("/", response_model=ReportOut)
def create_report(payload: ReportCreate,
                  db: Session = Depends(get_db),
                  user: User = Depends(current_user)):
    category, conf = classify(payload.description)
    sev = severity(payload.description)
    report = Report(
        user_id=user.id,
        description=payload.description,
        latitude=payload.latitude, longitude=payload.longitude,
        image_url=payload.image_url,
        category=category, severity=sev, ai_confidence=conf,
    )
    db.add(report); db.commit(); db.refresh(report)
    return report

@router.get("/", response_model=List[ReportOut])
def list_reports(status: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(Report)
    if status: q = q.filter(Report.status == status)
    return q.order_by(Report.created_at.desc()).all()

@router.patch("/{report_id}/verify")
def verify_report(report_id: int, db: Session = Depends(get_db),
                  user: User = Depends(current_user)):
    if user.role not in ("responder", "admin"):
        raise HTTPException(403, "Responders only")
    r = db.query(Report).get(report_id)
    if not r: raise HTTPException(404)
    r.status = "verified"; db.commit()
    return {"ok": True}
'''

FILES["backend/routers/evacuation.py"] = '''
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models import EvacuationCenter, Report
from schemas import EvacOut
from ai.router import plan_evacuation

router = APIRouter(prefix="/evacuation", tags=["evacuation"])

@router.get("/centers", response_model=List[EvacOut])
def centers(db: Session = Depends(get_db)):
    return db.query(EvacuationCenter).filter(EvacuationCenter.is_open == True).all()

@router.get("/plan")
def plan(lat: float = Query(...), lon: float = Query(...),
         db: Session = Depends(get_db)):
    centers = db.query(EvacuationCenter).all()
    reports = db.query(Report).filter(Report.status != "resolved").all()
    return {"routes": plan_evacuation(lat, lon, centers, reports)}
'''

FILES["backend/routers/services.py"] = '''
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import ServiceRequest, User
from schemas import ServiceCreate
from auth import current_user

router = APIRouter(prefix="/services", tags=["services"])

@router.post("/")
def create_service(payload: ServiceCreate,
                   db: Session = Depends(get_db),
                   user: User = Depends(current_user)):
    s = ServiceRequest(user_id=user.id, **payload.model_dump())
    db.add(s); db.commit(); db.refresh(s)
    return {"id": s.id, "status": s.status}

@router.get("/")
def list_services(db: Session = Depends(get_db)):
    return db.query(ServiceRequest).order_by(ServiceRequest.created_at.desc()).all()
'''

FILES["backend/ai/__init__.py"] = ""

FILES["backend/ai/classifier.py"] = '''
"""Lightweight NLP classifier for disaster reports. TF-IDF + LinearSVC."""
import os, joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.pipeline import Pipeline

MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "classifier.pkl")

TRAINING_DATA = [
    ("There is a big fire near the market", "fire"),
    ("Smoke coming from a house", "fire"),
    ("Flood waters rising on our street", "flood"),
    ("Knee-deep flood in the barangay", "flood"),
    ("Strong earthquake shook the buildings", "earthquake"),
    ("Ground shaking and cracks appeared", "earthquake"),
    ("Someone is injured and needs an ambulance", "medical"),
    ("Person collapsed and unresponsive", "medical"),
    ("Tree fell and blocked the road", "infrastructure"),
    ("Bridge collapsed after the storm", "infrastructure"),
    ("We need food and water supplies", "supply"),
    ("No electricity and water for 3 days", "supply"),
]

SEVERITY_KEYWORDS = {
    "critical": ["death", "dying", "trapped", "unconscious", "massive", "explosion"],
    "high":     ["injured", "rising fast", "big fire", "collapsed", "urgent"],
    "medium":   ["flood", "smoke", "blocked", "damage"],
    "low":      ["minor", "small", "slight"],
}

def train():
    X, y = zip(*TRAINING_DATA)
    pipe = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), lowercase=True)),
        ("clf", LinearSVC()),
    ])
    pipe.fit(X, y)
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    joblib.dump(pipe, MODEL_PATH)
    return pipe

def _load():
    if not os.path.exists(MODEL_PATH):
        return train()
    return joblib.load(MODEL_PATH)

_model = _load()

def classify(text: str):
    category = _model.predict([text])[0]
    scores = _model.decision_function([text])[0]
    conf = float(1 / (1 + abs(scores).min()))
    return category, round(conf, 3)

def severity(text: str) -> str:
    t = text.lower()
    for level in ("critical", "high", "medium", "low"):
        if any(k in t for k in SEVERITY_KEYWORDS[level]):
            return level
    return "medium"
'''

FILES["backend/ai/router.py"] = '''
"""Adaptive evacuation routing with A* over a hazard-weighted graph."""
import math, networkx as nx
from geopy.distance import geodesic

def haversine(a, b):
    return geodesic(a, b).km

def build_graph(nodes):
    G = nx.Graph()
    for n in nodes:
        G.add_node(n["id"], lat=n["lat"], lon=n["lon"], kind=n["kind"])
    for i, a in enumerate(nodes):
        for b in nodes[i+1:]:
            d = haversine((a["lat"], a["lon"]), (b["lat"], b["lon"]))
            G.add_edge(a["id"], b["id"], weight=d)
    return G

def nearest_node(G, lat, lon):
    best, best_d = None, math.inf
    for n, data in G.nodes(data=True):
        d = haversine((lat, lon), (data["lat"], data["lon"]))
        if d < best_d:
            best, best_d = n, d
    return best

def plan_evacuation(user_lat, user_lon, centers, reports, blocked_radius_km=0.5):
    nodes = [{"id": "user", "lat": user_lat, "lon": user_lon, "kind": "user"}]
    for c in centers:
        nodes.append({"id": f"c{c.id}", "lat": c.latitude, "lon": c.longitude, "kind": "center"})
    for r in reports:
        nodes.append({"id": f"r{r.id}", "lat": r.latitude, "lon": r.longitude, "kind": "hazard"})

    G = build_graph(nodes)

    hazards = [(r.latitude, r.longitude, r.severity) for r in reports]
    for u, v, data in G.edges(data=True):
        mid = ((G.nodes[u]["lat"]+G.nodes[v]["lat"])/2,
               (G.nodes[u]["lon"]+G.nodes[v]["lon"])/2)
        for h_lat, h_lon, sev in hazards:
            d = haversine(mid, (h_lat, h_lon))
            if d < blocked_radius_km:
                data["weight"] *= {"critical": 10, "high": 5, "medium": 2}.get(sev, 1)

    results = []
    for c in centers:
        if not c.is_open: continue
        try:
            path = nx.astar_path(G, "user", f"c{c.id}", weight="weight")
            dist = nx.astar_path_length(G, "user", f"c{c.id}", weight="weight")
            results.append({
                "center_id": c.id, "name": c.name,
                "distance_km": round(dist, 2),
                "path": path,
                "capacity_left": c.capacity - c.occupancy,
            })
        except nx.NetworkXNoPath:
            continue

    results.sort(key=lambda x: (x["distance_km"], -x["capacity_left"]))
    return results
'''

# ============================================================
# MOBILE FILES
# ============================================================
FILES["mobile/package.json"] = '''
{
  "name": "resqlink-mobile",
  "version": "1.0.0",
  "main": "node_modules/expo/AppEntry.js",
  "scripts": {
    "start": "expo start",
    "android": "expo start --android",
    "ios": "expo start --ios"
  },
  "dependencies": {
    "expo": "~51.0.0",
    "expo-location": "~17.0.1",
    "expo-image-picker": "~15.0.7",
    "expo-status-bar": "~1.12.1",
    "react": "18.2.0",
    "react-native": "0.74.5",
    "react-native-maps": "1.14.0",
    "@react-navigation/native": "^6.1.18",
    "@react-navigation/native-stack": "^6.11.0",
    "@react-navigation/bottom-tabs": "^6.6.1",
    "react-native-screens": "3.31.1",
    "react-native-safe-area-context": "4.10.5",
    "react-native-gesture-handler": "~2.16.1",
    "@react-native-async-storage/async-storage": "^1.23.1",
    "axios": "^1.7.7"
  }
}
'''

FILES["mobile/app.json"] = '''
{
  "expo": {
    "name": "ResQLink AI",
    "slug": "resqlink-ai",
    "version": "1.0.0",
    "orientation": "portrait",
    "userInterfaceStyle": "light",
    "splash": { "resizeMode": "contain", "backgroundColor": "#1e40af" },
    "ios": { "supportsTablet": true },
    "android": { "permissions": ["ACCESS_FINE_LOCATION", "ACCESS_COARSE_LOCATION"] }
  }
}
'''

FILES["mobile/App.js"] = '''
import 'react-native-gesture-handler';
import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { AuthProvider } from './src/context/AuthContext';
import HomeScreen from './src/screens/HomeScreen';
import ReportScreen from './src/screens/ReportScreen';
import MapScreen from './src/screens/MapScreen';
import ServicesScreen from './src/screens/ServicesScreen';

const Tab = createBottomTabNavigator();

export default function App() {
  return (
    <AuthProvider>
      <NavigationContainer>
        <Tab.Navigator screenOptions={{ headerShown: false }}>
          <Tab.Screen name="Home"     component={HomeScreen} />
          <Tab.Screen name="Report"   component={ReportScreen} />
          <Tab.Screen name="Map"      component={MapScreen} />
          <Tab.Screen name="Services" component={ServicesScreen} />
        </Tab.Navigator>
      </NavigationContainer>
    </AuthProvider>
  );
}
'''

FILES["mobile/src/api/client.js"] = '''
import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

// Replace with your LAN IP when running on a physical device
export const BASE_URL = 'http://192.168.1.10:8000';

const api = axios.create({ baseURL: BASE_URL });

api.interceptors.request.use(async (config) => {
  const token = await AsyncStorage.getItem('token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export default api;
'''

FILES["mobile/src/context/AuthContext.js"] = '''
import React, { createContext, useState, useEffect } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import api from '../api/client';

export const AuthContext = createContext();

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const token = await AsyncStorage.getItem('token');
      if (token) setUser({ token });
      setLoading(false);
    })();
  }, []);

  const login = async (email, password) => {
    const form = new URLSearchParams();
    form.append('username', email);
    form.append('password', password);
    const { data } = await api.post('/users/login', form, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
    await AsyncStorage.setItem('token', data.access_token);
    setUser({ token: data.access_token });
  };

  const register = async (full_name, email, password) => {
    await api.post('/users/register', { full_name, email, password });
    await login(email, password);
  };

  const logout = async () => {
    await AsyncStorage.removeItem('token');
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
'''

FILES["mobile/src/screens/HomeScreen.js"] = '''
import React, { useContext, useState } from 'react';
import { View, Text, TextInput, Button, StyleSheet, Alert } from 'react-native';
import { AuthContext } from '../context/AuthContext';

export default function HomeScreen() {
  const { user, login, register, logout } = useContext(AuthContext);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [isRegistering, setIsRegistering] = useState(false);

  if (user) {
    return (
      <View style={styles.container}>
        <Text style={styles.title}>Welcome to ResQLink AI</Text>
        <Button title="Log out" onPress={logout} />
      </View>
    );
  }

  const submit = async () => {
    try {
      if (isRegistering) await register(name, email, password);
      else await login(email, password);
    } catch (e) {
      Alert.alert('Error', e.response?.data?.detail || e.message);
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>{isRegistering ? 'Register' : 'Log in'}</Text>
      {isRegistering && (
        <TextInput style={styles.input} placeholder="Full name" value={name} onChangeText={setName} />
      )}
      <TextInput style={styles.input} placeholder="Email" autoCapitalize="none"
                 keyboardType="email-address" value={email} onChangeText={setEmail} />
      <TextInput style={styles.input} placeholder="Password" secureTextEntry
                 value={password} onChangeText={setPassword} />
      <Button title={isRegistering ? 'Create account' : 'Log in'} onPress={submit} />
      <Text style={styles.toggle} onPress={() => setIsRegistering(!isRegistering)}>
        {isRegistering ? 'Already have an account? Log in' : "Don't have an account? Register"}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 24, justifyContent: 'center' },
  title: { fontSize: 26, fontWeight: 'bold', marginBottom: 20, textAlign: 'center' },
  input: { borderWidth: 1, borderColor: '#ccc', borderRadius: 8, padding: 12, marginBottom: 12 },
  toggle: { textAlign: 'center', marginTop: 16, color: '#1e40af' },
});
'''

FILES["mobile/src/screens/ReportScreen.js"] = '''
import React, { useState } from 'react';
import { View, Text, TextInput, Button, Alert, StyleSheet } from 'react-native';
import * as Location from 'expo-location';
import api from '../api/client';

export default function ReportScreen() {
  const [description, setDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const submit = async () => {
    if (!description.trim()) return Alert.alert('Please describe the incident');
    setSubmitting(true);
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') throw new Error('Location permission denied');
      const loc = await Location.getCurrentPositionAsync({});

      const { data } = await api.post('/reports/', {
        description,
        latitude: loc.coords.latitude,
        longitude: loc.coords.longitude,
      });

      Alert.alert(
        'Report submitted',
        `AI classified this as: ${data.category.toUpperCase()}\\n` +
        `Severity: ${data.severity}\\nConfidence: ${data.ai_confidence}`
      );
      setDescription('');
    } catch (e) {
      Alert.alert('Error', e.response?.data?.detail || e.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Report an Incident</Text>
      <TextInput
        style={styles.input}
        multiline
        placeholder="Describe what is happening..."
        value={description}
        onChangeText={setDescription}
      />
      <Button title={submitting ? 'Sending...' : 'Submit Report'} onPress={submit} disabled={submitting} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 20, backgroundColor: '#fff' },
  title: { fontSize: 22, fontWeight: 'bold', marginBottom: 16 },
  input: {
    borderWidth: 1, borderColor: '#ccc', borderRadius: 8,
    padding: 12, minHeight: 120, textAlignVertical: 'top', marginBottom: 16,
  },
});
'''

FILES["mobile/src/screens/MapScreen.js"] = '''
import React, { useEffect, useState } from 'react';
import { View, StyleSheet } from 'react-native';
import MapView, { Marker } from 'react-native-maps';
import * as Location from 'expo-location';
import api from '../api/client';

const SEVERITY_COLOR = {
  critical: '#7f1d1d', high: '#dc2626',
  medium: '#f59e0b', low: '#10b981',
};

export default function MapScreen() {
  const [region, setRegion] = useState(null);
  const [reports, setReports] = useState([]);
  const [centers, setCenters] = useState([]);

  useEffect(() => {
    (async () => {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status === 'granted') {
        const loc = await Location.getCurrentPositionAsync({});
        setRegion({
          latitude: loc.coords.latitude,
          longitude: loc.coords.longitude,
          latitudeDelta: 0.05,
          longitudeDelta: 0.05,
        });
      }
      try {
        const [r, c] = await Promise.all([
          api.get('/reports/'), api.get('/evacuation/centers'),
        ]);
        setReports(r.data); setCenters(c.data);
      } catch {}
    })();
  }, []);

  if (!region) return <View style={styles.container} />;

  return (
    <MapView style={styles.map} region={region} showsUserLocation>
      {reports.map((r) => (
        <Marker
          key={`r${r.id}`}
          coordinate={{ latitude: r.latitude, longitude: r.longitude }}
          title={r.category.toUpperCase()}
          description={`${r.severity} — ${r.description}`}
          pinColor={SEVERITY_COLOR[r.severity] || 'orange'}
        />
      ))}
      {centers.map((c) => (
        <Marker
          key={`c${c.id}`}
          coordinate={{ latitude: c.latitude, longitude: c.longitude }}
          title={`Evac: ${c.name}`}
          description={`Capacity left: ${c.capacity - c.occupancy}`}
          pinColor="blue"
        />
      ))}
    </MapView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  map: { flex: 1 },
});
'''

FILES["mobile/src/screens/ServicesScreen.js"] = '''
import React from 'react';
import { View, Text, TouchableOpacity, Alert, StyleSheet } from 'react-native';
import * as Location from 'expo-location';
import api from '../api/client';

const SERVICES = [
  { key: 'rescue',  label: '🚨 Rescue' },
  { key: 'medical', label: '🚑 Medical' },
  { key: 'food',    label: '🍞 Food' },
  { key: 'water',   label: '💧 Water' },
];

export default function ServicesScreen() {
  const request = async (type) => {
    try {
      const loc = await Location.getCurrentPositionAsync({});
      await api.post('/services/', {
        service_type: type,
        details: `Request for ${type}`,
        latitude: loc.coords.latitude,
        longitude: loc.coords.longitude,
      });
      Alert.alert('Request sent', `Your ${type} request has been submitted.`);
    } catch (e) { Alert.alert('Error', e.message); }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Request Assistance</Text>
      {SERVICES.map((s) => (
        <TouchableOpacity key={s.key} style={styles.btn} onPress={() => request(s.key)}>
          <Text style={styles.btnText}>{s.label}</Text>
        </TouchableOpacity>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 20 },
  title: { fontSize: 22, fontWeight: 'bold', marginBottom: 20 },
  btn: {
    backgroundColor: '#1e40af', padding: 18, borderRadius: 10,
    marginBottom: 12, alignItems: 'center',
  },
  btnText: { color: '#fff', fontSize: 18, fontWeight: '600' },
});
'''

# ============================================================
# DOCS + GIT
# ============================================================
FILES["README.md"] = '''
# Community ResQLink AI

AI-powered mobile app for real-time disaster reporting, adaptive evacuation, and public service assistance in **Bacoor, Cavite, Philippines**.

## Stack
- **Backend**: FastAPI + SQLAlchemy + SQLite
- **AI**: scikit-learn (NLP classifier) + NetworkX A* (evacuation routing)
- **Mobile**: React Native (Expo)

## Quick Start

### Backend
```bash
cd backend
python -m venv venv
# Windows: venv\\\\Scripts\\\\activate
# Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
python seed.py
uvicorn main:app --reload --host 0.0.0.0 --port 8000
'''