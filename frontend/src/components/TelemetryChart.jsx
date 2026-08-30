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

const CustomTelemetryTooltip = ({ active, payload }) => {
  if (!active || !payload || !payload.length) return null;
  const data = payload[0]?.payload;
  if (!data) return null;

  return (
    <div className="p-3 bg-slate-950/95 border border-sky-500/40 rounded-xl shadow-2xl text-xs font-mono min-w-[240px]">
      <div className="flex items-center justify-between border-b border-slate-800 pb-1.5 mb-2">
        <span className="text-slate-400 font-sans font-semibold">🕒 {data.time}</span>
        {data.is_anomaly ? (
          <span className="px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-400 text-[10px] font-bold border border-rose-500/40 animate-pulse">
            ⚠️ ANOMALY ({data.severity ? Math.round(data.severity * 100) : 85}%)
          </span>
        ) : (
          <span className="px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 text-[10px] font-bold border border-emerald-500/40">
            ✓ NOMINAL
          </span>
        )}
      </div>

      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <span className="text-sky-400 font-sans flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-sky-400" /> Temperature:
          </span>
          <span className="text-white font-bold">{data.temperature != null ? `${Number(data.temperature).toFixed(1)}°C` : '—'}</span>
        </div>

        {data.imputed_temperature != null && data.imputed_temperature !== data.temperature && (
          <div className="flex items-center justify-between text-emerald-400 text-[11px]">
            <span className="font-sans flex items-center gap-1.5">
              <span className="w-2 h-0.5 bg-emerald-400 border-t border-dashed" /> AE Imputed:
            </span>
            <span className="font-bold">{Number(data.imputed_temperature).toFixed(1)}°C</span>
          </div>
        )}

        <div className="flex items-center justify-between">
          <span className="text-indigo-400 font-sans flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-indigo-400" /> Pressure:
          </span>
          <span className="text-white font-bold">{data.pressure != null ? `${Number(data.pressure).toFixed(1)} hPa` : '—'}</span>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-teal-400 font-sans flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-teal-400" /> Humidity:
          </span>
          <span className="text-white font-bold">{data.humidity != null ? `${Number(data.humidity).toFixed(1)}%` : '—'}</span>
        </div>

        {data.dew_point != null && (
          <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1 border-t border-slate-800/80">
            <span className="font-sans">Dew Point:</span>
            <span>{Number(data.dew_point).toFixed(1)}°C</span>
          </div>
        )}
      </div>
    </div>
  );
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

  // Compute live min/max summary based on selected parameter
  let activeValues = [];
  let unit = '°C';
  let rangeLabel = 'Observed Temp:';

  if (selectedParam === 'PRES') {
    activeValues = readings.map(r => r.pressure_hpa).filter(v => v != null);
    unit = ' hPa';
    rangeLabel = 'Pressure Range:';
  } else if (selectedParam === 'RH') {
    activeValues = readings.map(r => r.humidity_pct).filter(v => v != null);
    unit = '%';
    rangeLabel = 'Humidity Range:';
  } else {
    activeValues = readings.map(r => r.temperature_c).filter(v => v != null);
    unit = '°C';
    rangeLabel = 'Observed Temp:';
  }

  const minVal = activeValues.length ? Math.min(...activeValues).toFixed(1) : '—';
  const maxVal = activeValues.length ? Math.max(...activeValues).toFixed(1) : '—';
  const avgVal = activeValues.length ? (activeValues.reduce((a, b) => a + b, 0) / activeValues.length).toFixed(1) : '—';

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
    <div className="glass-panel p-5 flex flex-col h-[580px] relative">
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
              { id: 'ALL', label: 'All' },
              { id: 'TEMP', label: 'Temperature' },
              { id: 'PRES', label: 'Pressure' },
              { id: 'RH', label: 'Humidity' },
            ].map(({ id, label }) => (
              <button
                key={id}
                onClick={() => handleParamChange(id)}
                className={`px-3 py-1 rounded-lg font-bold transition-all ${
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
        <span className="text-[11px] text-slate-400 uppercase font-sans">{rangeLabel}</span>
        <span>Min: <strong className="text-sky-400">{minVal}{unit}</strong></span>
        <span className="text-slate-700">|</span>
        <span>Avg: <strong className="text-emerald-400">{avgVal}{unit}</strong></span>
        <span className="text-slate-700">|</span>
        <span>Max: <strong className="text-amber-400">{maxVal}{unit}</strong></span>
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
            <ComposedChart data={chartData} margin={{ top: 10, right: 15, left: -10, bottom: 0 }}>
              <defs>
                <linearGradient id="tempGlow" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#38BDF8" stopOpacity={0.2} />
                  <stop offset="100%" stopColor="#38BDF8" stopOpacity={0.0} />
                </linearGradient>
                <linearGradient id="presGlow" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#818CF8" stopOpacity={0.2} />
                  <stop offset="100%" stopColor="#818CF8" stopOpacity={0.0} />
                </linearGradient>
                <linearGradient id="rhGlow" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#2DD4BF" stopOpacity={0.2} />
                  <stop offset="100%" stopColor="#2DD4BF" stopOpacity={0.0} />
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

              {/* Left Y Axis: Temp (in ALL or TEMP mode) */}
              {(selectedParam === 'ALL' || selectedParam === 'TEMP') && (
                <YAxis
                  yAxisId="left"
                  stroke="#38BDF8"
                  fontSize={11}
                  domain={['auto', 'auto']}
                  tickFormatter={(v) => `${Number(v).toFixed(1)}°C`}
                />
              )}

              {/* Dedicated Left Y Axis when viewing Pressure alone */}
              {selectedParam === 'PRES' && (
                <YAxis
                  yAxisId="left"
                  stroke="#818CF8"
                  fontSize={11}
                  domain={['auto', 'auto']}
                  tickFormatter={(v) => `${Number(v).toFixed(1)} hPa`}
                />
              )}

              {/* Dedicated Left Y Axis when viewing Humidity alone */}
              {selectedParam === 'RH' && (
                <YAxis
                  yAxisId="left"
                  stroke="#2DD4BF"
                  fontSize={11}
                  domain={[0, 100]}
                  tickFormatter={(v) => `${Number(v).toFixed(0)}%`}
                />
              )}

              {/* Right Y Axis: Pressure (in ALL mode) */}
              {selectedParam === 'ALL' && (
                <YAxis
                  yAxisId="right-pres"
                  orientation="right"
                  stroke="#818CF8"
                  fontSize={11}
                  domain={['auto', 'auto']}
                  tickFormatter={(v) => `${Number(v).toFixed(1)} hPa`}
                />
              )}

              {/* Right Y Axis: RH (in ALL mode, scaled 0-100%) */}
              {selectedParam === 'ALL' && (
                <YAxis
                  yAxisId="right-rh"
                  orientation="right"
                  stroke="#2DD4BF"
                  fontSize={10}
                  domain={[0, 100]}
                  hide={true}
                />
              )}

              <Tooltip content={<CustomTelemetryTooltip />} />
              <Legend verticalAlign="top" height={32} iconType="circle" />

              {/* Area Glow fills for dedicated single-channel views */}
              {selectedParam === 'TEMP' && (
                <Area
                  yAxisId="left"
                  type="monotone"
                  dataKey="temperature"
                  fill="url(#tempGlow)"
                  stroke="none"
                  legendType="none"
                />
              )}
              {selectedParam === 'PRES' && (
                <Area
                  yAxisId="left"
                  type="monotone"
                  dataKey="pressure"
                  fill="url(#presGlow)"
                  stroke="none"
                  legendType="none"
                />
              )}
              {selectedParam === 'RH' && (
                <Area
                  yAxisId="left"
                  type="monotone"
                  dataKey="humidity"
                  fill="url(#rhGlow)"
                  stroke="none"
                  legendType="none"
                />
              )}

              {/* 1. Temperature Observed Curve */}
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

              {/* 2. AE Imputed Temperature */}
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

              {/* 3. Barometric Pressure Curve */}
              {(selectedParam === 'ALL' || selectedParam === 'PRES') && (
                <Line
                  yAxisId={selectedParam === 'PRES' ? 'left' : 'right-pres'}
                  type="monotone"
                  dataKey="pressure"
                  name="Pressure (hPa)"
                  stroke="#818CF8"
                  strokeWidth={2}
                  dot={selectedParam === 'PRES' ? renderInjectedFaultDot : false}
                  activeDot={{ r: 5, fill: '#818CF8', stroke: '#FFF', strokeWidth: 2 }}
                />
              )}

              {/* 4. AE Imputed Pressure */}
              {selectedParam === 'PRES' && (
                <Line
                  yAxisId="left"
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

              {/* 5. Humidity Curve */}
              {(selectedParam === 'ALL' || selectedParam === 'RH') && (
                <Line
                  yAxisId={selectedParam === 'RH' ? 'left' : 'right-rh'}
                  type="monotone"
                  dataKey="humidity"
                  name="Relative Humidity (%)"
                  stroke="#2DD4BF"
                  strokeWidth={2}
                  dot={selectedParam === 'RH' ? renderInjectedFaultDot : false}
                  activeDot={{ r: 5, fill: '#2DD4BF', stroke: '#FFF', strokeWidth: 2 }}
                />
              )}

              {/* 6. AE Imputed Humidity */}
              {selectedParam === 'RH' && (
                <Line
                  yAxisId="left"
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
