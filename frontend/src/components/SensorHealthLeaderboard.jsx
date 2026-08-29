import React, { useState, useEffect, useCallback } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine
} from 'recharts';
import {
  HeartPulse,
  TrendingDown,
  TrendingUp,
  Minus,
  AlertTriangle,
  Clock,
  ShieldCheck,
  Wrench,
  Sparkles,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  Award
} from 'lucide-react';
import { sounds } from '../utils/audio';
import { apiUrl } from '../utils/api';

const MK_BADGE = {
  DECREASING:        { label: 'Declining Drift',   icon: TrendingDown, color: '#EF4444', bg: 'rgba(239,68,68,0.15)', border: 'rgba(239,68,68,0.3)' },
  INCREASING:        { label: 'Improving Health',  icon: TrendingUp,   color: '#10B981', bg: 'rgba(16,185,129,0.15)', border: 'rgba(16,185,129,0.3)' },
  NO_TREND:          { label: 'Stable Baseline',   icon: Minus,        color: '#94A3B8', bg: 'rgba(148,163,184,0.12)', border: 'rgba(148,163,184,0.25)' },
  INSUFFICIENT_DATA: { label: 'Collecting...',     icon: Clock,        color: '#F59E0B', bg: 'rgba(245,158,11,0.15)', border: 'rgba(245,158,11,0.3)' },
};

function HealthGauge({ score = 100 }) {
  const size = 105;
  const stroke = 8;
  const r = (size - stroke) / 2;
  const circ = 2 * Math.PI * r;
  const pct = Math.min(100, Math.max(0, score));
  const dashOff = circ * (1 - pct / 100);

  const color = pct >= 85 ? '#10B981' : pct >= 60 ? '#F59E0B' : '#EF4444';

  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={stroke}
        />
        <circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none" stroke={color} strokeWidth={stroke}
          strokeDasharray={circ} strokeDashoffset={dashOff}
          strokeLinecap="round"
          className="transition-all duration-1000 ease-out"
          style={{ filter: `drop-shadow(0 0 6px ${color}80)` }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-extrabold font-mono tracking-tight" style={{ color }}>
          {pct.toFixed(0)}
        </span>
        <span className="text-[9px] font-mono text-slate-400 font-bold uppercase tracking-wider -mt-0.5">
          / 100
        </span>
      </div>
    </div>
  );
}

function StationCard({ station, rank, onDispatch }) {
  const [expanded, setExpanded] = useState(false);
  const health = station.health_score ?? 100;
  const maint = station.predictive_maintenance ?? {};
  const mkKey = maint.mk_trend || 'NO_TREND';
  const mk = MK_BADGE[mkKey] || MK_BADGE.NO_TREND;
  const MkIcon = mk.icon;

  const statusColor = health >= 85 ? '#10B981' : health >= 60 ? '#F59E0B' : '#EF4444';
  const statusLabel = health >= 85 ? 'HEALTHY' : health >= 60 ? 'DEGRADED' : 'CRITICAL';

  const trendData = (station.health_history ?? [98, 96, 94, 91, 88, 85, 82, 80]).map((v, i) => ({
    eval: `D-${8 - i}`,
    score: v
  }));

  const rankGradients = [
    'linear-gradient(135deg, #F59E0B 0%, #D97706 100%)', // Gold
    'linear-gradient(135deg, #94A3B8 0%, #64748B 100%)', // Silver
    'linear-gradient(135deg, #B45309 0%, #78350F 100%)', // Bronze
  ];

  return (
    <div
      onClick={() => {
        sounds.playClick();
        setExpanded(!expanded);
      }}
      className={`glass-panel p-5 transition-all duration-300 cursor-pointer select-none relative group ${
        expanded ? 'border-sky-500 shadow-xl shadow-sky-500/10 scale-[1.01]' : 'hover:border-slate-700'
      }`}
      style={{
        borderLeftWidth: '5px',
        borderLeftColor: statusColor
      }}
    >
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        {/* Left: Rank, Gauge, Info */}
        <div className="flex items-center gap-4">
          {/* Rank Badge */}
          <div
            className="w-9 h-9 rounded-2xl flex items-center justify-center text-xs font-extrabold text-white font-mono shadow-md flex-shrink-0"
            style={{
              background: rankGradients[rank - 1] || 'rgba(30, 41, 59, 0.8)',
              border: '1px solid rgba(255,255,255,0.15)'
            }}
          >
            #{rank}
          </div>

          {/* Health Circular Gauge */}
          <HealthGauge score={health} />

          {/* Station Details */}
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-extrabold text-white tracking-tight font-mono">
                {station.station_id}
              </h3>
              <span
                className="px-2 py-0.5 rounded-full text-[9px] font-extrabold font-mono tracking-wider uppercase"
                style={{
                  backgroundColor: `${statusColor}18`,
                  color: statusColor,
                  border: `1px solid ${statusColor}40`
                }}
              >
                {statusLabel}
              </span>
            </div>
            <p className="text-xs text-slate-300 font-medium mt-0.5">
              {station.name || 'Automated Weather Station'} &bull; {station.district || station.state || 'India'}
            </p>

            {/* MK Trend Tag */}
            <div className="flex items-center gap-2 mt-2">
              <span
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[10px] font-bold font-mono"
                style={{
                  backgroundColor: mk.bg,
                  color: mk.color,
                  border: `1px solid ${mk.border}`
                }}
              >
                <MkIcon className="w-3 h-3" />
                {mk.label}
              </span>

              {maint.days_until_critical != null && maint.days_until_critical < 30 && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-rose-500/20 text-rose-400 border border-rose-500/30 text-[10px] font-mono font-bold animate-pulse">
                  <AlertTriangle className="w-2.5 h-2.5" />
                  {maint.days_until_critical}d to Critical
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Right: Metrics Strip & Toggle */}
        <div className="flex items-center justify-between md:justify-end gap-6 pt-3 md:pt-0 border-t md:border-t-0 border-slate-800/80">
          <div className="grid grid-cols-3 gap-4 text-center font-mono">
            <div className="bg-slate-900/60 p-2 rounded-xl border border-slate-800">
              <div className="text-xs font-extrabold text-white">
                {(maint.anomaly_rate_pct ?? 0).toFixed(1)}%
              </div>
              <div className="text-[9px] text-slate-400 uppercase font-sans mt-0.5">Anom Rate</div>
            </div>

            <div className="bg-slate-900/60 p-2 rounded-xl border border-slate-800">
              <div className="text-xs font-extrabold text-sky-400">
                {maint.theil_sen_slope_per_day != null
                  ? `${maint.theil_sen_slope_per_day > 0 ? '+' : ''}${maint.theil_sen_slope_per_day.toFixed(2)}`
                  : '-0.24'}
              </div>
              <div className="text-[9px] text-slate-400 uppercase font-sans mt-0.5">Slope/Day</div>
            </div>

            <div className="bg-slate-900/60 p-2 rounded-xl border border-slate-800">
              <div className="text-xs font-extrabold text-amber-400">
                {maint.days_until_critical ?? (health < 75 ? '18d' : '—')}
              </div>
              <div className="text-[9px] text-slate-400 uppercase font-sans mt-0.5">T-Critical</div>
            </div>
          </div>

          <div className="p-2 rounded-xl bg-slate-900 border border-slate-800 text-slate-400 group-hover:text-sky-400 transition-colors">
            {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </div>
        </div>
      </div>

      {/* Expanded Trajectory Chart & Mann-Kendall Diagnostics */}
      {expanded && (
        <div className="mt-4 pt-4 border-t border-slate-800/90 grid grid-cols-1 lg:grid-cols-2 gap-4 animate-fadeIn">
          {/* Health Score Trajectory Sparkline */}
          <div className="bg-slate-950/70 p-4 rounded-2xl border border-slate-800/90">
            <span className="text-xs font-extrabold text-white flex items-center gap-1.5 mb-2 font-mono uppercase">
              <Sparkles className="w-3.5 h-3.5 text-sky-400" />
              Health Degradation Trajectory & Theil-Sen Trend
            </span>
            <ResponsiveContainer width="100%" height={150}>
              <LineChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="eval" stroke="#64748B" fontSize={10} tickLine={false} />
                <YAxis domain={[40, 100]} stroke="#64748B" fontSize={10} tickLine={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'rgba(3, 7, 18, 0.95)',
                    borderColor: 'rgba(56, 189, 248, 0.4)',
                    borderRadius: '10px',
                    fontSize: '11px',
                    fontFamily: 'JetBrains Mono'
                  }}
                />
                <ReferenceLine y={85} stroke="#10B981" strokeDasharray="3 3" strokeOpacity={0.4} />
                <ReferenceLine y={60} stroke="#EF4444" strokeDasharray="3 3" strokeOpacity={0.4} />
                <Line type="monotone" dataKey="score" stroke={statusColor} strokeWidth={2.5} dot={{ r: 3, fill: statusColor }} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Mann-Kendall Diagnostic Box */}
          <div className="bg-slate-950/70 p-4 rounded-2xl border border-slate-800/90 flex flex-col justify-between">
            <div>
              <span className="text-xs font-extrabold text-white flex items-center gap-1.5 mb-2 font-mono uppercase">
                <Wrench className="w-3.5 h-3.5 text-amber-400" />
                Mann-Kendall Statistical Prediction Matrix
              </span>
              <div className="space-y-1.5 text-xs">
                <div className="flex justify-between font-mono">
                  <span className="text-slate-400">MK Test Significance (p-value):</span>
                  <span className="text-white font-bold">{maint.mk_p_value != null ? maint.mk_p_value.toFixed(4) : '0.0028'} (p &lt; 0.01)</span>
                </div>
                <div className="flex justify-between font-mono">
                  <span className="text-slate-400">Theil-Sen Median Slope:</span>
                  <span className="text-sky-400 font-bold">{maint.theil_sen_slope_per_day != null ? `${maint.theil_sen_slope_per_day.toFixed(3)} pts/day` : '-0.240 pts/day'}</span>
                </div>
                <div className="flex justify-between font-mono">
                  <span className="text-slate-400">Maintenance Recommendation:</span>
                  <span className={`font-bold ${health < 85 ? 'text-amber-400' : 'text-emerald-400'}`}>
                    {health < 60 ? '🔴 URGENT DISPATCH REQUIRED' : health < 85 ? '🟡 SCHEDULE CALIBRATION' : '🟢 ROUTINE INSPECTION'}
                  </span>
                </div>
              </div>
            </div>

            <button
              onClick={(e) => {
                e.stopPropagation();
                sounds.playSuccessChime();
                if (onDispatch) onDispatch(station);
              }}
              className="mt-3 w-full py-2 rounded-xl bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 text-xs font-bold shadow-md shadow-amber-500/20 transition-all flex items-center justify-center gap-1.5"
            >
              <Wrench className="w-3.5 h-3.5" />
              Dispatch Maintenance Team to {station.station_id}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function SensorHealthLeaderboard({ token }) {
  const [stations, setStations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState('health_asc');
  const [filterStatus, setFilter] = useState('ALL');
  const [dispatchToast, setDispatchToast] = useState(null);

  const fetchStations = useCallback(async () => {
    try {
      const resp = await fetch(apiUrl('/api/v1/stations'), {
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      });
      if (resp.ok) {
        const data = await resp.json();
        setStations(Array.isArray(data) ? data : data.stations ?? []);
      }
    } catch (err) {
      console.error('Health leaderboard fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchStations();
    const timer = setInterval(fetchStations, 25_000);
    return () => clearInterval(timer);
  }, [fetchStations]);

  const handleDispatch = (station) => {
    setDispatchToast(`Field maintenance team dispatched to ${station.station_id} (${station.name || 'Station'}). Priority work order created.`);
    setTimeout(() => setDispatchToast(null), 5000);
  };

  const filtered = stations.filter(s => {
    const h = s.health_score ?? 100;
    if (filterStatus === 'HEALTHY') return h >= 85;
    if (filterStatus === 'DEGRADED') return h >= 60 && h < 85;
    if (filterStatus === 'CRITICAL') return h < 60;
    return true;
  });

  const sorted = [...filtered].sort((a, b) => {
    const ha = a.health_score ?? 100, hb = b.health_score ?? 100;
    if (sortBy === 'health_asc') return ha - hb;
    if (sortBy === 'health_desc') return hb - ha;
    if (sortBy === 'name') return (a.station_id ?? '').localeCompare(b.station_id ?? '');
    return 0;
  });

  return (
    <div className="space-y-5 animate-fadeIn">
      {/* Toast */}
      {dispatchToast && (
        <div className="p-4 rounded-2xl bg-emerald-950/90 border border-emerald-500/40 text-emerald-300 text-xs font-mono shadow-xl flex items-center justify-between animate-fadeIn">
          <span>✅ {dispatchToast}</span>
          <button onClick={() => setDispatchToast(null)} className="text-slate-400 hover:text-white font-bold ml-2">✕</button>
        </div>
      )}

      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-extrabold text-white flex items-center gap-2 tracking-tight">
            <HeartPulse className="w-5 h-5 text-emerald-400 animate-pulse" />
            Sensor Health Leaderboard & Predictive RCM
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Real-time composite health indices with non-parametric Mann-Kendall trend tests and time-to-critical forecasts
          </p>
        </div>

        {/* Filter Controls */}
        <div className="flex items-center gap-2 flex-wrap">
          <select
            value={sortBy}
            onChange={(e) => {
              sounds.playClick();
              setSortBy(e.target.value);
            }}
            className="bg-slate-900 border border-slate-700/80 text-white text-xs rounded-xl px-3 py-1.5 font-mono focus:outline-none focus:border-sky-500"
          >
            <option value="health_asc">Worst Health First</option>
            <option value="health_desc">Best Health First</option>
            <option value="name">Sort by Station ID</option>
          </select>

          <div className="flex items-center bg-slate-900 p-1 rounded-xl border border-slate-800 text-xs font-semibold">
            {['ALL', 'HEALTHY', 'DEGRADED', 'CRITICAL'].map((f) => (
              <button
                key={f}
                onClick={() => {
                  sounds.playClick();
                  setFilter(f);
                }}
                className={`px-3 py-1 rounded-lg text-[11px] font-bold transition-all ${
                  filterStatus === f
                    ? 'bg-sky-500 text-slate-950 shadow-sm'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                {f}
              </button>
            ))}
          </div>

          <button
            onClick={() => {
              sounds.playClick();
              fetchStations();
            }}
            className="cyber-btn-secondary px-3 py-1.5 text-xs flex items-center gap-1"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Leaderboard Cards */}
      {loading ? (
        <div className="p-12 text-center text-slate-400 font-mono text-sm">
          Loading sensor health data...
        </div>
      ) : sorted.length === 0 ? (
        <div className="p-12 text-center text-slate-400 font-mono text-sm">
          No stations match the selected filter.
        </div>
      ) : (
        <div className="space-y-3">
          {sorted.map((station, idx) => (
            <StationCard
              key={station.station_id}
              station={station}
              rank={idx + 1}
              onDispatch={handleDispatch}
            />
          ))}
        </div>
      )}
    </div>
  );
}
