import React, { useState } from 'react';
import {
  ShieldCheck,
  Activity,
  Cloud,
  User,
  LogOut,
  Sliders,
  Volume2,
  VolumeX,
  Bell,
  BellOff,
  Radio,
  BarChart2,
  Layers,
  Settings,
  HeartPulse,
  Terminal
} from 'lucide-react';
import { sounds } from '../utils/audio';
import { LanguageToggle, useTranslation } from '../i18n';

export default function Header({
  isWsConnected,
  user,
  onOpenLogin,
  onLogout,
  activeTab,
  setActiveTab,
  toastEnabled,
  onToggleToast
}) {
  const { t } = useTranslation();
  const [isMuted, setIsMuted] = useState(sounds.isMuted);

  const handleTabClick = (tabId) => {
    sounds.playClick();
    setActiveTab(tabId);
  };

  const handleSoundToggle = () => {
    const muted = sounds.toggleMute();
    setIsMuted(muted);
  };

  const NAV_ITEMS = [
    { id: 'overview',   label: 'Network Overview', icon: Layers },
    { id: 'telemetry',  label: 'Telemetry Stream', icon: Activity },
    { id: 'alerts',     label: 'Incident Center',  icon: ShieldCheck },
    { id: 'health',     label: 'Station Health',   icon: HeartPulse },
    { id: 'benchmark',  label: 'Model Benchmark',  icon: BarChart2 },
    { id: 'simulator',  label: 'Fault Injector',   icon: Terminal },
    { id: 'admin',      label: 'Calibration',      icon: Settings },
  ];

  return (
    <header className="sticky top-0 z-40 w-full border-b border-[rgba(0,210,255,0.14)] bg-[#08090E]/95 backdrop-blur-md transition-all shadow-[0_4px_20px_rgba(0,0,0,0.5)]">
      <div className="max-w-[1720px] w-full mx-auto px-3 sm:px-6 py-2 flex items-center justify-between gap-3">
        {/* Left: Professional Brand Title */}
        <div
          onClick={() => handleTabClick('overview')}
          className="flex items-center gap-2.5 cursor-pointer group select-none flex-shrink-0"
        >
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#00D2FF] to-[#0088FF] flex items-center justify-center text-[#08090E] shadow-[0_0_14px_rgba(0,210,255,0.4)] flex-shrink-0">
            <Cloud className="w-4 h-4" />
          </div>

          <div className="flex-shrink-0">
            <div className="flex items-center gap-1.5">
              <h1 className="text-sm font-bold tracking-tight text-white font-sans whitespace-nowrap">
                SkyGuard AI
              </h1>
              <span className="px-1.5 py-0.2 rounded bg-slate-900 border border-[#00D2FF]/30 text-[#00D2FF] text-[9px] font-mono font-bold">
                IMD QC
              </span>
            </div>
            <p className="text-[10px] text-slate-400 hidden 2xl:block whitespace-nowrap">
              Surface Weather Telemetry & Anomaly Detection
            </p>
          </div>
        </div>

        {/* Center: Navigation Tabs */}
        <nav className="hidden lg:flex items-center gap-0.5 bg-[#0E111A] p-1 rounded-xl border border-[rgba(0,210,255,0.15)] flex-shrink-0">
          {NAV_ITEMS.map(({ id, label, icon: Icon }) => {
            const isActive = activeTab === id;
            return (
              <button
                key={id}
                onClick={() => handleTabClick(id)}
                className={`px-2.5 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 whitespace-nowrap ${
                  isActive
                    ? 'bg-[#00D2FF] text-[#08090E] font-bold shadow-[0_0_14px_rgba(0,210,255,0.45)]'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{label}</span>
              </button>
            );
          })}
        </nav>

        {/* Right: Operational Controls & Auth */}
        <div className="flex items-center gap-2 flex-shrink-0">
          {/* Toast Notification Toggle */}
          <button
            onClick={onToggleToast}
            title={toastEnabled ? 'Toast popups are ON (Click to Mute)' : 'Toast popups are MUTED (Click to Enable)'}
            className={`p-1.5 rounded-lg border text-xs font-medium flex items-center gap-1.5 transition-all flex-shrink-0 ${
              toastEnabled
                ? 'bg-[#00D2FF]/10 border-[#00D2FF]/30 text-[#00D2FF]'
                : 'bg-slate-900 border-slate-800 text-slate-500 hover:text-slate-300'
            }`}
          >
            {toastEnabled ? <Bell className="w-3.5 h-3.5" /> : <BellOff className="w-3.5 h-3.5" />}
            <span className="hidden 2xl:inline text-[11px] font-sans">
              {toastEnabled ? 'Toasts Active' : 'Toasts Muted'}
            </span>
          </button>

          {/* Sound FX Toggle */}
          <button
            onClick={handleSoundToggle}
            title={isMuted ? 'Audio chime muted' : 'Audio chime active'}
            className={`p-1.5 rounded-lg border text-xs transition-all flex-shrink-0 ${
              isMuted
                ? 'bg-slate-900 border-slate-800 text-slate-500 hover:text-slate-300'
                : 'bg-[#00FFA3]/10 border-[#00FFA3]/30 text-[#00FFA3]'
            }`}
          >
            {isMuted ? <VolumeX className="w-3.5 h-3.5" /> : <Volume2 className="w-3.5 h-3.5" />}
          </button>

          {/* Real-time Connection Status */}
          <div
            className={`flex items-center gap-1.5 px-2 py-1 rounded-lg border text-[10px] font-mono font-medium flex-shrink-0 ${
              isWsConnected
                ? 'bg-[#00FFA3]/10 border-[#00FFA3]/35 text-[#00FFA3]'
                : 'bg-[#FF0055]/10 border-[#FF0055]/35 text-[#FF0055]'
            }`}
          >
            <span
              className="pulse-dot"
              style={{ backgroundColor: isWsConnected ? '#00FFA3' : '#FF0055' }}
            />
            <span className="hidden sm:inline whitespace-nowrap">
              {isWsConnected ? 'LIVE FEED' : 'OFFLINE'}
            </span>
          </div>

          {/* User Account / Auth */}
          {user ? (
            <div className="flex items-center gap-2 pl-2 border-l border-slate-800 flex-shrink-0">
              <div className="text-right hidden sm:block">
                <p className="text-xs font-bold text-white leading-tight font-sans whitespace-nowrap">
                  {user.full_name || user.email.split('@')[0]}
                </p>
                <span className="text-[10px] text-[#00D2FF] uppercase font-mono block font-bold">
                  {user.role}
                </span>
              </div>
              <button
                onClick={() => {
                  sounds.playClick();
                  onLogout();
                }}
                title="Logout"
                className="p-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-[#FF0055] transition-all flex-shrink-0"
              >
                <LogOut className="w-3.5 h-3.5" />
              </button>
            </div>
          ) : (
            <button
              onClick={() => {
                sounds.playClick();
                onOpenLogin();
              }}
              className="btn-primary px-3.5 py-1.5 text-xs flex items-center gap-1.5 whitespace-nowrap flex-shrink-0 shadow-md font-semibold"
            >
              <User className="w-3.5 h-3.5" />
              <span>Operator Login</span>
            </button>
          )}
        </div>
      </div>

      {/* Mobile Navigation Bar */}
      <div className="lg:hidden flex items-center gap-1 px-3 py-1.5 bg-slate-900 border-t border-slate-800 overflow-x-auto">
        {NAV_ITEMS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => handleTabClick(id)}
            className={`px-2.5 py-1 rounded-md text-xs font-medium whitespace-nowrap flex items-center gap-1 ${
              activeTab === id
                ? 'bg-sky-600 text-white font-bold'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Icon className="w-3 h-3" />
            {label}
          </button>
        ))}
      </div>
    </header>
  );
}
