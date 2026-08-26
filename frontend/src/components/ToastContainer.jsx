import React from 'react';
import { AlertCircle, X, ArrowRight } from 'lucide-react';
import { sounds } from '../utils/audio';

export default function ToastContainer({ toasts = [], onDismiss, onInspect }) {
  if (!toasts || toasts.length === 0) return null;

  return (
    <div className="fixed bottom-5 right-5 z-50 flex flex-col gap-2.5 max-w-sm w-full pointer-events-none">
      {toasts.map((t) => (
        <div
          key={t.id || t.event_id}
          className="pointer-events-auto p-3.5 rounded-xl bg-slate-900/95 border border-slate-700 shadow-xl backdrop-blur-md animate-slideInRight flex flex-col gap-1.5"
          style={{ borderLeft: '4px solid #EF4444' }}
        >
          {/* Header */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="p-1 rounded-md bg-rose-500/20 text-rose-400">
                <AlertCircle className="w-3.5 h-3.5" />
              </span>
              <span className="font-mono text-xs font-bold text-white">{t.station_id}</span>
              <span className="px-1.5 py-0.2 rounded bg-rose-500/10 text-rose-400 text-[10px] font-mono font-semibold">
                ANOMALY FLAGGED
              </span>
            </div>

            <button
              onClick={() => {
                sounds.playClick();
                onDismiss(t.id || t.event_id);
              }}
              className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Body */}
          <p className="text-xs text-slate-300 line-clamp-2 leading-relaxed">
            {t.explanation || t.root_cause || 'Physical parameter outlier flagged by detector ensemble.'}
          </p>

          {/* Footer */}
          <div className="flex items-center justify-between pt-1 mt-0.5 border-t border-slate-800 text-[11px]">
            <span className="text-slate-400 font-mono text-[10px]">
              {new Date(t.timestamp || Date.now()).toLocaleTimeString()}
            </span>
            <button
              onClick={() => {
                sounds.playClick();
                if (onInspect) onInspect(t);
                onDismiss(t.id || t.event_id);
              }}
              className="flex items-center gap-1 font-semibold text-sky-400 hover:text-sky-300 transition-colors"
            >
              Inspect Diagnostic <ArrowRight className="w-3 h-3" />
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
