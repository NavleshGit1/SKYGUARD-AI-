import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import Header from './components/Header';
import LiveTicker from './components/LiveTicker';
import ToastContainer from './components/ToastContainer';
import KPICards from './components/KPICards';
import LiveMap from './components/LiveMap';
import TelemetryChart from './components/TelemetryChart';
import AlertFeed from './components/AlertFeed';
import SimulatorPanel from './components/SimulatorPanel';
import AuthModal from './components/AuthModal';
import SensorHealthLeaderboard from './components/SensorHealthLeaderboard';
import ModelBenchmarkScreen from './components/ModelBenchmarkScreen';
import AdminSettings from './components/AdminSettings';
import { LanguageProvider, LanguageToggle } from './i18n';
import { sounds } from './utils/audio';

const DEFAULT_STATIONS = [
  {
    station_id: "AWS-DEL-01",
    name: "New Delhi Safdarjung",
    state: "Delhi",
    latitude: 28.5847,
    longitude: 77.2069,
    altitude_m: 216.0,
    health_score: 98.4,
    health_status: "HEALTHY",
    latest_reading: {
      temperature_c: 32.4,
      pressure_hpa: 1002.5,
      humidity_pct: 64.0,
      dew_point_c: 24.8,
      is_anomaly: false,
      timestamp: new Date().toISOString()
    }
  },
  {
    station_id: "AWS-MUM-01",
    name: "Mumbai Santacruz",
    state: "Maharashtra",
    latitude: 19.0760,
    longitude: 72.8777,
    altitude_m: 14.0,
    health_score: 96.1,
    health_status: "HEALTHY",
    latest_reading: {
      temperature_c: 29.8,
      pressure_hpa: 1004.1,
      humidity_pct: 78.0,
      dew_point_c: 25.6,
      is_anomaly: false,
      timestamp: new Date().toISOString()
    }
  },
  {
    station_id: "AWS-KOL-01",
    name: "Kolkata Alipore",
    state: "West Bengal",
    latitude: 22.5726,
    longitude: 88.3639,
    altitude_m: 9.0,
    health_score: 99.0,
    health_status: "HEALTHY",
    latest_reading: {
      temperature_c: 31.2,
      pressure_hpa: 1001.8,
      humidity_pct: 72.0,
      dew_point_c: 25.5,
      is_anomaly: false,
      timestamp: new Date().toISOString()
    }
  },
  {
    station_id: "AWS-CHE-01",
    name: "Chennai Meenambakkam",
    state: "Tamil Nadu",
    latitude: 13.0827,
    longitude: 80.2707,
    altitude_m: 16.0,
    health_score: 94.7,
    health_status: "HEALTHY",
    latest_reading: {
      temperature_c: 33.6,
      pressure_hpa: 1003.4,
      humidity_pct: 60.0,
      dew_point_c: 24.6,
      is_anomaly: false,
      timestamp: new Date().toISOString()
    }
  },
  {
    station_id: "AWS-JAI-01",
    name: "Jaipur Sanganer",
    state: "Rajasthan",
    latitude: 26.9124,
    longitude: 75.7873,
    altitude_m: 390.0,
    health_score: 97.5,
    health_status: "HEALTHY",
    latest_reading: {
      temperature_c: 35.0,
      pressure_hpa: 1000.2,
      humidity_pct: 48.0,
      dew_point_c: 22.3,
      is_anomaly: false,
      timestamp: new Date().toISOString()
    }
  }
];

// Generate initial baseline telemetry readings
const DEFAULT_READINGS = Array.from({ length: 20 }).map((_, i) => {
  const t = new Date(Date.now() - (19 - i) * 60000);
  const baseT = 31.5 + Math.sin(i / 3) * 1.8;
  return {
    id: i,
    timestamp: t.toISOString(),
    temperature_c: parseFloat(baseT.toFixed(1)),
    imputed_temperature_c: parseFloat(baseT.toFixed(1)),
    pressure_hpa: parseFloat((1002.5 + Math.cos(i / 4) * 0.8).toFixed(1)),
    imputed_pressure_hpa: parseFloat((1002.5 + Math.cos(i / 4) * 0.8).toFixed(1)),
    humidity_pct: parseFloat((65.0 - Math.sin(i / 3) * 4.0).toFixed(1)),
    imputed_humidity_pct: parseFloat((65.0 - Math.sin(i / 3) * 4.0).toFixed(1)),
    dew_point_c: 24.5,
    sea_level_pressure_hpa: 1004.2,
    is_anomaly: false,
    severity_score: 0.0,
    is_imputed: false
  };
});

function getApiBaseUrl() {
  let raw = (import.meta.env.VITE_API_URL || '').trim();
  if (!raw) return '';
  if (!raw.startsWith('http://') && !raw.startsWith('https://')) {
    raw = `https://${raw}`;
  }
  return raw.replace(/\/+$/, '');
}

const API_BASE_URL = getApiBaseUrl();
if (API_BASE_URL) {
  axios.defaults.baseURL = API_BASE_URL;
}

export default function App() {
  const [stations, setStations] = useState(DEFAULT_STATIONS);
  const [selectedStation, setSelectedStation] = useState(DEFAULT_STATIONS[0]);
  const selectedStationRef = useRef(DEFAULT_STATIONS[0]);
  
  const [readings, setReadings] = useState(DEFAULT_READINGS);
  const [anomalies, setAnomalies] = useState([]);
  // overview | telemetry | alerts | health | benchmark | simulator | admin
  const [activeTab, setActiveTab] = useState('overview');

  // Floating Toast Notifications Queue
  const [toasts, setToasts] = useState([]);
  const [toastEnabled, setToastEnabled] = useState(() => localStorage.getItem('skyguard_toast_enabled') === 'true');
  const lastToastTimeRef = useRef({});

  const [token, setToken] = useState(() => localStorage.getItem('skyguard_token'));
  
  // Real-Time WebSocket state
  const [isWsConnected, setIsWsConnected] = useState(false);
  const wsRef = useRef(null);

  // User state
  const [user, setUser] = useState(null);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);

  useEffect(() => {
    selectedStationRef.current = selectedStation;
  }, [selectedStation]);

  const handleToggleToast = () => {
    const nextVal = !toastEnabled;
    setToastEnabled(nextVal);
    localStorage.setItem('skyguard_toast_enabled', String(nextVal));
    if (nextVal) {
      sounds.playSuccessChime();
    }
  };

  // 1. Initial Data Fetching from Live API
  const fetchInitialData = async () => {
    try {
      const [stRes, anomRes] = await Promise.all([
        axios.get('/api/v1/stations'),
        axios.get('/api/v1/anomalies?limit=50')
      ]);
      if (Array.isArray(stRes.data) && stRes.data.length > 0) {
        setStations(stRes.data);
        if (!selectedStationRef.current) {
          setSelectedStation(stRes.data[0]);
          fetchStationTelemetry(stRes.data[0].station_id);
        }
      }
      if (Array.isArray(anomRes.data)) {
        setAnomalies(anomRes.data);
      }
    } catch (err) {
      // Graceful fallback to initial default stations when API is offline/cold-starting
      console.warn('API connecting note:', err.message);
    }
  };

  const fetchStationTelemetry = async (stationId) => {
    try {
      const res = await axios.get(`/api/v1/stations/${stationId}`);
      if (res.data?.recent_readings && Array.isArray(res.data.recent_readings) && res.data.recent_readings.length > 0) {
        setReadings(res.data.recent_readings);
      }
    } catch (err) {
      console.warn(`Telemetry sync note for ${stationId}:`, err.message);
    }
  };

  useEffect(() => {
    fetchInitialData();
    // Safety poll every 8s
    const pollInterval = setInterval(() => {
      axios.get('/api/v1/stations').then(res => {
        if (Array.isArray(res.data) && res.data.length > 0) setStations(res.data);
      }).catch(() => {});
      axios.get('/api/v1/anomalies?limit=50').then(res => {
        if (Array.isArray(res.data)) setAnomalies(res.data);
      }).catch(() => {});
      if (selectedStationRef.current) {
        fetchStationTelemetry(selectedStationRef.current.station_id);
      }
    }, 8000);
    return () => clearInterval(pollInterval);
  }, []);

  // 2. Select Station Change
  const handleSelectStation = (st, shouldSwitchTab = false) => {
    setSelectedStation(st);
    fetchStationTelemetry(st.station_id);
    if (shouldSwitchTab) {
      setActiveTab('telemetry');
    }
  };

  // 3. WebSocket Real-Time Stream
  useEffect(() => {
    let reconnectTimer = null;
    let isMounted = true;

    const connectWs = () => {
      if (!isMounted) return;
      const rawToken = localStorage.getItem('skyguard_token');
      const isValidToken = rawToken && rawToken !== 'undefined' && rawToken !== 'null' && rawToken.length > 20;
      const tokenParam = isValidToken ? `?token=${encodeURIComponent(rawToken)}` : '';
      
      let wsUrl = '';
      if (API_BASE_URL) {
        const cleanWs = API_BASE_URL.replace(/^http:/, 'ws:').replace(/^https:/, 'wss:');
        wsUrl = `${cleanWs}/api/v1/ws/live-feed${tokenParam}`;
      } else {
        const hostname = window.location.hostname || 'localhost';
        const isLocalVite = window.location.port === '5173';
        const portStr = isLocalVite ? ':8000' : (window.location.port ? `:${window.location.port}` : '');
        const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        wsUrl = `${wsProto}//${hostname}${portStr}/api/v1/ws/live-feed${tokenParam}`;
      }
      
      try {
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          if (isMounted) setIsWsConnected(true);
        };

        ws.onerror = () => {
          if (isMounted) setIsWsConnected(false);
        };

        ws.onclose = () => {
          if (isMounted) {
            setIsWsConnected(false);
            reconnectTimer = setTimeout(connectWs, 6000);
          }
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === 'TELEMETRY_INGESTED') {
              const currentSelectedId = selectedStationRef.current?.station_id;
              
              // 1. Update Telemetry curve if this matches currently viewed station
              if (data.station_id === currentSelectedId) {
                setReadings((prev) => [
                  {
                    id: Date.now(),
                    timestamp: data.timestamp,
                    temperature_c: data.reading?.temperature_c,
                    pressure_hpa: data.reading?.pressure_hpa,
                    humidity_pct: data.reading?.humidity_pct,
                    dew_point_c: data.reading?.dew_point_c,
                    sea_level_pressure_hpa: data.reading?.sea_level_pressure_hpa,
                    is_anomaly: data.is_anomaly,
                    severity_score: data.severity_score,
                    is_imputed: data.imputed?.is_imputed || false,
                    imputed_temperature_c: data.imputed?.temperature_c || null,
                    imputed_pressure_hpa: data.imputed?.pressure_hpa || null,
                    imputed_humidity_pct: data.imputed?.humidity_pct || null
                  },
                  ...prev.slice(0, 49)
                ]);
              }

              // 2. Update Station Health in List & Map
              setStations((prev) =>
                prev.map((s) =>
                  s.station_id === data.station_id
                    ? {
                        ...s,
                        health_score: data.health_score,
                        health_status: data.health_status,
                        latest_reading: {
                          temperature_c: data.reading?.temperature_c,
                          pressure_hpa: data.reading?.pressure_hpa,
                          humidity_pct: data.reading?.humidity_pct,
                          is_anomaly: data.is_anomaly,
                          timestamp: data.timestamp
                        }
                      }
                    : s
                )
              );

              // 3. Prepend to Anomaly Feed if flagged
              if (data.is_anomaly && data.anomaly_event) {
                setAnomalies((prev) => [data.anomaly_event, ...prev.slice(0, 99)]);
                
                // Audio Chime & Throttled Toast
                sounds.playAlarm();
                
                const now = Date.now();
                const lastTime = lastToastTimeRef.current[data.station_id] || 0;
                if (now - lastTime > 15000) {
                  lastToastTimeRef.current[data.station_id] = now;
                  const newToast = {
                    id: `${data.anomaly_event.event_id || Date.now()}`,
                    title: `Anomaly Detected: ${data.station_id}`,
                    message: data.anomaly_event.explanation || 'Sensor reading breached physical normal threshold.',
                    severity: data.anomaly_event.severity_score >= 0.75 ? 'HIGH' : 'MEDIUM',
                    timestamp: new Date().toLocaleTimeString(),
                    alert: data.anomaly_event
                  };
                  setToasts((prev) => [newToast, ...prev.slice(0, 4)]);
                }
              }
            }
          } catch (err) {
            console.error('Error handling WebSocket message:', err);
          }
        };
      } catch (e) {
        console.warn('WS Init note:', e.message);
      }
    };

    connectWs();

    return () => {
      isMounted = false;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  const handleDismissToast = (id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  const handleSelectToast = (alert) => {
    setActiveTab('alerts');
  };

  return (
    <LanguageProvider>
      <div className="min-h-screen bg-[var(--bg-app)] text-slate-100 flex flex-col font-sans select-none antialiased">
        {/* 1. Global Navigation Bar */}
        <Header
          activeTab={activeTab}
          onTabChange={setActiveTab}
          user={user}
          onOpenLogin={() => setIsAuthModalOpen(true)}
          onLogout={() => {
            setUser(null);
            setToken(null);
            localStorage.removeItem('skyguard_token');
          }}
          isWsConnected={isWsConnected}
          toastEnabled={toastEnabled}
          onToggleToast={handleToggleToast}
        />

        {/* 2. Scrolling Telemetry Ticker Marquee */}
        <LiveTicker stations={stations} onSelectStation={handleSelectStation} />

        {/* 3. Main Dashboard Workspace */}
        <main className="flex-1 max-w-[1720px] w-full mx-auto p-3 sm:p-5 lg:p-6 space-y-6">
          {/* OVERVIEW TAB */}
          {activeTab === 'overview' && (
            <div className="space-y-6">
              {/* Top Row: KPI Cards */}
              <KPICards stations={stations} anomalies={anomalies} />

              {/* Middle Row: GIS Radar Map + Telemetry Chart */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                <div className="lg:col-span-6 xl:col-span-5">
                  <LiveMap
                    stations={stations}
                    selectedStation={selectedStation}
                    onSelectStation={handleSelectStation}
                  />
                </div>
                <div className="lg:col-span-6 xl:col-span-7">
                  <TelemetryChart
                    stations={stations}
                    selectedStation={selectedStation}
                    onSelectStation={handleSelectStation}
                    readings={readings}
                  />
                </div>
              </div>

              {/* Bottom Row: Incident Feed */}
              <AlertFeed
                anomalies={anomalies}
                onResolveSuccess={fetchInitialData}
                onSelectStation={handleSelectStation}
              />
            </div>
          )}

          {/* TELEMETRY DEEP DIVE TAB */}
          {activeTab === 'telemetry' && (
            <div className="space-y-6">
              <TelemetryChart
                stations={stations}
                selectedStation={selectedStation}
                onSelectStation={handleSelectStation}
                readings={readings}
              />
              <SensorHealthLeaderboard
                stations={stations}
                selectedStation={selectedStation}
                onSelectStation={handleSelectStation}
              />
            </div>
          )}

          {/* ALERTS & INCIDENTS TAB */}
          {activeTab === 'alerts' && (
            <AlertFeed
              anomalies={anomalies}
              onResolveSuccess={fetchInitialData}
              onSelectStation={handleSelectStation}
            />
          )}

          {/* HEALTH LEADERBOARD TAB */}
          {activeTab === 'health' && (
            <SensorHealthLeaderboard
              stations={stations}
              selectedStation={selectedStation}
              onSelectStation={handleSelectStation}
            />
          )}

          {/* AI BENCHMARKS TAB */}
          {activeTab === 'benchmark' && <ModelBenchmarkScreen />}

          {/* FAULT INJECTION SIMULATOR TAB */}
          {activeTab === 'simulator' && (
            <SimulatorPanel
              stations={stations}
              onInjectionSuccess={() => {
                fetchInitialData();
                sounds.playSuccessChime();
              }}
            />
          )}

          {/* SYSTEM SETTINGS TAB */}
          {activeTab === 'admin' && (
            <AdminSettings onRefreshData={fetchInitialData} />
          )}
        </main>

        {/* 4. Floating Toast Notification Hub */}
        {toastEnabled && (
          <ToastContainer
            toasts={toasts}
            onDismiss={handleDismissToast}
            onSelectAlert={handleSelectToast}
          />
        )}

        {/* 5. Operator Login Modal */}
        <AuthModal
          isOpen={isAuthModalOpen}
          onClose={() => setIsAuthModalOpen(false)}
          onLoginSuccess={(userData, userToken) => {
            setUser(userData);
            setToken(userToken);
            localStorage.setItem('skyguard_token', userToken);
            setIsAuthModalOpen(false);
            sounds.playSuccessChime();
          }}
        />
      </div>
    </LanguageProvider>
  );
}
