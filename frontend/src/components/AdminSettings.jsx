import React, { useState, useEffect, useCallback } from 'react';
import {
  Settings,
  Sliders,
  ShieldCheck,
  RefreshCw,
  Cpu,
  Search,
  CheckCircle2,
  AlertTriangle,
  FileCheck2,
  Save,
  RotateCcw,
  Sparkles,
  Lock
} from 'lucide-react';
import { sounds } from '../utils/audio';
import api from '../utils/api';

function SliderRow({ label, description, value, min, max, step = 0.01, unit = '', onChange }) {
  const pct = ((value - min) / (max - min)) * 100;
  return (
    <div className="bg-slate-900/60 p-4 rounded-2xl border border-slate-800/80 transition-all hover:border-slate-700">
      <div className="flex items-center justify-between mb-2">
        <div>
          <div className="text-xs font-extrabold text-white uppercase font-mono tracking-tight">{label}</div>
          {description && <div className="text-[11px] text-slate-400 font-sans mt-0.5">{description}</div>}
        </div>
        <div className="text-base font-extrabold font-mono text-sky-400 bg-sky-500/10 px-2.5 py-1 rounded-lg border border-sky-500/20">
          {typeof value === 'number' ? value.toFixed(step < 1 ? 2 : 0) : value}{unit}
        </div>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-sky-400"
        style={{
          background: `linear-gradient(to right, #38BDF8 0%, #38BDF8 ${pct}%, #1E293B ${pct}%, #1E293B 100%)`
        }}
      />
      <div className="flex justify-between text-[9px] font-mono text-slate-400 mt-1">
        <span>{min}{unit}</span>
        <span>{max}{unit}</span>
      </div>
    </div>
  );
}

function AuditTrailViewer({ token }) {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [verified, setVerified] = useState(null);
  const [page, setPage] = useState(1);
  const PER_PAGE = 10;

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await api.get('/api/v1/audit?limit=100&skip=0');
      const data = resp.data;
      setLogs(Array.isArray(data) ? data : data?.logs ?? []);
    } catch (e) {
      console.warn('Could not fetch audit logs:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  const verifyIntegrity = async () => {
    sounds.playClick();
    try {
      const resp = await api.get('/api/v1/audit/verify');
      sounds.playSuccessChime();
      setVerified(resp.data);
    } catch (e) {
      setVerified({ status: 'ERROR', message: String(e?.response?.data?.detail || e.message || e) });
    }
  };

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  const paginated = logs.slice((page - 1) * PER_PAGE, page * PER_PAGE);

  return (
    <div className="mt-8 pt-6 border-t border-slate-800/80">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <div>
          <h3 className="text-base font-extrabold text-white flex items-center gap-2 tracking-tight">
            <Lock className="w-4 h-4 text-violet-400" />
            Cryptographic Audit Trail (SHA-256 Hash Chain)
          </h3>
          <p className="text-xs text-slate-400">
            Append-only, immutable forensic ledger of all operator actions and threshold adjustments
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={verifyIntegrity}
            className="px-3.5 py-1.5 rounded-xl bg-violet-500/20 text-violet-300 border border-violet-500/40 text-xs font-bold font-mono hover:bg-violet-500 hover:text-white transition-all flex items-center gap-1.5"
          >
            <Search className="w-3.5 h-3.5" />
            Verify Hash Integrity
          </button>
          <button
            onClick={() => {
              sounds.playClick();
              fetchLogs();
            }}
            className="cyber-btn-secondary px-3 py-1.5 text-xs flex items-center gap-1"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </button>
        </div>
      </div>

      {/* Verification result box */}
      {verified && (
        <div
          className={`p-4 rounded-2xl border mb-4 text-xs font-mono animate-fadeIn ${
            verified.status === 'VERIFIED_VALID' || verified.status === 'VALID'
              ? 'bg-emerald-950/40 border-emerald-500/40 text-emerald-300'
              : 'bg-rose-950/40 border-rose-500/40 text-rose-300'
          }`}
        >
          <div className="flex items-center gap-2 font-bold text-sm">
            <CheckCircle2 className="w-4 h-4" />
            {verified.status}: {verified.message || 'Cryptographic hash chain is 100% intact from Genesis block.'}
          </div>
          {verified.latest_hash && (
            <div className="text-[10px] text-slate-400 mt-1 truncate">
              Latest Block Hash: <span className="text-sky-400">{verified.latest_hash}</span>
            </div>
          )}
        </div>
      )}

      {/* Audit Log Table */}
      <div className="rounded-2xl border border-slate-800 overflow-hidden bg-slate-950/70">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-slate-900/90 text-[10px] text-slate-400 uppercase tracking-wider border-b border-slate-800">
              <tr>
                <th className="p-3">Timestamp</th>
                <th className="p-3">Actor</th>
                <th className="p-3">Action</th>
                <th className="p-3">Event ID / Details</th>
                <th className="p-3">Block Hash (SHA-256)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {loading ? (
                <tr>
                  <td colSpan="5" className="p-6 text-center text-slate-500 font-sans">
                    Loading cryptographic audit records...
                  </td>
                </tr>
              ) : paginated.length === 0 ? (
                <tr>
                  <td colSpan="5" className="p-6 text-center text-slate-500 font-sans">
                    No audit records logged yet.
                  </td>
                </tr>
              ) : (
                paginated.map((entry, idx) => (
                  <tr key={idx} className="hover:bg-slate-900/50 transition-colors">
                    <td className="p-3 text-slate-300 whitespace-nowrap">
                      {new Date(entry.timestamp).toLocaleString()}
                    </td>
                    <td className="p-3 text-sky-400 font-bold">{entry.actor || 'Operator'}</td>
                    <td className="p-3 font-bold text-white">{entry.action}</td>
                    <td className="p-3 text-slate-400 max-w-xs truncate">
                      {JSON.stringify(entry.details || {})}
                    </td>
                    <td className="p-3 text-slate-500 text-[10px] truncate max-w-[120px]">
                      {entry.current_hash ? entry.current_hash.slice(0, 16) + '...' : 'Genesis'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default function AdminSettings({ token: propToken, onRefreshData, onOpenAuth }) {
  const activeToken = propToken || localStorage.getItem('skyguard_token');
  const [weights, setWeights] = useState({
    w_rule: 0.10,
    w_flatline: 0.10,
    w_iforest: 0.25,
    w_autoencoder: 0.35,
    w_drift: 0.15,
    w_spatial: 0.15,
    threshold_severity: 0.60,
    cooldown_seconds: 120,
  });

  const [saving, setSaving] = useState(false);
  const [toastMsg, setToastMsg] = useState(null);
  const [retrainingModel, setRetrainingModel] = useState(null);

  // Load server thresholds on mount if available
  useEffect(() => {
    const loadThresholds = async () => {
      try {
        const resp = await api.get('/api/v1/admin/thresholds');
        const data = resp.data;
        const t = data?.thresholds || {};
        setWeights((prev) => ({
          ...prev,
          threshold_severity: t.fusion_threshold ?? prev.threshold_severity,
          w_iforest: t.iforest_weight ?? prev.w_iforest,
          w_autoencoder: t.autoencoder_weight ?? prev.w_autoencoder,
          w_drift: t.drift_weight ?? prev.w_drift,
          w_spatial: t.spatial_weight ?? prev.w_spatial,
          cooldown_seconds: t.alert_cooldown_seconds ?? prev.cooldown_seconds,
        }));
      } catch (e) {
        console.warn('Could not fetch server thresholds (unauthenticated or offline):', e);
      }
    };
    loadThresholds();
  }, [activeToken]);

  const handleWeightChange = (key, val) => {
    setWeights((prev) => ({ ...prev, [key]: val }));
  };

  const handleSave = async () => {
    sounds.playClick();
    setSaving(true);
    setToastMsg(null);
    const tokenToUse = propToken || localStorage.getItem('skyguard_token');

    if (!tokenToUse) {
      setToastMsg({
        type: 'error',
        text: 'Admin Authentication Required: Please log in using the Login button (admin@skyguard.ai) to calibrate weights.'
      });
      setSaving(false);
      return;
    }

    try {
      const resp = await api.post('/api/v1/admin/thresholds', {
        fusion_threshold: weights.threshold_severity,
        iforest_weight: weights.w_iforest,
        autoencoder_weight: weights.w_autoencoder,
        drift_weight: weights.w_drift,
        spatial_weight: weights.w_spatial,
        alert_cooldown_seconds: weights.cooldown_seconds
      });

      sounds.playSuccessChime();
      setToastMsg({
        type: 'success',
        text: 'Runtime detector weights & anomaly thresholds calibrated successfully.'
      });
      if (onRefreshData) onRefreshData();
    } catch (e) {
      const status = e?.response?.status;
      if (status === 401 || status === 403) {
        setToastMsg({
          type: 'error',
          text: 'Session expired or insufficient privileges. Please log in as Admin (admin@skyguard.ai).'
        });
      } else {
        setToastMsg({
          type: 'error',
          text: `Calibration update failed: ${e?.response?.data?.detail || e.message || 'Unknown error'}`
        });
      }
    } finally {
      setSaving(false);
    }
  };

  const handleRetrain = async (modelType) => {
    sounds.playClick();
    setRetrainingModel(modelType);
    const tokenToUse = propToken || localStorage.getItem('skyguard_token');

    if (!tokenToUse) {
      setToastMsg({
        type: 'error',
        text: 'Admin Authentication Required to trigger asynchronous model retraining.'
      });
      setRetrainingModel(null);
      return;
    }

    try {
      const resp = await api.post('/api/v1/admin/retrain', {
        models: [modelType.toLowerCase()]
      });
      sounds.playSuccessChime();
      setToastMsg({
        type: 'success',
        text: `Retraining job scheduled for ${modelType}. Running in background.`
      });
    } catch (e) {
      setToastMsg({
        type: 'error',
        text: `Retraining error: ${e?.response?.data?.detail || e.message || 'Request failed'}`
      });
    } finally {
      setRetrainingModel(null);
    }
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Toast Notice */}
      {toastMsg && (
        <div className={`p-4 rounded-2xl border text-xs font-mono shadow-xl flex items-center justify-between animate-fadeIn ${
          toastMsg.type === 'error'
            ? 'bg-rose-950/90 border-rose-500/40 text-rose-300'
            : 'bg-emerald-950/90 border-emerald-500/40 text-emerald-300'
        }`}>
          <span>{toastMsg.type === 'error' ? '⚠️' : '✅'} {toastMsg.text}</span>
          <div className="flex items-center gap-2">
            {toastMsg.type === 'error' && onOpenAuth && (
              <button
                onClick={onOpenAuth}
                className="px-2 py-1 rounded-lg bg-rose-500/30 text-white font-bold hover:bg-rose-500 transition-all"
              >
                Log In
              </button>
            )}
            <button onClick={() => setToastMsg(null)} className="text-slate-400 hover:text-white font-bold ml-2">✕</button>
          </div>
        </div>
      )}

      {/* Auth Banner if unauthenticated */}
      {!activeToken && (
        <div className="p-3.5 rounded-2xl bg-amber-950/40 border border-amber-500/30 text-amber-300 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Lock className="w-4 h-4 text-amber-400" />
            <span>You are viewing calibration in read-only mode. Log in as <strong>admin@skyguard.ai</strong> to save runtime weights.</span>
          </div>
          {onOpenAuth && (
            <button
              onClick={onOpenAuth}
              className="px-3 py-1 rounded-xl bg-amber-500/20 text-amber-300 border border-amber-500/40 text-xs font-bold hover:bg-amber-500 hover:text-slate-900 transition-all"
            >
              Log In as Admin
            </button>
          )}
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-extrabold text-white flex items-center gap-2 tracking-tight">
            <Settings className="w-5 h-5 text-sky-400" />
            Admin Calibration & Ensemble Configuration Center
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Calibrate detector fusion weights, trigger asynchronous model retraining, and inspect cryptographic audit logs
          </p>
        </div>

        <button
          onClick={handleSave}
          disabled={saving}
          className="cyber-btn-primary px-5 py-2.5 text-xs flex items-center gap-2"
        >
          <Save className="w-4 h-4" />
          <span>{saving ? 'Saving...' : 'Save & Calibrate Weights'}</span>
        </button>
      </div>

      {/* Sliders Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <SliderRow
          label="Autoencoder Weight (AE)"
          description="Neural reconstruction joint thermodynamic MSE"
          value={weights.w_autoencoder}
          min={0.0} max={1.0} step={0.05}
          onChange={(v) => handleWeightChange('w_autoencoder', v)}
        />
        <SliderRow
          label="Isolation Forest Weight (IF)"
          description="Unsupervised multidimensional tree isolation depth"
          value={weights.w_iforest}
          min={0.0} max={1.0} step={0.05}
          onChange={(v) => handleWeightChange('w_iforest', v)}
        />
        <SliderRow
          label="STL + CUSUM Drift Weight"
          description="Cumulative sum residual drift tracking"
          value={weights.w_drift}
          min={0.0} max={1.0} step={0.05}
          onChange={(v) => handleWeightChange('w_drift', v)}
        />
        <SliderRow
          label="Spatial IDW Weight"
          description="Peer station distance-weighted consistency"
          value={weights.w_spatial}
          min={0.0} max={1.0} step={0.05}
          onChange={(v) => handleWeightChange('w_spatial', v)}
        />
        <SliderRow
          label="Composite Severity Threshold"
          description="Minimum ensemble score to flag anomaly"
          value={weights.threshold_severity}
          min={0.3} max={0.95} step={0.05}
          onChange={(v) => handleWeightChange('threshold_severity', v)}
        />
        <SliderRow
          label="Alert Cooldown (Hysteresis)"
          description="Deduplication window in seconds"
          value={weights.cooldown_seconds}
          min={30} max={600} step={15} unit="s"
          onChange={(v) => handleWeightChange('cooldown_seconds', v)}
        />
      </div>

      {/* Model Retraining Control Cards */}
      <div className="glass-panel p-5">
        <h3 className="text-sm font-extrabold text-white uppercase font-mono tracking-wider flex items-center gap-2 mb-3">
          <Cpu className="w-4 h-4 text-sky-400" />
          On-Demand Model Retraining Workers
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {[
            { id: 'AUTOENCODER', name: 'PyTorch Deep Autoencoder', desc: 'Retrains 8→6→3→6→8 neural compressor' },
            { id: 'ISOLATION_FOREST', name: 'Isolation Forest Model', desc: 'Retrains 150-tree unsupervised isolation forest' },
            { id: 'META_ENSEMBLE', name: 'XGBoost Meta-Classifier', desc: 'Optimizes weighted ensemble fusion layer' },
          ].map((m) => (
            <div key={m.id} className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 flex flex-col justify-between">
              <div>
                <div className="text-xs font-bold text-white font-mono">{m.name}</div>
                <div className="text-[11px] text-slate-400 mt-1">{m.desc}</div>
              </div>
              <button
                disabled={retrainingModel === m.id}
                onClick={() => handleRetrain(m.id)}
                className="mt-3 w-full py-1.5 rounded-xl bg-slate-800 hover:bg-sky-500 hover:text-slate-950 text-slate-200 text-xs font-bold transition-all disabled:opacity-50 flex items-center justify-center gap-1.5 font-mono"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${retrainingModel === m.id ? 'animate-spin' : ''}`} />
                {retrainingModel === m.id ? 'Training...' : 'Retrain Checkpoint'}
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Audit Trail Ledger */}
      <AuditTrailViewer token={token} />
    </div>
  );
}
