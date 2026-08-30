import React, { useState, useEffect, useRef } from 'react';
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
  Sliders,
  Activity,
  ShieldAlert,
  ArrowRight
} from 'lucide-react';
import api from '../utils/api';
import { sounds } from '../utils/audio';

export default function SimulatorPanel({ stations = [], onInjectSuccess, onTabChange }) {
  const [stationId, setStationId] = useState('AWS-DEL-01');
  const [anomalyType, setAnomalyType] = useState('SPIKE');
  const [parameter, setParameter] = useState('temperature_c');
  const [magnitude, setMagnitude] = useState(25.0);
  const [duration, setDuration] = useState(10);
  const [loading, setLoading] = useState(false);
  const [lastResponse, setLastResponse] = useState(null);
  // Blueprint §8.4: Live countdown state after injection fires
  const [countdownMax, setCountdownMax] = useState(0);
  const [countdownLeft, setCountdownLeft] = useState(0);
  const countdownRef = useRef(null);

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
      // Blueprint §8.4: Start live countdown
      const ticks = parseInt(duration) || 10;
      setCountdownMax(ticks);
      setCountdownLeft(ticks);
      if (countdownRef.current) clearInterval(countdownRef.current);
      countdownRef.current = setInterval(() => {
        setCountdownLeft(prev => {
          if (prev <= 1) { clearInterval(countdownRef.current); return 0; }
          return prev - 1;
        });
      }, 2000); // 1 tick = 1 simulator cycle = ~2s
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

            {/* Blueprint §8.4: Live Countdown + Quick-Jump Buttons after injection */}
            {lastResponse && (
              <div className="mt-4 animate-fadeIn space-y-3">
                {/* Status Banner */}
                <div className="p-3 rounded-lg bg-slate-900 border border-emerald-500/40">
                  <div className="flex items-center gap-1.5 font-bold mb-1 text-emerald-400 text-[11px]">
                    <Check className="w-3.5 h-3.5" />
                    {lastResponse.status || 'INJECTION ARMED'}
                  </div>
                  <p className="text-slate-300 font-sans text-[11px] leading-relaxed">{lastResponse.message}</p>
                </div>

                {/* Countdown Progress Bar */}
                {countdownLeft > 0 ? (
                  <div className="p-3 rounded-lg bg-slate-900 border border-amber-500/30">
                    <div className="flex justify-between items-center mb-1.5">
                      <span className="text-[10px] text-amber-400 font-bold uppercase">Fault Active</span>
                      <span className="text-[10px] text-amber-300 font-mono font-bold">{countdownLeft} / {countdownMax} cycles</span>
                    </div>
                    <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                      <div
                        className="h-2 rounded-full bg-gradient-to-r from-amber-500 to-rose-500 transition-all duration-1000"
                        style={{ width: `${(countdownLeft / countdownMax) * 100}%` }}
                      />
                    </div>
                    <p className="text-[9px] text-slate-500 mt-1.5 font-sans">Anomaly injection active — detector ensemble evaluating each cycle</p>
                  </div>
                ) : countdownMax > 0 ? (
                  <div className="p-2.5 rounded-lg bg-emerald-950/40 border border-emerald-500/30 text-emerald-400 text-[10px] font-bold text-center">
                    ✅ Injection Complete — Detectors should have flagged the event
                  </div>
                ) : null}

                {/* Quick-Jump Navigation — Blueprint §8.4 Demo Loop */}
                <div className="space-y-1.5">
                  <p className="text-[9px] text-slate-500 font-sans uppercase tracking-wider">Watch the detection pipeline:</p>
                  <button
                    onClick={() => { sounds.playClick(); onTabChange && onTabChange('telemetry'); }}
                    className="w-full flex items-center justify-between px-3 py-2 rounded-xl bg-sky-500/10 border border-sky-500/30 text-sky-400 text-[11px] font-bold hover:bg-sky-500/25 transition-all"
                  >
                    <span className="flex items-center gap-1.5"><Activity className="w-3.5 h-3.5" /> Watch Telemetry Stream</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => { sounds.playClick(); onTabChange && onTabChange('alerts'); }}
                    className="w-full flex items-center justify-between px-3 py-2 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-[11px] font-bold hover:bg-rose-500/25 transition-all"
                  >
                    <span className="flex items-center gap-1.5"><ShieldAlert className="w-3.5 h-3.5" /> Inspect Incident Center</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            )}
          </div>

          {!lastResponse && (
            <div className="p-2.5 bg-slate-900 rounded-lg text-[10px] text-slate-400 border border-slate-800 font-sans leading-relaxed">
              💡 <strong className="text-slate-200">Demonstration Guide:</strong> Select a fault type above, set duration &amp; magnitude, then execute. Use the jump buttons that appear to follow the real-time detection loop.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
