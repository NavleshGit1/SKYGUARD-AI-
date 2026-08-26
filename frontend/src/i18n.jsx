/**
 * SkyGuard AI — Internationalization (i18n)
 * Blueprint §4 Component 10.6: English + Hindi UI support for regional field operators
 *
 * Usage:
 *   import { useTranslation, LanguageProvider } from './i18n';
 *   const { t, lang, setLang } = useTranslation();
 *   <p>{t('dashboard.title')}</p>
 */
import { createContext, useContext, useState } from 'react';

const translations = {
  en: {
    // Navigation
    'nav.overview':    'Command Center',
    'nav.map':         'Live Map',
    'nav.telemetry':   'Telemetry',
    'nav.alerts':      'Alert Feed',
    'nav.health':      'Sensor Health',
    'nav.benchmark':   'Model Benchmark',
    'nav.simulator':   'Simulator',
    'nav.admin':       'Admin Settings',

    // Dashboard KPIs
    'kpi.total_stations':  'Total Stations',
    'kpi.healthy':         'Healthy',
    'kpi.critical':        'Critical',
    'kpi.active_alerts':   'Active Alerts',

    // Status labels
    'status.healthy':   'Healthy',
    'status.degraded':  'Degraded',
    'status.critical':  'Critical',
    'status.active':    'Active',
    'status.resolved':  'Resolved',
    'status.ack':       'Acknowledged',

    // Common actions
    'action.refresh':   'Refresh',
    'action.resolve':   'Mark Resolved',
    'action.ack':       'Acknowledge',
    'action.save':      'Save',
    'action.cancel':    'Cancel',
    'action.details':   'View Details',
    'action.inject':    'Inject Fault',
    'action.retrain':   'Retrain Model',

    // Fault types
    'fault.spike':        'Spike',
    'fault.flatline':     'Flatline',
    'fault.drift':        'Calibration Drift',
    'fault.dropout':      'Signal Dropout',
    'fault.noise':        'High Noise',
    'fault.multivariate': 'Thermodynamic Violation',
    'fault.normal':       'Normal',

    // Sensor params
    'param.temperature':  'Temperature',
    'param.pressure':     'Barometric Pressure',
    'param.humidity':     'Relative Humidity',
    'param.dew_point':    'Dew Point',

    // Health screen
    'health.title':       'Sensor Health Leaderboard',
    'health.subtitle':    'Real-time composite health scoring + Mann-Kendall predictive maintenance',
    'health.mk_trend':    'MK Trend',
    'health.days_critical':'Days to Critical',
    'health.maintenance': 'Maintenance Required',
    'health.slope':       'Theil-Sen Slope / Day',

    // Benchmark screen
    'benchmark.title':    'Data Quality & Model Benchmark',
    'benchmark.f1':       'F₁ Score',
    'benchmark.precision':'Precision',
    'benchmark.recall':   'Recall',
    'benchmark.mttd':     'Mean Time to Detection',
    'benchmark.run':      'Run Benchmark Suite',

    // Admin screen
    'admin.title':        'Admin Settings & Threshold Calibration',
    'admin.fusion_thr':   'Fusion Anomaly Threshold',
    'admin.cooldown':     'Alert Cooldown Window',
    'admin.save_thr':     'Save Thresholds',
    'admin.retrain':      'Trigger Retraining',
    'admin.audit':        'Audit Trail',
    'admin.verify':       'Verify Integrity',

    // Alert
    'alert.root_cause':   'Root Cause',
    'alert.severity':     'Severity',
    'alert.confidence':   'Confidence',
    'alert.explanation':  'Diagnosis',
    'alert.shap':         'SHAP Feature Attribution',

    // Footer / misc
    'misc.loading':       'Loading…',
    'misc.no_data':       'No data available.',
    'lang.toggle':        'हिंदी',
  },

  hi: {
    // Navigation
    'nav.overview':    'कमांड सेंटर',
    'nav.map':         'लाइव मानचित्र',
    'nav.telemetry':   'टेलीमेट्री',
    'nav.alerts':      'अलर्ट फ़ीड',
    'nav.health':      'सेंसर स्वास्थ्य',
    'nav.benchmark':   'मॉडल बेंचमार्क',
    'nav.simulator':   'सिम्युलेटर',
    'nav.admin':       'व्यवस्थापक सेटिंग',

    // Dashboard KPIs
    'kpi.total_stations':  'कुल स्टेशन',
    'kpi.healthy':         'स्वस्थ',
    'kpi.critical':        'गंभीर',
    'kpi.active_alerts':   'सक्रिय अलर्ट',

    // Status labels
    'status.healthy':   'स्वस्थ',
    'status.degraded':  'क्षीण',
    'status.critical':  'गंभीर',
    'status.active':    'सक्रिय',
    'status.resolved':  'हल किया गया',
    'status.ack':       'स्वीकृत',

    // Common actions
    'action.refresh':   'ताज़ा करें',
    'action.resolve':   'हल के रूप में चिह्नित करें',
    'action.ack':       'स्वीकार करें',
    'action.save':      'सहेजें',
    'action.cancel':    'रद्द करें',
    'action.details':   'विवरण देखें',
    'action.inject':    'खराबी इंजेक्ट करें',
    'action.retrain':   'मॉडल पुनः प्रशिक्षित करें',

    // Fault types
    'fault.spike':        'स्पाइक',
    'fault.flatline':     'फ्लैटलाइन',
    'fault.drift':        'कैलिब्रेशन ड्रिफ्ट',
    'fault.dropout':      'सिग्नल ड्रॉपआउट',
    'fault.noise':        'उच्च शोर',
    'fault.multivariate': 'थर्मोडायनामिक उल्लंघन',
    'fault.normal':       'सामान्य',

    // Sensor params
    'param.temperature':  'तापमान',
    'param.pressure':     'वायुदाब',
    'param.humidity':     'सापेक्ष आर्द्रता',
    'param.dew_point':    'ओस बिंदु',

    // Health screen
    'health.title':       'सेंसर स्वास्थ्य लीडरबोर्ड',
    'health.subtitle':    'वास्तविक समय स्वास्थ्य स्कोरिंग + मान-केंडल पूर्वानुमान',
    'health.mk_trend':    'MK रुझान',
    'health.days_critical':'गंभीर होने में दिन',
    'health.maintenance': 'रखरखाव आवश्यक',
    'health.slope':       'थाइल-सेन ढलान / दिन',

    // Benchmark screen
    'benchmark.title':    'डेटा गुणवत्ता और मॉडल बेंचमार्क',
    'benchmark.f1':       'F₁ स्कोर',
    'benchmark.precision':'परिशुद्धता',
    'benchmark.recall':   'रिकॉल',
    'benchmark.mttd':     'औसत पहचान समय',
    'benchmark.run':      'बेंचमार्क चलाएं',

    // Admin screen
    'admin.title':        'व्यवस्थापक सेटिंग और थ्रेशोल्ड कैलिब्रेशन',
    'admin.fusion_thr':   'फ्यूजन विसंगति थ्रेशोल्ड',
    'admin.cooldown':     'अलर्ट कूलडाउन विंडो',
    'admin.save_thr':     'थ्रेशोल्ड सहेजें',
    'admin.retrain':      'पुनः प्रशिक्षण शुरू करें',
    'admin.audit':        'ऑडिट ट्रेल',
    'admin.verify':       'अखंडता सत्यापित करें',

    // Alert
    'alert.root_cause':   'मूल कारण',
    'alert.severity':     'गंभीरता',
    'alert.confidence':   'आत्मविश्वास',
    'alert.explanation':  'निदान',
    'alert.shap':         'SHAP विशेषता Attribution',

    // Footer / misc
    'misc.loading':       'लोड हो रहा है…',
    'misc.no_data':       'कोई डेटा उपलब्ध नहीं।',
    'lang.toggle':        'English',
  }
};

const I18nContext = createContext(null);

export function LanguageProvider({ children }) {
  const [lang, setLang] = useState(() =>
    localStorage.getItem('skyguard_lang') || 'en'
  );

  const changeLang = (l) => {
    localStorage.setItem('skyguard_lang', l);
    setLang(l);
  };

  const t = (key) => translations[lang]?.[key] ?? translations.en?.[key] ?? key;

  return (
    <I18nContext.Provider value={{ t, lang, setLang: changeLang }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useTranslation() {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error('useTranslation must be used inside <LanguageProvider>');
  return ctx;
}

/**
 * Language Toggle Button — drop this anywhere in the UI.
 */
export function LanguageToggle({ style = {} }) {
  const { t, lang, setLang } = useTranslation();
  return (
    <button
      id="language-toggle-btn"
      onClick={() => setLang(lang === 'en' ? 'hi' : 'en')}
      title="Switch language / भाषा बदलें"
      style={{
        padding:      '6px 14px',
        borderRadius: 8,
        fontSize:     13,
        fontWeight:   600,
        cursor:       'pointer',
        background:   'rgba(59,130,246,0.12)',
        color:        '#93C5FD',
        border:       '1px solid rgba(59,130,246,0.25)',
        transition:   'all 0.2s',
        ...style
      }}
    >
      🌐 {t('lang.toggle')}
    </button>
  );
}
