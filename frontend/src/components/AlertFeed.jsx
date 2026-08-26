import React, { useState } from 'react';
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer
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
import axios from 'axios';
import { sounds } from '../utils/audio';

const STATION_MAP = {
  'AWS-DEL-01': { name: 'Delhi Safdarjung', state: 'Delhi' },
  'AWS-MUM-01': { name: 'Mumbai Santacruz', state: 'Maharashtra' },
  'AWS-CHE-01': { name: 'Chennai Meenambakkam', state: 'Tamil Nadu' },
  'AWS-KOL-01': { name: 'Kolkata Alipore', state: 'West Bengal' },
  'AWS-JAI-01': { name: 'Jaipur Sanganer', state: 'Rajasthan' }
};

export default function AlertFeed({ anomalies = [], stations = [], onResolveAlert }) {
  const [selectedAlert, setSelectedAlert] = useState(null);
  const [filterStatus, setFilterStatus] = useState('ACTIVE');
  const [filterStation, setFilterStation] = useState('ALL');
  const [resolveNotes, setResolveNotes] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Filter by both Status and Station
  const filtered = anomalies.filter((a) => {
    const matchesStatus = filterStatus === 'ALL' || a.status === filterStatus;
    const matchesStation = filterStation === 'ALL' || a.station_id === filterStation;
    return matchesStatus && matchesStation;
  });

  const handleAction = async (newStatus) => {
    if (!selectedAlert) return;
    setIsSubmitting(true);
    try {
      await axios.patch(`/api/v1/anomalies/${selectedAlert.event_id}/resolve`, {
        status: newStatus,
        resolved_by: 'Operator (Web UI)',
        resolution_notes: resolveNotes || `Incident ${newStatus.toLowerCase()} via Incident Center.`
      });
      sounds.playSuccessChime();
      onResolveAlert(selectedAlert.event_id, newStatus);
      setSelectedAlert((prev) => ({ ...prev, status: newStatus }));
      setResolveNotes('');
    } catch (err) {
      console.error('Failed to resolve alert:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Helper to format simple title & icon
  const getSimpleFaultInfo = (rootCause = '', explanation = '') => {
    const rc = rootCause.toUpperCase();
    if (rc.includes('THERMODYNAMIC') || rc.includes('DEW')) {
      return {
        title: 'Moisture / Humidity Sensor Glitch',
        icon: <Droplets className="w-4 h-4 text-sky-400" />,
        badgeColor: 'bg-sky-500/20 text-sky-300 border-sky-500/30',
        fix: 'Check the humidity sensor probe for water droplets, rain condensation, or dirt buildup.'
      };
    }
    if (rc.includes('FLATLINE') || rc.includes('FROZEN')) {
      return {
        title: 'Stuck / Frozen Sensor Value',
        icon: <Snowflake className="w-4 h-4 text-cyan-400" />,
        badgeColor: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30',
        fix: 'Inspect data cable connection and restart the station datalogger.'
      };
    }
    if (rc.includes('BOUND') || rc.includes('PHYSICAL')) {
      return {
        title: 'Extreme / Impossible Weather Reading',
        icon: <AlertTriangle className="w-4 h-4 text-rose-400" />,
        badgeColor: 'bg-rose-500/20 text-rose-300 border-rose-500/30',
        fix: 'Inspect transducer wiring for electrical shorts or loose terminal screws.'
      };
    }
    if (rc.includes('DRIFT')) {
      return {
        title: 'Slow Sensor Calibration Drift',
        icon: <TrendingDown className="w-4 h-4 text-amber-400" />,
        badgeColor: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
        fix: 'Dispatch field technician for physical baseline zero-point recalibration.'
      };
    }
    if (rc.includes('SPATIAL')) {
      return {
        title: 'Mismatch with Nearby Stations',
        icon: <MapPin className="w-4 h-4 text-purple-400" />,
        badgeColor: 'bg-purple-500/20 text-purple-300 border-purple-500/30',
        fix: 'Cross-verify with neighboring AWS nodes to confirm localized sensor bias.'
      };
    }
    return {
      title: 'Sudden Sensor Spike / Glitch',
      icon: <Zap className="w-4 h-4 text-amber-400" />,
      badgeColor: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
      fix: 'Check power supply line and grounding for electrical voltage spikes.'
    };
  };

  const activeCount = anomalies.filter((a) => a.status === 'ACTIVE').length;

  return (
    <div className="glass-panel p-5 flex flex-col h-[580px] relative">
      {/* Clean Single-Row Header */}
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

        {/* Filter Controls (Station + Status) */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* Station Filter Dropdown */}
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
              {Object.entries(STATION_MAP).map(([id, info]) => {
                const count = anomalies.filter(a => a.station_id === id).length;
                return (
                  <option key={id} value={id} className="bg-slate-950 text-white">
                    {info.name} ({count})
                  </option>
                );
              })}
            </select>
          </div>

          {/* Status Tabs */}
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

      {/* Alert Cards List */}
      <div className="flex-1 overflow-y-auto space-y-2.5 pr-1">
        {filtered.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-slate-500 text-sm gap-2 py-10">
            <CheckCircle className="w-10 h-10 text-emerald-500/60" />
            <p className="font-semibold text-slate-300">No {filterStatus.toLowerCase()} incidents recorded.</p>
            <p className="text-xs text-slate-500">All sensor telemetry for {filterStation === 'ALL' ? 'all stations' : STATION_MAP[filterStation]?.name || filterStation} is operating nominally.</p>
          </div>
        ) : (
          filtered.map((alert) => {
            const isHigh = alert.severity_score >= 0.75;
            const isSelected = selectedAlert?.event_id === alert.event_id;
            const stInfo = STATION_MAP[alert.station_id] || { name: alert.station_id, state: 'India' };
            const fault = getSimpleFaultInfo(alert.root_cause, alert.explanation);

            return (
              <div
                key={alert.event_id}
                onClick={() => {
                  sounds.playClick();
                  setSelectedAlert(alert);
                }}
                className={`p-3.5 rounded-2xl border transition-all duration-200 cursor-pointer flex items-center justify-between group ${
                  isSelected
                    ? 'bg-[#121624] border-[#00D2FF] shadow-lg shadow-[#00D2FF]/20 scale-[1.01]'
                    : isHigh
                    ? 'bg-[#1E0812]/50 border-[#FF0055]/40 hover:border-[#FF0055]/80 hover:bg-[#2A0B1A]/60'
                    : 'bg-[#0E111A]/80 border-[rgba(0,210,255,0.12)] hover:border-[rgba(0,210,255,0.3)] hover:bg-[#141824]'
                }`}
                style={{
                  borderLeftWidth: '4px',
                  borderLeftColor: isHigh ? '#FF0055' : alert.status === 'RESOLVED' ? '#00FFA3' : '#F59E0B'
                }}
              >
                <div className="flex items-start gap-3 flex-1 min-w-0 pr-3">
                  <div
                    className={`p-2 rounded-xl mt-0.5 transition-transform group-hover:scale-110 flex-shrink-0 ${
                      isHigh ? 'bg-[#FF0055]/20 text-[#FF0055]' : 'bg-amber-500/20 text-amber-400'
                    }`}
                  >
                    {fault.icon}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold text-xs text-white flex items-center gap-1">
                        <MapPin className="w-3 h-3 text-[#00D2FF]" />
                        {stInfo.name}
                        <span className="text-[10px] text-slate-400 font-mono">({alert.station_id})</span>
                      </span>
                      <span className="text-[10px] text-slate-400 flex items-center gap-1 font-mono">
                        <Clock className="w-3 h-3 text-slate-500" />
                        {new Date(alert.timestamp).toLocaleTimeString()}
                      </span>
                      <span
                        className={`text-[9px] font-bold px-2 py-0.5 rounded-full font-mono uppercase ${
                          alert.status === 'ACTIVE'
                            ? 'bg-[#FF0055]/20 text-[#FF0055] border border-[#FF0055]/30'
                            : alert.status === 'ACKNOWLEDGED'
                            ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                            : 'bg-[#00FFA3]/20 text-[#00FFA3] border border-[#00FFA3]/30'
                        }`}
                      >
                        {alert.status}
                      </span>
                    </div>

                    <p className="text-xs text-slate-100 font-bold mt-1">
                      {fault.title}
                    </p>
                    <p className="text-[11px] text-slate-300 line-clamp-1 mt-0.5 leading-relaxed">
                      {alert.explanation}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-3 flex-shrink-0">
                  <div className="text-right">
                    <span className="text-sm font-mono font-extrabold text-rose-400">
                      {(alert.severity_score * 100).toFixed(0)}%
                    </span>
                    <span className="text-[9px] text-slate-400 font-mono block uppercase">Severity</span>
                  </div>
                  <ChevronRight className="w-4 h-4 text-slate-500 group-hover:text-sky-400 group-hover:translate-x-0.5 transition-all" />
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* XAI DETAIL INSPECTION DRAWER MODAL */}
      {selectedAlert && (
        <div className="absolute inset-0 z-50 bg-[#070B14] p-5 flex flex-col rounded-2xl border border-sky-500/60 shadow-2xl animate-fadeIn select-text">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-3.5 bg-[#070B14]">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-xl bg-[#0D1F38] text-sky-400 border border-sky-500/40 shadow-sm">
                <Sparkles className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-extrabold text-white flex items-center gap-2">
                  XAI Sensor Diagnosis & Simple Reason
                  <span className="font-mono text-[11px] text-sky-400 font-bold">#{selectedAlert.event_id.slice(-8)}</span>
                </h3>
                <p className="text-xs text-slate-400">
                  📍 <strong className="text-slate-200">{STATION_MAP[selectedAlert.station_id]?.name || selectedAlert.station_id}</strong> &bull; {new Date(selectedAlert.timestamp).toLocaleString()}
                </p>
              </div>
            </div>
            <button
              onClick={() => {
                sounds.playClick();
                setSelectedAlert(null);
              }}
              className="p-1.5 rounded-xl bg-[#0F172A] text-slate-400 hover:text-white border border-slate-700 hover:bg-slate-800 transition-all"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Drawer Body */}
          <div className="flex-1 overflow-y-auto space-y-3.5 pr-1 text-xs bg-[#070B14]">
            {/* Plain English Reason Box */}
            <div className="p-3.5 rounded-2xl bg-[#0B192E] border border-sky-500/40 shadow-md">
              <span className="text-[10px] font-bold text-sky-400 uppercase tracking-wider block mb-1 font-mono">
                🔍 What Happened? (Reason in Simple Words)
              </span>
              <p className="text-slate-100 text-xs leading-relaxed font-medium">{selectedAlert.explanation}</p>
            </div>

            {/* Recommended Action */}
            <div className="p-3.5 rounded-2xl bg-[#1C160B] border border-amber-500/40 shadow-md">
              <span className="text-[10px] font-bold text-amber-400 uppercase tracking-wider block mb-1 font-mono flex items-center gap-1.5">
                <Wrench className="w-3.5 h-3.5" />
                🔧 Recommended Fix for Technicians
              </span>
              <p className="text-amber-200 text-xs font-medium leading-relaxed">
                {getSimpleFaultInfo(selectedAlert.root_cause).fix}
              </p>
            </div>

            {/* Metrics */}
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3 rounded-2xl bg-[#0D1527] border border-slate-800 shadow-sm">
                <span className="text-slate-400 block text-[10px] uppercase font-mono font-bold">Severity Score</span>
                <div className="text-lg font-extrabold text-rose-400 font-mono mt-0.5">
                  {(selectedAlert.severity_score * 100).toFixed(1)}%
                </div>
              </div>
              <div className="p-3 rounded-2xl bg-[#0D1527] border border-slate-800 shadow-sm">
                <span className="text-slate-400 block text-[10px] uppercase font-mono font-bold">AI Certainty</span>
                <div className="text-lg font-extrabold text-emerald-400 font-mono mt-0.5">
                  {((selectedAlert.confidence_score || 0.92) * 100).toFixed(1)}%
                </div>
              </div>
            </div>

            {/* AI Imputed Values */}
            {selectedAlert.estimated_corrected_values && (
              <div className="p-3.5 rounded-2xl bg-[#071A13] border border-emerald-500/40 shadow-md">
                <span className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider block mb-1.5 font-mono">
                  🩹 Autoencoder Imputed Value (AI Corrected Physical Reading)
                </span>
                <div className="grid grid-cols-3 gap-2 font-mono text-center">
                  <div className="bg-[#0A1322] p-2 rounded-xl border border-slate-700">
                    <span className="text-[9px] text-slate-400 block font-sans uppercase">Temp</span>
                    <span className="text-emerald-400 font-bold text-xs">
                      {selectedAlert.estimated_corrected_values.temperature_c}°C
                    </span>
                  </div>
                  <div className="bg-[#0A1322] p-2 rounded-xl border border-slate-700">
                    <span className="text-[9px] text-slate-400 block font-sans uppercase">Pressure</span>
                    <span className="text-emerald-400 font-bold text-xs">
                      {selectedAlert.estimated_corrected_values.pressure_hpa}hPa
                    </span>
                  </div>
                  <div className="bg-[#0A1322] p-2 rounded-xl border border-slate-700">
                    <span className="text-[9px] text-slate-400 block font-sans uppercase">Humidity</span>
                    <span className="text-emerald-400 font-bold text-xs">
                      {selectedAlert.estimated_corrected_values.humidity_pct}%
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Action Footer */}
          <div className="mt-3 pt-3 border-t border-slate-800 flex items-center justify-between gap-3 bg-[#070B14]">
            <input
              type="text"
              placeholder="Resolution notes (e.g. 'Cleaned sensor probe')..."
              value={resolveNotes}
              onChange={(e) => setResolveNotes(e.target.value)}
              className="flex-1 bg-[#0D1527] border border-slate-700 text-white text-xs rounded-xl px-3 py-2 focus:outline-none focus:border-sky-500"
            />
            <div className="flex items-center gap-2">
              <button
                disabled={isSubmitting || selectedAlert.status === 'ACKNOWLEDGED'}
                onClick={() => handleAction('ACKNOWLEDGED')}
                className="px-3.5 py-2 rounded-xl bg-amber-500/20 text-amber-300 border border-amber-500/40 text-xs font-bold hover:bg-amber-500 hover:text-slate-950 transition-all disabled:opacity-40"
              >
                Acknowledge
              </button>
              <button
                disabled={isSubmitting || selectedAlert.status === 'RESOLVED'}
                onClick={() => handleAction('RESOLVED')}
                className="px-3.5 py-2 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 text-slate-950 text-xs font-bold hover:brightness-110 shadow-lg shadow-emerald-500/20 transition-all flex items-center gap-1.5 disabled:opacity-40"
              >
                <CheckCircle className="w-3.5 h-3.5" /> Mark Resolved
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
