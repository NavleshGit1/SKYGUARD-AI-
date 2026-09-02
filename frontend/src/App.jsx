import React, { useState, useEffect, useRef } from 'react';
import api, { getWebSocketUrl } from './utils/api';
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

export default function App() {
  const [stations, setStations] = useState([]);
  const [selectedStation, setSelectedStation] = useState(null);
  const selectedStationRef = useRef(null);
  
  const [readings, setReadings] = useState([]);
  const [anomalies, setAnomalies] = useState([]);
  // overview | telemetry | alerts | health | benchmark | simulator | admin
  const [activeTab, setActiveTab] = useState('overview');

  // Floating Toast Notifications Queue (Default MUTED to prevent annoying continuous popups)
  const [toasts, setToasts] = useState([]);
  const [toastEnabled, setToastEnabled] = useState(() => localStorage.getItem('skyguard_toast_enabled') === 'true');
  const lastToastTimeRef = useRef({});

  // VULN-11 NOTE: For production, migrate to HttpOnly cookie storage.
  // localStorage is readable by JavaScript — susceptible to XSS exfiltration.
  // Recommended: POST /auth/login sets Set-Cookie: session=<token>; HttpOnly; Secure; SameSite=Strict
  const [token, setToken] = useState(() => localStorage.getItem('skyguard_token'));
  
  // Real-Time WebSocket state
  const [isWsConnected, setIsWsConnected] = useState(false);
  const wsRef = useRef(null);

  // User state
  const [user, setUser] = useState(null);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);

  // Synchronize ref with state
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

  // 1. Initial Data Fetching
  const fetchInitialData = async () => {
    try {
      const [stRes, anomRes] = await Promise.all([
        api.get('/api/v1/stations'),
        api.get('/api/v1/anomalies?limit=50')
      ]);
      setStations(stRes.data);
      setAnomalies(anomRes.data);

      if (stRes.data.length > 0 && !selectedStationRef.current) {
        setSelectedStation(stRes.data[0]);
        fetchStationTelemetry(stRes.data[0].station_id);
      }
    } catch (err) {
      console.error('Failed to load initial data:', err);
    }
  };

  const fetchStationTelemetry = async (stationId) => {
    try {
      const res = await api.get(`/api/v1/stations/${stationId}`);
      if (res.data.recent_readings) {
        setReadings(res.data.recent_readings);
      }
    } catch (err) {
      console.error(`Failed to load readings for ${stationId}:`, err);
    }
  };

  useEffect(() => {
    fetchInitialData();
    const pollInterval = setInterval(() => {
      api.get('/api/v1/stations').then(res => setStations(res.data)).catch(() => {});
      api.get('/api/v1/anomalies?limit=50').then(res => setAnomalies(res.data)).catch(() => {});
    }, 10000);
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

    const connectWs = () => {
      const rawToken = localStorage.getItem('skyguard_token');
      const isValidToken = rawToken && rawToken !== 'undefined' && rawToken !== 'null' && rawToken.length > 20;
      const tokenParam = isValidToken ? `?token=${encodeURIComponent(rawToken)}` : '';
      const baseWsUrl = getWebSocketUrl();
      const wsUrl = `${baseWsUrl}${tokenParam}`;
      
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsWsConnected(true);
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
                  temperature_c: data.reading.temperature_c,
                  pressure_hpa: data.reading.pressure_hpa,
                  humidity_pct: data.reading.humidity_pct,
                  dew_point_c: data.reading.dew_point_c,
                  sea_level_pressure_hpa: data.reading.sea_level_pressure_hpa,
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
                        temperature_c: data.reading.temperature_c,
                        pressure_hpa: data.reading.pressure_hpa,
                        humidity_pct: data.reading.humidity_pct,
                        is_anomaly: data.is_anomaly,
                        timestamp: data.timestamp
                      }
                    }
                  : s
              )
            );

            // 3. Prepend to Anomaly Feed (quietly update table)
            if (data.is_anomaly) {
              const newIncident = {
                event_id: `evt-${Date.now()}`,
                id: `toast-${Date.now()}`,
                station_id: data.station_id,
                timestamp: data.timestamp,
                severity: data.severity_score,
                severity_score: data.severity_score,
                confidence_score: 0.92,
                root_cause: data.root_cause,
                explanation: data.explanation,
                estimated_corrected_values: data.imputed,
                status: 'ACTIVE'
              };

              setAnomalies((prev) => [newIncident, ...prev]);

              // ONLY show popup toast if user has explicitly enabled toasts AND at least 60s passed for this station
              if (toastEnabled) {
                const now = Date.now();
                const lastTime = lastToastTimeRef.current[data.station_id] || 0;
                if (now - lastTime > 60000) {
                  lastToastTimeRef.current[data.station_id] = now;
                  sounds.playAlert();
                  setToasts((prev) => [newIncident, ...prev.slice(0, 1)]);
                  // Auto-dismiss after 6 seconds
                  setTimeout(() => {
                    setToasts((prev) => prev.filter(t => t.id !== newIncident.id));
                  }, 6000);
                }
              }
            }
          }
        } catch (e) {
          console.error('[SkyGuard WS] Message parse error:', e);
        }
      };

      ws.onclose = (event) => {
        setIsWsConnected(false);
        if (event.code === 4001) {
          console.warn('[SkyGuard WS] Token expired or rotated, clearing stale credential');
          localStorage.removeItem('skyguard_token');
          setToken(null);
        }
        reconnectTimer = setTimeout(connectWs, 3000);
      };

      ws.onerror = (e) => {
        console.warn('[SkyGuard WS] Connection error:', e);
        ws.close();
      };
    };

    connectWs();

    return () => {
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (wsRef.current) wsRef.current.close();
    };
  }, [toastEnabled]);

  const handleResolveAlert = (eventId, newStatus) => {
    setAnomalies((prev) =>
      prev.map((a) => (a.event_id === eventId ? { ...a, status: newStatus } : a))
    );
  };

  const handleSimulatorTriggerSuccess = (stationId) => {
    const matched = stations.find(s => s.station_id === stationId);
    if (matched) {
      setSelectedStation(matched);
      fetchStationTelemetry(stationId);
    }
  };

  const handleInspectToast = (toastItem) => {
    setActiveTab('alerts');
    const matched = stations.find(s => s.station_id === toastItem.station_id);
    if (matched) {
      setSelectedStation(matched);
      fetchStationTelemetry(toastItem.station_id);
    }
  };

  const handleDismissToast = (id) => {
    setToasts((prev) => prev.filter(t => t.id !== id && t.event_id !== id));
  };

  return (
    <LanguageProvider>
      <div className="min-h-screen bg-[var(--bg-app)] text-slate-100 flex flex-col font-sans select-none antialiased pb-12">
        {/* 1. Global Navigation Bar */}
        <Header
          activeTab={activeTab}
          setActiveTab={setActiveTab}
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
          {/* TAB 1: NETWORK OVERVIEW (KPIs + GIS Pan-India Radar Map) */}
          {activeTab === 'overview' && (
            <div className="space-y-6 animate-fadeIn">
              <KPICards stations={stations} anomalies={anomalies} />
              <LiveMap
                stations={stations}
                selectedStation={selectedStation}
                onSelectStation={handleSelectStation}
              />
            </div>
          )}

          {/* TAB 2: TELEMETRY STREAM & SELF-HEALING IMPUTATION */}
          {activeTab === 'telemetry' && (
            <div className="space-y-6 animate-fadeIn">
              <TelemetryChart
                stations={stations}
                selectedStation={selectedStation}
                onSelectStation={handleSelectStation}
                readings={readings}
              />
            </div>
          )}

          {/* TAB 3: INCIDENT CENTER & EXPLAINABLE AI (XAI) */}
          {activeTab === 'alerts' && (
            <div className="space-y-6 animate-fadeIn">
              <AlertFeed
                anomalies={anomalies}
                stations={stations}
                onResolveAlert={handleResolveAlert}
                onResolveSuccess={fetchInitialData}
                onSelectStation={handleSelectStation}
              />
            </div>
          )}

          {/* TAB 4: STATION HEALTH LEADERBOARD & MAINTENANCE */}
          {activeTab === 'health' && (
            <div className="space-y-6 animate-fadeIn">
              <SensorHealthLeaderboard
                stations={stations}
                selectedStation={selectedStation}
                onSelectStation={handleSelectStation}
              />
            </div>
          )}

          {/* TAB 5: AI MODEL BENCHMARKS */}
          {activeTab === 'benchmark' && (
            <div className="space-y-6 animate-fadeIn">
              <ModelBenchmarkScreen />
            </div>
          )}

          {/* TAB 6: FAULT INJECTION WORKBENCH */}
          {activeTab === 'simulator' && (
            <div className="space-y-6 animate-fadeIn">
              <SimulatorPanel
                stations={stations}
                onTabChange={setActiveTab}
                onInjectSuccess={(stId) => {
                  const target = stations.find(s => s.station_id === stId);
                  if (target) {
                    setSelectedStation(target);
                    fetchStationTelemetry(stId);
                  }
                  sounds.playSuccessChime();
                  setActiveTab('telemetry');
                }}
                onInjectionSuccess={(stId) => {
                  const target = stations.find(s => s.station_id === stId);
                  if (target) {
                    setSelectedStation(target);
                    fetchStationTelemetry(stId);
                  }
                  sounds.playSuccessChime();
                  setActiveTab('telemetry');
                }}
              />
            </div>
          )}


          {/* TAB 7: CALIBRATION & SYSTEM SETTINGS */}
          {activeTab === 'admin' && (
            <div className="space-y-6 animate-fadeIn">
              <AdminSettings token={token} onRefreshData={fetchInitialData} />
            </div>
          )}
        </main>

        {/* 4. Floating Toast Notification Hub */}
        {toastEnabled && (
          <ToastContainer
            toasts={toasts}
            onDismiss={handleDismissToast}
            onInspect={handleInspectToast}
            onSelectAlert={handleInspectToast}
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
