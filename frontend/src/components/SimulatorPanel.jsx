import React, { useState } from 'react';
import {
  Terminal,
  Zap,
  Flame,
  Snowflake,
  TrendingUp,
  Radio,
  Layers,
  Check,
  Play,
  Sliders
} from 'lucide-react';
import api from '../utils/api';
import { sounds } from '../utils/audio';

export default function SimulatorPanel({ stations = [], onInjectSuccess }) {
  const [stationId, setStationId] = useState('AWS-DEL-01');
  const [anomalyType, setAnomalyType] = useState('SPIKE');
  const [parameter, setParameter] = useState('temperature_c');
  const [magnitude, setMagnitude] = useState(25.0);
  const [duration, setDuration] = useState(10);
  const [loading, setLoading] = useState(false);
  const [lastResponse, setLastResponse] = useState(null);

  const FAULT_PRESETS = [
    {
      id: 'SPIKE',
      name: 'Impulse Step Spike (+25°C)',
      icon: Zap,
      desc: 'Instantaneous rate-of-change limit violation',
      defaultParam: 'temperature_c',
      defaultMag: 25.0
    },
    {
      id: 'FLATLINE',
      name: 'Frozen Transducer (Zero Variance)',
      icon: Snowflake,
      desc: 'ADC latching / constant frozen sensor output',
      defaultParam: 'pressure_hpa',
      defaultMag: 0.0
    },
    {
      id: 'DRIFT',
      name: 'Calibration Drift (Theil-Sen)',
      icon: TrendingUp,
      desc: 'Progressive systematic linear calibration decay',
      defaultParam: 'temperature_c',
      defaultMag: 15.0
    },
    {
      id: 'THERMODYNAMIC_VIOLATION',
      name: 'Dew Point Invariant Inversion',
      icon: Flame,
      desc: 'Physically impossible thermodynamic state (Tdew > T)',
      defaultParam: 'humidity_pct',
      defaultMag: 99.9
    },
    {
      id: 'NOISE_BURST',
      name: 'High-Variance EMI Noise Burst',
      icon: Radio,
      desc: 'Electromagnetic interference and signal jitter',
      defaultParam: 'humidity_pct',
      defaultMag: 20.0
    },
    {
      id: 'SPATIAL_DEVIATION',
      name: 'Spatial IDW Microclimate Outlier',
      icon: Layers,
      desc: 'Isolated spatial discrepancy vs peer stations (R ≤ 50km)',
      defaultParam: 'temperature_c',
      defaultMag: 18.0
    }
  ];

  const handleTrigger = async (e) => {
    e.preventDefault();
    sounds.playFaultTrigger();
    setLoading(true);
    try {
      const res = await api.post('/api/v1/simulator/inject', {
        station_id: stationId,
        anomaly_type: anomalyType,
        parameter: parameter,
        duration_ticks: parseInt(duration),
        magnitude: parseFloat(magnitude)
      });
      setLastResponse(res.data);
      if (onInjectSuccess) {
        onInjectSuccess(stationId);
      }
    } catch (err) {
      console.error('Failed to trigger injection:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="glass-panel p-5 flex flex-col h-[520px]">
      {/* Header */}
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-800">
        <div>
          <h2 className="text-base font-bold text-white flex items-center gap-2">
            <Terminal className="w-4 h-4 text-sky-400" />
            Hardware & Synthetic Fault Injection Workbench
          </h2>
          <p className="text-xs text-slate-400">
            Inject calibrated physical sensor anomalies into live telemetry streams to validate AI detection and autoencoder imputation
          </p>
        </div>
        <span className="glass-badge text-slate-300 font-mono text-[10px]">
          Evaluation Workbench
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 flex-1 overflow-hidden">
        {/* Left Form Controls */}
        <form onSubmit={handleTrigger} className="lg:col-span-7 flex flex-col justify-between space-y-3">
          <div className="space-y-3">
            {/* Target Station */}
            <div>
              <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1 font-mono">
                Target Weather Station
              </label>
              <select
                value={stationId}
                onChange={(e) => {
                  sounds.playClick();
                  setStationId(e.target.value);
                }}
                className="w-full bg-slate-900 border border-slate-700 text-white text-xs rounded-lg px-3 py-1.5 focus:outline-none focus:border-sky-500 font-mono"
              >
                {stations.map((st) => (
                  <option key={st.station_id} value={st.station_id}>
                    {st.station_id} — {st.name} ({st.state || 'India'})
                  </option>
                ))}
              </select>
            </div>

            {/* Anomaly Mode Presets Grid (6 Scenarios) */}
            <div>
              <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1 font-mono">
                Select Anomaly Scenario (6 Fault Modes)
              </label>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {FAULT_PRESETS.map((preset) => {
                  const Icon = preset.icon;
                  const isSelected = anomalyType === preset.id;
                  return (
                    <button
                      type="button"
                      key={preset.id}
                      onClick={() => {
                        sounds.playClick();
                        setAnomalyType(preset.id);
                        setParameter(preset.defaultParam);
                        setMagnitude(preset.defaultMag);
                      }}
                      className={`p-2.5 rounded-lg border text-left transition-all flex flex-col justify-between ${
                        isSelected
                          ? 'bg-sky-500/15 border-sky-500 text-white'
                          : 'bg-slate-900/60 border-slate-800 text-slate-400 hover:border-slate-700 hover:text-slate-200'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <Icon className={`w-3.5 h-3.5 ${isSelected ? 'text-sky-400' : 'text-slate-500'}`} />
                        {isSelected && <span className="w-1.5 h-1.5 rounded-full bg-sky-400" />}
                      </div>
                      <div>
                        <span className="text-xs font-semibold block leading-tight text-white">{preset.name}</span>
                        <span className="text-[9px] text-slate-400 line-clamp-1 mt-0.5">{preset.desc}</span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Parameter & Magnitude Inputs */}
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="text-[10px] text-slate-400 font-mono block mb-1">Target Parameter</label>
                <select
                  value={parameter}
                  onChange={(e) => setParameter(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 text-white text-xs rounded-lg px-2.5 py-1.5 font-mono"
                >
                  <option value="temperature_c">Temperature (°C)</option>
                  <option value="pressure_hpa">Pressure (hPa)</option>
                  <option value="humidity_pct">Humidity (%)</option>
                </select>
              </div>

              <div>
                <label className="text-[10px] text-slate-400 font-mono block mb-1">Offset Magnitude (+Δ)</label>
                <input
                  type="number"
                  step="0.1"
                  value={magnitude}
                  onChange={(e) => setMagnitude(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 text-white text-xs rounded-lg px-2.5 py-1.5 font-mono font-bold"
                />
              </div>

              <div>
                <label className="text-[10px] text-slate-400 font-mono block mb-1">Duration (Cycles)</label>
                <input
                  type="number"
                  value={duration}
                  onChange={(e) => setDuration(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 text-white text-xs rounded-lg px-2.5 py-1.5 font-mono font-bold"
                />
              </div>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn-primary w-full py-2.5 text-xs flex items-center justify-center gap-2 font-bold"
          >
            <Play className="w-3.5 h-3.5 fill-white" />
            {loading ? 'Transmitting Fault Scenario...' : 'Execute Anomaly Injection Scenario'}
          </button>
        </form>

        {/* Right Status / Diagnostics Console */}
        <div className="lg:col-span-5 bg-slate-950 border border-slate-800 rounded-xl p-4 flex flex-col justify-between font-mono text-xs overflow-hidden">
          <div>
            <div className="flex items-center justify-between border-b border-slate-800 pb-2 mb-3">
              <span className="text-[11px] text-slate-300 font-bold uppercase tracking-wider flex items-center gap-1.5">
                <Radio className="w-3.5 h-3.5 text-sky-400" />
                Live Ingestion Diagnostics
              </span>
              <span className="w-2 h-2 rounded-full bg-emerald-400" />
            </div>

            <div className="space-y-2 text-slate-300 text-[11px]">
              <div className="flex justify-between">
                <span className="text-slate-500">Telemetry Feed:</span>
                <span className="text-white font-semibold">213k Records (IMD Format)</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Sampling Interval:</span>
                <span className="text-emerald-400 font-semibold">1.0s / cycle</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Payload Security:</span>
                <span className="text-sky-400 font-semibold">HMAC-SHA256 Signed</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Pipeline Mode:</span>
                <span className="text-slate-200 font-semibold">Multi-Detector Ensemble</span>
              </div>
            </div>

            {lastResponse && (
              <div className="mt-4 p-3 rounded-lg bg-slate-900 border border-slate-700 text-slate-200 text-[11px] animate-fadeIn">
                <div className="flex items-center gap-1.5 font-bold mb-1 text-sky-400">
                  <Check className="w-3.5 h-3.5" />
                  {lastResponse.status}
                </div>
                <p className="text-slate-300 font-sans text-xs">{lastResponse.message}</p>
              </div>
            )}
          </div>

          <div className="p-2.5 bg-slate-900 rounded-lg text-[10px] text-slate-400 border border-slate-800 font-sans leading-relaxed">
            💡 <strong className="text-slate-200">Demonstration Guide:</strong> Execute an injection above, then open the <strong>Telemetry Stream</strong> or <strong>Incident Center</strong> tab to observe the real-time detector response and autoencoder value imputation.
          </div>
        </div>
      </div>
    </div>
  );
}
