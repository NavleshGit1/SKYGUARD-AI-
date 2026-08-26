import React, { useState } from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid
} from 'recharts';
import {
  Activity,
  Thermometer,
  Wind,
  Droplets,
  Sparkles,
  Download,
  Clock,
  CheckCircle2,
  AlertTriangle
} from 'lucide-react';
import { sounds } from '../utils/audio';

// Crisp solid red dot ONLY rendered on injected fault / anomaly readings
const renderInjectedFaultDot = (props) => {
  const { cx, cy, payload } = props;
  if (!cx || !cy) return null;
  if (payload && payload.is_anomaly) {
    return (
      <circle
        key={`fault-dot-${cx}-${cy}`}
        cx={cx}
        cy={cy}
        r={5}
        fill="#EF4444"
        stroke="#FFFFFF"
        strokeWidth={1.5}
      />
    );
  }
  return null;
};

export default function TelemetryChart({ stations = [], selectedStation, onSelectStation, readings = [] }) {
  const [selectedParam, setSelectedParam] = useState('ALL'); // ALL, TEMP, PRES, RH

  // Format data for recharts
  const chartData = readings.map((r) => {
    const rawTemp = r.temperature_c;
    const rawPres = r.pressure_hpa;
    const rawRh = r.humidity_pct;

    // Continuous AE baseline across all 3 channels:
    const impTemp = (r.imputed_temperature_c != null) ? r.imputed_temperature_c : rawTemp;
    const impPres = (r.imputed_pressure_hpa != null) ? r.imputed_pressure_hpa : rawPres;
    const impRh = (r.imputed_humidity_pct != null) ? r.imputed_humidity_pct : rawRh;

    return {
      time: new Date(r.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      temperature: rawTemp,
      imputed_temperature: impTemp,
      pressure: rawPres,
      imputed_pressure: impPres,
      humidity: rawRh,
      imputed_humidity: impRh,
      dew_point: r.dew_point_c,
      sea_level_pressure: r.sea_level_pressure_hpa,
      is_anomaly: r.is_anomaly,
      severity: r.severity_score,
      imputed: r.is_imputed
    };
  }).reverse();

  // Compute live min/max summary
  const temps = readings.map(r => r.temperature_c).filter(v => v != null);
  const minTemp = temps.length ? Math.min(...temps).toFixed(1) : '—';
  const maxTemp = temps.length ? Math.max(...temps).toFixed(1) : '—';
  const avgTemp = temps.length ? (temps.reduce((a, b) => a + b, 0) / temps.length).toFixed(1) : '—';

  const exportCSV = () => {
    sounds.playClick();
    if (!readings.length) return;
    const headers = [
      "timestamp",
      "temperature_c", "imputed_temperature_c",
      "pressure_hpa", "imputed_pressure_hpa",
      "humidity_pct", "imputed_humidity_pct",
      "dew_point_c", "is_anomaly", "is_imputed"
    ];
    const rows = readings.map(r => [
      r.timestamp,
      r.temperature_c, r.imputed_temperature_c,
      r.pressure_hpa, r.imputed_pressure_hpa,
      r.humidity_pct, r.imputed_humidity_pct,
      r.dew_point_c,
      r.is_anomaly,
      r.is_imputed
    ]);
    const csvContent = "data:text/csv;charset=utf-8," + [headers.join(","), ...rows.map(e => e.join(","))].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `telemetry_${selectedStation?.station_id || 'AWS'}_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleParamChange = (param) => {
    sounds.playClick();
    setSelectedParam(param);
  };

  return (
    <div className="glass-panel p-5 flex flex-col h-[560px] relative">
      {/* Header & Filter Controls */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 mb-3 pb-2 border-b border-slate-800/80">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <Activity className="w-4 h-4 text-sky-400" />
              High-Precision Telemetry & Imputation Engine
            </h2>
            <span className="glass-badge text-emerald-400 border-emerald-500/30 text-[10px] font-mono font-bold">
              {selectedStation?.station_id || 'AWS-DEL-01'}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Real-time physical telemetry curves with Autoencoder self-healing for Temperature, Pressure, and Humidity
          </p>
        </div>

        {/* Station, Parameter & Export Controls */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* Station Selector */}
          <select
            value={selectedStation?.station_id || ''}
            onChange={(e) => {
              sounds.playClick();
              const st = stations.find((s) => s.station_id === e.target.value);
              if (st) onSelectStation(st);
            }}
            className="bg-slate-900/90 border border-slate-700/80 text-white text-xs rounded-xl px-3 py-1.5 focus:outline-none focus:border-sky-500 font-mono font-semibold shadow-inner"
          >
            {stations.map((st) => (
              <option key={st.station_id} value={st.station_id} className="bg-slate-950 text-white">
                {st.station_id} — {st.name}
              </option>
            ))}
          </select>

          {/* Parameter Tabs */}
          <div className="flex items-center bg-slate-900/90 p-1 rounded-xl border border-slate-800 text-xs">
            {[
              { id: 'ALL', label: 'All Sensors' },
              { id: 'TEMP', label: 'Temp' },
              { id: 'PRES', label: 'Pres' },
              { id: 'RH', label: 'Humidity' },
            ].map(({ id, label }) => (
              <button
                key={id}
                onClick={() => handleParamChange(id)}
                className={`px-2.5 py-1 rounded-lg font-bold transition-all ${
                  selectedParam === id
                    ? 'bg-sky-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Export CSV */}
          <button
            onClick={exportCSV}
            title="Export CSV Telemetry"
            className="btn-secondary px-2.5 py-1.5 text-xs flex items-center gap-1.5"
          >
            <Download className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Export</span>
          </button>
        </div>
      </div>

      {/* Mini Stats Banner */}
      <div className="flex items-center gap-4 px-3 py-1.5 rounded-xl bg-slate-900/40 border border-slate-800/80 mb-2 text-xs font-mono text-slate-300">
        <span className="text-[11px] text-slate-400 uppercase font-sans">Observed Range:</span>
        <span>Min: <strong className="text-sky-400">{minTemp}°C</strong></span>
        <span className="text-slate-700">|</span>
        <span>Avg: <strong className="text-emerald-400">{avgTemp}°C</strong></span>
        <span className="text-slate-700">|</span>
        <span>Max: <strong className="text-amber-400">{maxTemp}°C</strong></span>
        <div className="ml-auto flex items-center gap-3 text-[10px]">
          <span className="flex items-center gap-1 text-emerald-400">
            <span className="w-2 h-0.5 bg-emerald-400 border-t border-dashed" /> Dashed = AE Imputed (Self-Healed)
          </span>
          <span className="flex items-center gap-1 text-rose-400">
            <span className="w-2 h-2 rounded-full bg-rose-500" /> Red Dot = Injected Fault
          </span>
        </div>
      </div>

      {/* Chart Canvas */}
      <div className="flex-1 w-full relative">
        {chartData.length === 0 ? (
          <div className="h-full flex items-center justify-center text-slate-500 text-sm font-mono">
            Waiting for telemetry stream from {selectedStation?.name || 'station'}...
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={chartData} margin={{ top: 10, right: 15, left: -15, bottom: 0 }}>
              <defs>
                <linearGradient id="tempGlow" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#38BDF8" stopOpacity={0.25} />
                  <stop offset="100%" stopColor="#38BDF8" stopOpacity={0.0} />
                </linearGradient>
              </defs>

              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />

              <XAxis
                dataKey="time"
                stroke="#64748B"
                fontSize={10}
                tickLine={false}
                axisLine={{ stroke: 'rgba(255, 255, 255, 0.1)' }}
              />

              {/* Left Y Axis: Temp */}
              {(selectedParam === 'ALL' || selectedParam === 'TEMP') && (
                <YAxis
                  yAxisId="left"
                  stroke="#38BDF8"
                  fontSize={11}
                  domain={['auto', 'auto']}
                  tickFormatter={(v) => `${Number(v).toFixed(1)}°C`}
                />
              )}

              {/* Right Y Axis: Pressure */}
              {(selectedParam === 'ALL' || selectedParam === 'PRES') && (
                <YAxis
                  yAxisId="right-pres"
                  orientation="right"
                  stroke="#818CF8"
                  fontSize={11}
                  domain={['auto', 'auto']}
                  tickFormatter={(v) => `${Number(v).toFixed(1)}hPa`}
                />
              )}

              {/* Right Y Axis: RH */}
              {selectedParam === 'RH' && (
                <YAxis
                  yAxisId="right-rh"
                  orientation="right"
                  stroke="#2DD4BF"
                  fontSize={11}
                  domain={[0, 100]}
                  tickFormatter={(v) => `${v}%`}
                />
              )}

              <Tooltip
                contentStyle={{
                  backgroundColor: 'rgba(3, 7, 18, 0.95)',
                  borderColor: 'rgba(56, 189, 248, 0.4)',
                  borderRadius: '12px',
                  boxShadow: '0 15px 35px rgba(0,0,0,0.8), 0 0 15px rgba(56, 189, 248, 0.2)',
                  fontSize: '12px',
                  fontFamily: 'JetBrains Mono, monospace'
                }}
              />
              <Legend verticalAlign="top" height={32} iconType="circle" />

              {/* Temperature Area Glow (legendType="none" prevents extra duplicate label in legend) */}
              {(selectedParam === 'ALL' || selectedParam === 'TEMP') && (
                <Area
                  yAxisId="left"
                  type="monotone"
                  dataKey="temperature"
                  fill="url(#tempGlow)"
                  stroke="none"
                  legendType="none"
                />
              )}

              {/* 1. Temperature Observed Curve (Cyan with Red Dot on Injected Fault) */}
              {(selectedParam === 'ALL' || selectedParam === 'TEMP') && (
                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey="temperature"
                  name="Temperature (°C)"
                  stroke="#38BDF8"
                  strokeWidth={2.5}
                  dot={renderInjectedFaultDot}
                  activeDot={{ r: 5, fill: '#38BDF8', stroke: '#FFF', strokeWidth: 2 }}
                />
              )}

              {/* 2. AE Imputed Temperature (Dashed Green Trace) */}
              {(selectedParam === 'ALL' || selectedParam === 'TEMP') && (
                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey="imputed_temperature"
                  name="AE Imputed Temp (°C)"
                  stroke="#10B981"
                  strokeWidth={2.4}
                  strokeDasharray="5 5"
                  dot={false}
                  activeDot={{ r: 4, fill: '#10B981', stroke: '#FFF', strokeWidth: 1.5 }}
                />
              )}

              {/* 3. Barometric Pressure Curve (Purple with Red Dot on Injected Fault) */}
              {(selectedParam === 'ALL' || selectedParam === 'PRES') && (
                <Line
                  yAxisId="right-pres"
                  type="monotone"
                  dataKey="pressure"
                  name="Pressure (hPa)"
                  stroke="#818CF8"
                  strokeWidth={2}
                  dot={selectedParam === 'PRES' ? renderInjectedFaultDot : false}
                  activeDot={{ r: 5, fill: '#818CF8', stroke: '#FFF', strokeWidth: 2 }}
                />
              )}

              {/* 4. AE Imputed Pressure (Dashed Green Trace when viewing Pressure) */}
              {selectedParam === 'PRES' && (
                <Line
                  yAxisId="right-pres"
                  type="monotone"
                  dataKey="imputed_pressure"
                  name="AE Imputed Pres (hPa)"
                  stroke="#10B981"
                  strokeWidth={2.4}
                  strokeDasharray="5 5"
                  dot={false}
                  activeDot={{ r: 4, fill: '#10B981', stroke: '#FFF', strokeWidth: 1.5 }}
                />
              )}

              {/* 5. Humidity Curve (Teal with Red Dot on Injected Fault) */}
              {(selectedParam === 'ALL' || selectedParam === 'RH') && (
                <Line
                  yAxisId={selectedParam === 'RH' ? 'right-rh' : 'left'}
                  type="monotone"
                  dataKey="humidity"
                  name="Relative Humidity (%)"
                  stroke="#2DD4BF"
                  strokeWidth={2}
                  dot={selectedParam === 'RH' ? renderInjectedFaultDot : false}
                  activeDot={{ r: 5, fill: '#2DD4BF', stroke: '#FFF', strokeWidth: 2 }}
                />
              )}

              {/* 6. AE Imputed Humidity (Dashed Green Trace when viewing Humidity) */}
              {selectedParam === 'RH' && (
                <Line
                  yAxisId="right-rh"
                  type="monotone"
                  dataKey="imputed_humidity"
                  name="AE Imputed Humidity (%)"
                  stroke="#10B981"
                  strokeWidth={2.4}
                  strokeDasharray="5 5"
                  dot={false}
                  activeDot={{ r: 4, fill: '#10B981', stroke: '#FFF', strokeWidth: 1.5 }}
                />
              )}
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
