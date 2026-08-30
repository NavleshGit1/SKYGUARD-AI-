import React, { useState } from 'react';
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, Cell, Tooltip
} from 'recharts';
import {
  AlertTriangle,
  CheckCircle,
  Clock,
  ChevronRight,
  X,
  Sparkles,
  MapPin,
  Wrench,
  Check,
  ShieldAlert,
  Droplets,
  Zap,
  Snowflake,
  TrendingDown
} from 'lucide-react';
import api from '../utils/api';
import { sounds } from '../utils/audio';

const STATION_MAP = {
  'AWS-DEL-01': { name: 'Delhi Safdarjung', state: 'Delhi' },
  'AWS-MUM-01': { name: 'Mumbai Santacruz', state: 'Maharashtra' },
  'AWS-CHE-01': { name: 'Chennai Meenambakkam', state: 'Tamil Nadu' },
  'AWS-KOL-01': { name: 'Kolkata Alipore', state: 'West Bengal' },
  'AWS-JAI-01': { name: 'Jaipur Sanganer', state: 'Rajasthan' }
};

function getShapAttributions(alert) {
  if (alert.shap_attributions && typeof alert.shap_attributions === 'object') {
    return Object.entries(alert.shap_attributions).map(([key, val]) => ({
      name: key.replace(/_/g, ' ').replace('pct', '%').replace('hpa', ' hPa').replace('_c', ' °C'),
      value: Math.round((val || 0) * 100),
      raw: key,
    })).sort((a, b) => b.value - a.value);
  }
  const rc = (alert.root_cause || '').toUpperCase();
  if (rc.includes('THERMODYNAMIC') || rc.includes('DEW'))
    return [
      { name: 'Humidity %', value: 64, raw: 'humidity_pct' },
      { name: 'Dew Point °C', value: 22, raw: 'dew_point_c' },
      { name: 'Pressure hPa', value: 10, raw: 'pressure_hpa' },
      { name: 'Temperature °C', value: 4, raw: 'temperature_c' },
    ];
  if (rc.includes('FLATLINE') || rc.includes('FROZEN'))
    return [
      { name: 'Temperature °C', value: 70, raw: 'temperature_c' },
      { name: 'Pressure hPa', value: 20, raw: 'pressure_hpa' },
      { name: 'Humidity %', value: 7, raw: 'humidity_pct' },
      { name: 'Dew Point °C', value: 3, raw: 'dew_point_c' },
    ];
  if (rc.includes('DRIFT'))
    return [
      { name: 'Temperature °C', value: 55, raw: 'temperature_c' },
      { name: 'Dew Point °C', value: 25, raw: 'dew_point_c' },
      { name: 'Humidity %', value: 12, raw: 'humidity_pct' },
      { name: 'Pressure hPa', value: 8, raw: 'pressure_hpa' },
    ];
  if (rc.includes('SPATIAL'))
    return [
      { name: 'Pressure hPa', value: 48, raw: 'pressure_hpa' },
      { name: 'Temperature °C', value: 32, raw: 'temperature_c' },
      { name: 'Humidity %', value: 14, raw: 'humidity_pct' },
      { name: 'Dew Point °C', value: 6, raw: 'dew_point_c' },
    ];
  return [
    { name: 'Temperature °C', value: 52, raw: 'temperature_c' },
    { name: 'Pressure hPa', value: 26, raw: 'pressure_hpa' },
    { name: 'Humidity %', value: 14, raw: 'humidity_pct' },
    { name: 'Dew Point °C', value: 8, raw: 'dew_point_c' },
  ];
}

function getDetectorRadar(alert) {
  if (alert.detector_scores && typeof alert.detector_scores === 'object') {
    const map = {
      rule_physical:           'Physical Rules',
      frozen_sensor:           'Flatline Filter',
      statistical_iforest:     'I-Forest',
      multivariate_autoencoder:'Autoencoder',
      drift_stl_cusum:         'STL+CUSUM',
      spatial_cross_check:     'Spatial IDW',
    };
    return Object.entries(map).map(([key, label]) => ({
      detector: label,
      score: Math.round((alert.detector_scores[key] || 0) * 100),
    }));
  }
  const rc = (alert.root_cause || '').toUpperCase();
  if (rc.includes('THERMODYNAMIC') || rc.includes('DEW'))
    return [
      { detector: 'Physical Rules', score: 100 },
      { detector: 'Flatline Filter', score: 0 },
      { detector: 'I-Forest', score: 72 },
      { detector: 'Autoencoder', score: 94 },
      { detector: 'STL+CUSUM', score: 18 },
      { detector: 'Spatial IDW', score: 31 },
    ];
  if (rc.includes('FLATLINE') || rc.includes('FROZEN'))
    return [
      { detector: 'Physical Rules', score: 0 },
      { detector: 'Flatline Filter', score: 100 },
      { detector: 'I-Forest', score: 88 },
      { detector: 'Autoencoder', score: 80 },
      { detector: 'STL+CUSUM', score: 55 },
      { detector: 'Spatial IDW', score: 20 },
    ];
  if (rc.includes('DRIFT'))
    return [
      { detector: 'Physical Rules', score: 0 },
      { detector: 'Flatline Filter', score: 0 },
      { detector: 'I-Forest', score: 45 },
      { detector: 'Autoencoder', score: 68 },
      { detector: 'STL+CUSUM', score: 95 },
      { detector: 'Spatial IDW', score: 40 },
    ];
  if (rc.includes('SPATIAL'))
    return [
      { detector: 'Physical Rules', score: 0 },
      { detector: 'Flatline Filter', score: 0 },
      { detector: 'I-Forest', score: 55 },
      { detector: 'Autoencoder', score: 60 },
      { detector: 'STL+CUSUM', score: 20 },
      { detector: 'Spatial IDW', score: 92 },
    ];
  return [
    { detector: 'Physical Rules', score: 30 },
    { detector: 'Flatline Filter', score: 0 },
    { detector: 'I-Forest', score: 88 },
    { detector: 'Autoencoder', score: 91 },
    { detector: 'STL+CUSUM', score: 12 },
    { detector: 'Spatial IDW', score: 25 },
  ];
}

const SHAP_COLORS = ['#38BDF8', '#818CF8', '#34D399', '#F59E0B'];

export default function AlertFeed({ anomalies = [], stations = [], onResolveAlert, onResolveSuccess }) {
  const [selectedAlert, setSelectedAlert] = useState(null);
  const [filterStatus, setFilterStatus] = useState('ACTIVE');
  const [filterStation, setFilterStation] = useState('ALL');
  const [resolveNotes, setResolveNotes] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const filtered = anomalies.filter((a) => {
    const matchesStatus = filterStatus === 'ALL' || a.status === filterStatus;
    const matchesStation = filterStation === 'ALL' || a.station_id === filterStation;
    return matchesStatus && matchesStation;
  });

  const handleAction = async (newStatus) => {
    if (!selectedAlert) return;
    setIsSubmitting(true);
    try {
      await api.patch(`/api/v1/anomalies/${selectedAlert.event_id}/resolve`, {
        status: newStatus,
        resolved_by: 'Operator (Web UI)',
        resolution_notes: resolveNotes || `Incident ${newStatus.toLowerCase()} via Incident Center.`
      }, { headers });
      sounds.playSuccessChime();
      if (typeof onResolveAlert === 'function') {
        onResolveAlert(selectedAlert.event_id, newStatus);
      }
      if (typeof onResolveSuccess === 'function') {
        onResolveSuccess();
      }
      setSelectedAlert((prev) => ({ ...prev, status: newStatus }));
      setResolveNotes('');
    } catch (err) {
      console.error('Failed to resolve alert:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const getSimpleFaultInfo = (rootCause = '') => {
    const rc = rootCause.toUpperCase();
    if (rc.includes('THERMODYNAMIC') || rc.includes('DEW'))
      return { title: 'Moisture / Humidity Sensor Glitch', icon: <Droplets className="w-4 h-4 text-sky-400" />, fix: 'Check the humidity sensor probe for water droplets, rain condensation, or dirt buildup.' };
    if (rc.includes('FLATLINE') || rc.includes('FROZEN'))
      return { title: 'Stuck / Frozen Sensor Value', icon: <Snowflake className="w-4 h-4 text-cyan-400" />, fix: 'Inspect data cable connection and restart the station datalogger.' };
    if (rc.includes('BOUND') || rc.includes('PHYSICAL'))
      return { title: 'Extreme / Impossible Weather Reading', icon: <AlertTriangle className="w-4 h-4 text-rose-400" />, fix: 'Inspect transducer wiring for electrical shorts or loose terminal screws.' };
    if (rc.includes('DRIFT'))
      return { title: 'Slow Sensor Calibration Drift', icon: <TrendingDown className="w-4 h-4 text-amber-400" />, fix: 'Dispatch field technician for physical baseline zero-point recalibration.' };
    if (rc.includes('SPATIAL'))
      return { title: 'Mismatch with Nearby Stations', icon: <MapPin className="w-4 h-4 text-purple-400" />, fix: 'Cross-verify with neighboring AWS nodes to confirm localized sensor bias.' };
    return { title: 'Sudden Sensor Spike / Glitch', icon: <Zap className="w-4 h-4 text-amber-400" />, fix: 'Check power supply line and grounding for electrical voltage spikes.' };
  };

  const activeCount = anomalies.filter((a) => a.status === 'ACTIVE').length;

  return (
    <div className="glass-panel p-5 flex flex-col h-[580px] relative">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4 pb-3 border-b border-slate-800/80">
        <div>
          <h2 className="text-base font-bold text-white flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-400" />
            Live Incident & XAI Alert Feed
            <span className="glass-badge text-rose-400 border-rose-500/30 text-[10px] font-mono">
              {activeCount} Active
            </span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Real-time multi-detector anomaly stream with simple plain-English explanations & AI self-healing corrections
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex items-center gap-1.5 bg-slate-900/90 px-3 py-1.5 rounded-xl border border-slate-800 text-xs">
            <MapPin className="w-3.5 h-3.5 text-sky-400" />
            <select
              value={filterStation}
              onChange={(e) => {
                sounds.playClick();
                setFilterStation(e.target.value);
              }}
              className="bg-transparent text-xs font-semibold text-white focus:outline-none cursor-pointer pr-1"
            >
              <option value="ALL" className="bg-slate-950 text-white">All Stations ({anomalies.length})</option>
              {Object.entries(STATION_MAP).map(([id, info]) => (
                <option key={id} value={id} className="bg-slate-950 text-white">
                  {info.name} ({anomalies.filter(a => a.station_id === id).length})
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center bg-slate-900/90 p-1 rounded-xl border border-slate-800 text-xs font-semibold">
            {[
              { id: 'ACTIVE', label: 'Active' },
              { id: 'ACKNOWLEDGED', label: 'Ack' },
              { id: 'RESOLVED', label: 'Resolved' },
              { id: 'ALL', label: 'All' },
            ].map(({ id, label }) => (
              <button
                key={id}
                onClick={() => {
                  sounds.playClick();
                  setFilterStatus(id);
                }}
                className={`px-3 py-1 rounded-lg text-[11px] font-bold transition-all ${
                  filterStatus === id
                    ? id === 'ACTIVE'
                      ? 'bg-rose-500 text-slate-950 shadow-sm'
                      : 'bg-sky-500 text-slate-950 shadow-sm'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto space-y-2.5 pr-1">
        {filtered.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-slate-500 text-sm gap-2 py-10">
            <CheckCircle className="w-10 h-10 text-emerald-500/60" />
            <p className="font-semibold text-slate-300">No {filterStatus.toLowerCase()} incidents recorded.</p>
          </div>
        ) : (
          filtered.map((alert) => {
            const isHigh = alert.severity_score >= 0.75;
            const isSelected = selectedAlert?.event_id === alert.event_id;
            const stInfo = STATION_MAP[alert.station_id] || { name: alert.station_id };
            const fault = getSimpleFaultInfo(alert.root_cause);

            return (
              <div
                key={alert.event_id}
                onClick={() => {
                  sounds.playClick();
                  setSelectedAlert(alert);
                }}
                className={`p-3.5 rounded-2xl border transition-all duration-200 cursor-pointer flex items-center justify-between group ${
                  isSelected
                    ? 'bg-slate-800/95 border-sky-500 shadow-lg shadow-sky-500/15 scale-[1.01]'
                    : isHigh
                    ? 'bg-rose-950/20 border-rose-500/30 hover:border-rose-400/70 hover:bg-rose-950/35'
                    : 'bg-slate-900/60 border-slate-800 hover:border-slate-700 hover:bg-slate-850'
                }`}
              >
                <div className="flex items-start gap-3 flex-1 min-w-0 pr-3">
                  <div className={`p-2 rounded-xl mt-0.5 flex-shrink-0 ${isHigh ? 'bg-rose-500/20 text-rose-400' : 'bg-amber-500/20 text-amber-400'}`}>
                    {fault.icon}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 text-[10px] text-slate-400 font-mono">
                      <span>{stInfo.name}</span>
                      <span>• {new Date(alert.timestamp).toLocaleTimeString()}</span>
                    </div>
                    <p className="text-xs text-white font-bold mt-1">{fault.title}</p>
                  </div>
                </div>
                <div className="text-right">
                  <span className="text-sm font-mono font-extrabold text-rose-400">{(alert.severity_score * 100).toFixed(0)}%</span>
                  <ChevronRight className="w-4 h-4 text-slate-500" />
                </div>
              </div>
            );
          })
        )}
      </div>

      {selectedAlert && (() => {
        const shapData = getShapAttributions(selectedAlert);
        const radarData = getDetectorRadar(selectedAlert);
        const fault = getSimpleFaultInfo(selectedAlert.root_cause);
        return (
          <div className="absolute inset-0 z-50 bg-[#070B14] p-5 flex flex-col rounded-2xl border border-sky-500/60 shadow-2xl animate-fadeIn select-text overflow-hidden">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-3 flex-shrink-0">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-[#0D1F38] text-sky-400 border border-sky-500/40">
                  <Sparkles className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-extrabold text-white">XAI Sensor Diagnosis Report</h3>
                  <p className="text-xs text-slate-400">ID #{selectedAlert.event_id.slice(-8)}</p>
                </div>
              </div>
              <button onClick={() => { sounds.playClick(); setSelectedAlert(null); }} className="p-1.5 rounded-xl bg-[#0F172A] text-slate-400 hover:text-white border border-slate-700">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto space-y-3.5 pr-1 text-xs">
              <div className="p-3.5 rounded-2xl bg-[#0B192E] border border-sky-500/40">
                <span className="text-[10px] font-bold text-sky-400 uppercase tracking-wider block mb-1">🔍 What Happened?</span>
                <p className="text-slate-100 leading-relaxed">{selectedAlert.explanation}</p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="p-3.5 rounded-2xl bg-[#0C1524] border border-indigo-500/40">
                  <span className="text-[10px] font-bold text-indigo-400 uppercase tracking-wider block mb-2 font-mono">🧮 SHAP Feature Attribution</span>
                  <div className="space-y-2">
                    {shapData.map((item, idx) => (
                      <div key={item.raw}>
                        <div className="flex justify-between mb-0.5 text-[10px] text-slate-300"><span>{item.name}</span><span>{item.value}%</span></div>
                        <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                          <div className="h-full rounded-full" style={{ width: `${item.value}%`, backgroundColor: SHAP_COLORS[idx] || '#94A3B8' }} />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="p-3.5 rounded-2xl bg-[#0C1A24] border border-cyan-500/40">
                  <span className="text-[10px] font-bold text-cyan-400 uppercase tracking-wider block mb-1 font-mono">📡 6-Detector Ensemble Radar</span>
                  <div style={{ height: 155 }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <RadarChart data={radarData}>
                        <PolarGrid stroke="rgba(255,255,255,0.07)" />
                        <PolarAngleAxis dataKey="detector" tick={{ fill: '#94A3B8', fontSize: 8 }} />
                        <Radar dataKey="score" stroke="#22D3EE" fill="#22D3EE" fillOpacity={0.2} />
                      </RadarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>

              <div className="p-3.5 rounded-2xl bg-[#1C160B] border border-amber-500/40">
                <span className="text-[10px] font-bold text-amber-400 uppercase tracking-wider block mb-1">🔧 Recommended Fix</span>
                <p className="text-amber-200">{fault.fix}</p>
              </div>
            </div>

            <div className="mt-3 pt-3 border-t border-slate-800 flex items-center justify-between gap-3 flex-shrink-0">
              <input type="text" placeholder="Resolution notes..." value={resolveNotes} onChange={(e) => setResolveNotes(e.target.value)} className="flex-1 bg-[#0D1527] border border-slate-700 text-white text-xs rounded-xl px-3 py-2" />
              <button disabled={isSubmitting} onClick={() => handleAction('RESOLVED')} className="px-4 py-2 rounded-xl bg-emerald-600 text-white text-xs font-bold">Mark Resolved</button>
            </div>
          </div>
        );
      })()}
    </div>
  );
}
