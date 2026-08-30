import React, { useState, useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, GeoJSON } from 'react-leaflet';
import L from 'leaflet';
import {
  ShieldCheck,
  AlertTriangle,
  Radio,
  Thermometer,
  Wind,
  Droplets,
  Layers,
  Compass,
  ArrowUpRight,
  Maximize2,
  Map
} from 'lucide-react';
import { sounds } from '../utils/audio';

// Custom SVG Pulsing Radar Pin for Leaflet
const createStatusPin = (healthScore = 100, isAnom = false) => {
  let color = '#10B981'; // Green
  let pulseColor = 'rgba(16, 185, 129, 0.4)';
  if (isAnom || healthScore < 60) {
    color = '#EF4444'; // Red
    pulseColor = 'rgba(239, 68, 68, 0.5)';
  } else if (healthScore < 85) {
    color = '#F59E0B'; // Amber
    pulseColor = 'rgba(245, 158, 11, 0.4)';
  }

  const svgHtml = `
    <div style="position: relative; width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; cursor: pointer;">
      <div style="position: absolute; width: 32px; height: 32px; border-radius: 50%; background-color: ${pulseColor}; animation: pulse-ring 2s infinite;"></div>
      <div style="position: relative; width: 18px; height: 18px; border-radius: 50%; background: ${color}; border: 3px solid #030712; box-shadow: 0 0 15px ${color}, 0 0 5px #ffffff;"></div>
    </div>
  `;

  return L.divIcon({
    html: svgHtml,
    className: 'custom-leaflet-marker',
    iconSize: [36, 36],
    iconAnchor: [18, 18],
    popupAnchor: [0, -18]
  });
};

// India state boundaries GeoJSON style (Blueprint §2.2 — administrative overlay)
const STATE_BORDER_STYLE = {
  color: '#38BDF8',
  weight: 0.8,
  opacity: 0.35,
  fillColor: '#1E3A5F',
  fillOpacity: 0.06,
};

export default function LiveMap({ stations = [], selectedStation, onSelectStation }) {
  const [filterMode, setFilterMode] = useState('ALL'); // ALL | HEALTHY | ANOMALY
  const [showBorders, setShowBorders] = useState(true);
  const [indiaGeoJson, setIndiaGeoJson] = useState(null);
  const centerPosition = [22.3511, 78.6677]; // Geographic Center of India

  // Load India state GeoJSON from public CDN (Blueprint §2.2)
  useEffect(() => {
    fetch('https://raw.githubusercontent.com/geohacker/india/master/state/india_state.geojson')
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data) setIndiaGeoJson(data); })
      .catch(() => {}); // Silently ignore if offline
  }, []);

  const filteredStations = stations.filter((st) => {
    const isAnom = st.latest_reading?.is_anomaly;
    const health = st.health_score ?? 100;
    if (filterMode === 'HEALTHY') return health >= 85 && !isAnom;
    if (filterMode === 'ANOMALY') return isAnom || health < 60;
    return true;
  });

  return (
    <div className="glass-panel p-5 flex flex-col h-[580px] relative overflow-hidden">
      {/* Header & Filter Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3 z-10">
        <div>
          <h2 className="text-base font-bold text-white flex items-center gap-2">
            <Compass className="w-4 h-4 text-sky-400 animate-spin" style={{ animationDuration: '15s' }} />
            Geospatial AWS Telemetry GIS Map
            <span className="glass-badge text-sky-400 border-sky-500/30 text-[10px]">
              {stations.length} Nodes Online
            </span>
          </h2>
          <p className="text-xs text-slate-400">
            Interactive real-time Pan-India automated surface weather telemetry network
          </p>
        </div>

        {/* Quick Filter Buttons + Border Toggle */}
        <div className="flex items-center gap-2 flex-wrap self-start sm:self-auto">
          <div className="flex items-center gap-1.5 bg-slate-900/90 p-1 rounded-xl border border-slate-800">
            {[
              { id: 'ALL', label: 'All Stations' },
              { id: 'HEALTHY', label: 'Healthy (≥85)' },
              { id: 'ANOMALY', label: 'Alerts' },
            ].map(({ id, label }) => (
              <button
                key={id}
                onClick={() => {
                  sounds.playClick();
                  setFilterMode(id);
                }}
                className={`px-2.5 py-1 rounded-lg text-[11px] font-bold transition-all ${
                  filterMode === id
                    ? 'bg-sky-500 text-slate-950 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          {/* State Borders Toggle — Blueprint §2.2 */}
          <button
            onClick={() => { sounds.playClick(); setShowBorders(v => !v); }}
            title="Toggle India state boundary layer"
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl text-[11px] font-bold border transition-all ${
              showBorders
                ? 'bg-sky-500/15 border-sky-500/40 text-sky-400'
                : 'bg-slate-900/90 border-slate-800 text-slate-500 hover:text-slate-300'
            }`}
          >
            <Map className="w-3.5 h-3.5" />
            State Borders
          </button>
        </div>
      </div>

      {/* Map Body Container */}
      <div className="flex-1 w-full rounded-2xl overflow-hidden relative border border-slate-800/80 shadow-2xl">
        <MapContainer
          center={centerPosition}
          zoom={5}
          scrollWheelZoom={true}
          style={{ height: '100%', width: '100%', borderRadius: '14px' }}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          {/* India State Administrative Boundaries — Blueprint §2.2 */}
          {showBorders && indiaGeoJson && (
            <GeoJSON
              key="india-states"
              data={indiaGeoJson}
              style={STATE_BORDER_STYLE}
            />
          )}

          {filteredStations.map((st) => {
            const isAnom = st.latest_reading?.is_anomaly;
            const health = st.health_score ?? 100;
            const isSelected = selectedStation?.station_id === st.station_id;

            return (
              <Marker
                key={st.station_id}
                position={[st.latitude, st.longitude]}
                icon={createStatusPin(health, isAnom)}
                eventHandlers={{
                  click: () => {
                    sounds.playClick();
                    onSelectStation(st);
                  }
                }}
              >
                <Popup>
                  <div className="p-1 min-w-[220px]">
                    {/* Header */}
                    <div className="flex items-center justify-between border-b border-slate-800 pb-2 mb-2">
                      <div>
                        <h4 className="font-extrabold text-white text-sm tracking-tight">{st.name}</h4>
                        <span className="text-[10px] text-sky-400 font-mono font-bold">{st.station_id}</span>
                      </div>
                      <span
                        className={`text-[10px] font-extrabold px-2 py-0.5 rounded-full font-mono ${
                          isAnom
                            ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                            : health >= 85
                            ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                            : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                        }`}
                      >
                        {isAnom ? '🔴 ANOMALY' : `${health.toFixed(0)}% HEALTH`}
                      </span>
                    </div>

                    {/* Metadata Specs */}
                    <div className="space-y-1.5 text-xs text-slate-300">
                      <div className="flex justify-between font-mono text-[11px]">
                        <span className="text-slate-400">Elevation:</span>
                        <span className="text-white font-bold">{st.altitude_m}m MSL</span>
                      </div>
                      <div className="flex justify-between text-[11px]">
                        <span className="text-slate-400">Region:</span>
                        <span className="text-slate-200 font-medium">{st.district || st.state}, India</span>
                      </div>

                      {/* Live 3-Axis Reading Mini HUD */}
                      {st.latest_reading && (
                        <div className="mt-2.5 pt-2 border-t border-slate-800/90 grid grid-cols-3 gap-1 text-center font-mono">
                          <div className="bg-slate-900/80 p-1.5 rounded-lg border border-slate-800">
                            <span className="text-[9px] text-slate-400 block font-sans uppercase">Temp</span>
                            <span className="text-sky-400 font-bold text-xs">
                              {st.latest_reading.temperature_c != null ? `${st.latest_reading.temperature_c.toFixed(1)}°` : '—'}
                            </span>
                          </div>
                          <div className="bg-slate-900/80 p-1.5 rounded-lg border border-slate-800">
                            <span className="text-[9px] text-slate-400 block font-sans uppercase">Pres</span>
                            <span className="text-indigo-400 font-bold text-xs">
                              {st.latest_reading.pressure_hpa != null ? st.latest_reading.pressure_hpa.toFixed(0) : '—'}
                            </span>
                          </div>
                          <div className="bg-slate-900/80 p-1.5 rounded-lg border border-slate-800">
                            <span className="text-[9px] text-slate-400 block font-sans uppercase">Hum</span>
                            <span className="text-emerald-400 font-bold text-xs">
                              {st.latest_reading.humidity_pct != null ? `${st.latest_reading.humidity_pct.toFixed(0)}%` : '—'}
                            </span>
                          </div>
                        </div>
                      )}
                    </div>

                    <button
                      onClick={() => {
                        sounds.playClick();
                        onSelectStation(st, true);
                      }}
                      className="mt-3 w-full py-1.5 rounded-xl bg-gradient-to-r from-sky-500 to-indigo-600 text-white text-xs font-bold hover:brightness-110 shadow-md shadow-sky-500/20 transition-all flex items-center justify-center gap-1"
                    >
                      View Live Telemetry Analytics <ArrowUpRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </Popup>
              </Marker>
            );
          })}
        </MapContainer>

        {/* Floating Station HUD Indicator */}
        {selectedStation && (
          <div className="absolute bottom-3 left-3 z-[1000] bg-slate-950/90 border border-sky-500/30 p-2.5 rounded-xl backdrop-blur-xl shadow-xl flex items-center gap-3">
            <div className="w-2.5 h-2.5 rounded-full bg-sky-400 animate-ping" />
            <div>
              <div className="text-[10px] text-slate-400 uppercase font-mono font-bold">Selected Station</div>
              <div className="text-xs font-bold text-white font-mono">{selectedStation?.station_id} — {selectedStation?.name}</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
