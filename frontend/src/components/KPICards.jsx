import React from 'react';
import { Radio, Activity, AlertTriangle, ShieldCheck, Cpu } from 'lucide-react';
import { sounds } from '../utils/audio';

function MiniSparkline({ color = '#38BDF8', height = 28 }) {
  return (
    <svg className="w-full opacity-15 pointer-events-none" height={height} viewBox="0 0 100 25" preserveAspectRatio="none">
      <path
        d="M0,16 Q18,6 35,13 T70,8 T88,17 T100,5 L100,25 L0,25 Z"
        fill={`url(#spark-grad-${color.replace('#','')})`}
      />
      <path
        d="M0,16 Q18,6 35,13 T70,8 T88,17 T100,5"
        fill="none"
        stroke={color}
        strokeWidth="1.5"
      />
      <defs>
        <linearGradient id={`spark-grad-${color.replace('#','')}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.8" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
    </svg>
  );
}

export default function KPICards({ stations = [], anomalies = [] }) {
  const totalStations = stations.length || 5;
  const healthyStations = stations.filter(s => (s.health_score ?? 100) >= 85).length;
  const degradedStations = stations.filter(s => (s.health_score ?? 100) >= 60 && (s.health_score ?? 100) < 85).length;
  const criticalStations = stations.filter(s => (s.health_score ?? 100) < 60).length;
  const activeAlerts = anomalies.filter(a => a.status === 'ACTIVE').length;

  const avgHealth = Math.round(
    stations.reduce((acc, s) => acc + (s.health_score || 100), 0) / Math.max(1, totalStations)
  );

  const CARDS = [
    {
      id: 'network',
      title: 'Reporting Stations',
      value: totalStations,
      unit: 'ONLINE',
      subtext: 'Surface Observation Hubs',
      icon: Radio,
      color: '#00D2FF',
      badge: 'CONNECTED',
      badgeColor: '#00D2FF',
    },
    {
      id: 'health',
      title: 'Composite Health',
      value: `${avgHealth}%`,
      unit: 'INDEX',
      subtext: 'Mann-Kendall Monitored',
      icon: ShieldCheck,
      color: '#00FFA3',
      badge: avgHealth >= 85 ? 'OPTIMAL' : 'ATTENTION',
      badgeColor: avgHealth >= 85 ? '#00FFA3' : '#F59E0B',
      progressBar: avgHealth,
    },
    {
      id: 'nominal',
      title: 'Nominal State',
      value: healthyStations,
      unit: `/ ${totalStations}`,
      subtext: 'Health ≥ 85 (Zero Faults)',
      icon: Activity,
      color: '#00FFA3',
      badge: 'STABLE',
      badgeColor: '#00FFA3',
    },
    {
      id: 'degraded',
      title: 'Degraded / Drift',
      value: degradedStations + criticalStations,
      unit: 'WARNINGS',
      subtext: criticalStations > 0 ? `${criticalStations} Action Required` : 'Within Normal Bounds',
      icon: AlertTriangle,
      color: degradedStations + criticalStations > 0 ? '#F59E0B' : '#94A3B8',
      badge: criticalStations > 0 ? 'CRITICAL' : 'NOMINAL',
      badgeColor: criticalStations > 0 ? '#FF0055' : '#64748B',
    },
    {
      id: 'alerts',
      title: 'Active Incidents',
      value: activeAlerts,
      unit: 'FLAGS',
      subtext: 'Real-Time Anomaly Stream',
      icon: Cpu,
      color: activeAlerts > 0 ? '#FF0055' : '#00D2FF',
      badge: activeAlerts > 0 ? 'INVESTIGATE' : 'SECURE',
      badgeColor: activeAlerts > 0 ? '#FF0055' : '#00FFA3',
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5">
      {CARDS.map((card) => {
        const Icon = card.icon;
        return (
          <div
            key={card.id}
            onClick={() => sounds.playClick()}
            className="glass-panel p-4 flex flex-col justify-between relative select-none cursor-pointer transition-all duration-200 hover:border-slate-700"
          >
            {/* Top row */}
            <div className="flex items-center justify-between z-10">
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider font-mono">
                {card.title}
              </span>
              <div
                className="p-1.5 rounded-lg"
                style={{
                  backgroundColor: `${card.color}15`,
                  color: card.color,
                }}
              >
                <Icon className="w-3.5 h-3.5" />
              </div>
            </div>

            {/* Metric Value */}
            <div className="mt-3 z-10">
              <div className="flex items-baseline gap-2">
                <span
                  className="text-2xl font-bold font-mono tracking-tight"
                  style={{ color: card.color }}
                >
                  {card.value}
                </span>
                <span className="text-[10px] font-semibold text-slate-400 font-mono uppercase">
                  {card.unit}
                </span>
              </div>

              {/* Progress bar for health index */}
              {card.progressBar != null && (
                <div className="w-full bg-slate-800 h-1.5 rounded-full mt-2 overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-500 ease-out"
                    style={{
                      width: `${card.progressBar}%`,
                      backgroundColor: card.progressBar >= 85 ? '#10B981' : '#F59E0B'
                    }}
                  />
                </div>
              )}

              {/* Status footer with badge */}
              <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-800/60 text-[11px]">
                <span className="text-slate-400 truncate max-w-[120px] text-[10px]">
                  {card.subtext}
                </span>
                <span
                  className="px-1.5 py-0.2 rounded text-[9px] font-bold font-mono uppercase tracking-wider"
                  style={{
                    backgroundColor: `${card.badgeColor}15`,
                    color: card.badgeColor,
                    border: `1px solid ${card.badgeColor}30`,
                  }}
                >
                  {card.badge}
                </span>
              </div>
            </div>

            {/* Bottom Sparkline */}
            <div className="absolute bottom-0 left-0 right-0 z-0">
              <MiniSparkline color={card.color} height={28} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
