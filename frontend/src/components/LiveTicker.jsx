import React from 'react';
import { Radio, AlertCircle } from 'lucide-react';
import { sounds } from '../utils/audio';

export default function LiveTicker({ stations = [], onSelectStation }) {
  if (!stations || stations.length === 0) return null;

  // Duplicate for seamless infinite marquee loop
  const tickerItems = [...stations, ...stations];

  return (
    <div className="w-full bg-slate-950 border-y border-slate-800/80 overflow-hidden relative py-1.5 select-none z-20">
      {/* Left fixed badge */}
      <div className="absolute left-0 top-0 bottom-0 z-10 px-3 bg-gradient-to-r from-slate-950 via-slate-950/90 to-transparent flex items-center gap-2">
        <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-sky-500/10 border border-sky-500/20 text-[10px] font-semibold text-sky-400 font-mono tracking-wider">
          <Radio className="w-3 h-3 text-sky-400 animate-pulse" />
          STATION STREAM
        </div>
      </div>

      {/* Scrolling ticker track */}
      <div className="animate-marquee flex items-center gap-5 pl-44">
        {tickerItems.map((st, idx) => {
          const r = st.latest_reading || {};
          const isAnom = r.is_anomaly;
          const health = st.health_score ?? 100;
          const statusColor = health >= 85 ? '#10B981' : health >= 60 ? '#F59E0B' : '#EF4444';

          return (
            <div
              key={`${st.station_id}-${idx}`}
              onClick={() => {
                sounds.playClick();
                if (onSelectStation) onSelectStation(st, true);
              }}
              className={`flex items-center gap-3 px-3 py-1 rounded-lg border transition-all cursor-pointer ${
                isAnom
                  ? 'bg-rose-950/30 border-rose-500/40 hover:border-rose-400'
                  : 'bg-slate-900/60 border-slate-800 hover:border-slate-700 hover:bg-slate-800/60'
              }`}
            >
              {/* Station Code & State */}
              <div className="flex items-center gap-1.5">
                <span
                  className="w-1.5 h-1.5 rounded-full"
                  style={{ backgroundColor: statusColor }}
                />
                <span className="font-mono text-xs font-bold text-slate-200">
                  {st.station_id}
                </span>
                <span className="text-[10px] text-slate-400">
                  {st.name ? st.name.split(' ')[0] : ''}
                </span>
              </div>

              {/* Sensor Readings */}
              <div className="flex items-center gap-2 font-mono text-[11px]">
                <span className="text-slate-300">
                  <strong className="text-white">{r.temperature_c != null ? r.temperature_c.toFixed(1) : '—'}</strong>
                  <span className="text-slate-500 text-[9px]">°C</span>
                </span>
                <span className="text-slate-700">|</span>
                <span className="text-slate-300">
                  <strong className="text-white">{r.pressure_hpa != null ? r.pressure_hpa.toFixed(0) : '—'}</strong>
                  <span className="text-slate-500 text-[9px]">hPa</span>
                </span>
                <span className="text-slate-700">|</span>
                <span className="text-slate-300">
                  <strong className="text-white">{r.humidity_pct != null ? r.humidity_pct.toFixed(0) : '—'}</strong>
                  <span className="text-slate-500 text-[9px]">%</span>
                </span>
              </div>

              {/* Status Flag */}
              {isAnom ? (
                <span className="flex items-center gap-1 px-1.5 py-0.2 rounded bg-rose-500/20 text-rose-400 text-[9px] font-bold uppercase font-mono">
                  <AlertCircle className="w-2.5 h-2.5" />
                  FLAGGED
                </span>
              ) : (
                <span className="px-1.5 py-0.2 rounded bg-emerald-500/10 text-emerald-400 text-[9px] font-mono font-medium">
                  {health.toFixed(0)}%
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* Right gradient fade */}
      <div className="absolute right-0 top-0 bottom-0 z-10 w-12 bg-gradient-to-l from-slate-950 to-transparent pointer-events-none" />
    </div>
  );
}
