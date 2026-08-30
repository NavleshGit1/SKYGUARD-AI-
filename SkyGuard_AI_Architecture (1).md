# SkyGuard AI — Full Project Architecture (Reconsolidated, No Custom Edge Hardware)
### Intelligent Real-Time Anomaly Detection System for AWS (Temperature, Pressure, Humidity)

---

## 1. Design Philosophy

The system now assumes AWS stations already exist and already produce data (via their own vendor hardware/telemetry) — SkyGuard AI is a **software-only intelligence layer** that sits on top of that incoming data stream. There is no custom sensor/microcontroller build; the "edge" concept collapses into whatever the AWS network's own data feed already is (API, file drop, or streaming telemetry).

This simplifies the system to **two tiers** instead of three:

```
TIER 1 (Data Source / Feed)   →   TIER 2 (Software Pipeline: ingestion → detection → serving)
Existing AWS network output       Everything SkyGuard AI builds
```

No single model still satisfies every objective (spikes, frozen values, drift, multivariate inconsistency, explainability). The hybrid multi-detector ensemble approach from before is retained in full — only the hardware/edge-firmware layer is removed.

---

## 2. High-Level System Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  LAYER 1 — DATA SOURCE LAYER                                                 │
│  - Existing AWS network feeds: live telemetry (API/streaming) and/or         │
│    historical data files (CSV/DB export) per station                        │
└───────────────────────────────┬──────────────────────────────────────────────┘
                                 │ API polling / file ingestion / message stream
┌───────────────────────────────▼──────────────────────────────────────────────┐
│  LAYER 2 — DATA INGESTION LAYER                                              │
│  - Feed adapters, message broker, schema validation, timestamp sync         │
└───────────────────────────────┬──────────────────────────────────────────────┘
┌───────────────────────────────▼──────────────────────────────────────────────┐
│  LAYER 3 — STREAM PROCESSING & FEATURE ENGINEERING                          │
│  - Windowing, rolling stats, seasonal decomposition, physics-derived        │
│    features (dew point, pressure-altitude norm, heat index)                 │
└───────────────────────────────┬──────────────────────────────────────────────┘
┌───────────────────────────────▼──────────────────────────────────────────────┐
│  LAYER 4 — ANOMALY DETECTION ENGINE (ensemble, runs in parallel)             │
│  ┌────────────┐ ┌────────────┐ ┌───────────────┐ ┌────────────┐ ┌─────────┐ │
│  │Rule/Range  │ │Frozen-Value│ │Statistical    │ │Multivariate│ │Temporal │ │
│  │& Physical  │ │/ Stuck-    │ │Point Anomaly  │ │Consistency │ │Drift &  │ │
│  │Plausibility│ │Sensor      │ │(IF/z-score/   │ │(Autoenc./  │ │Seasonal │ │
│  │Checks      │ │Detector    │ │robust MAD)    │ │Correlation)│ │Model    │ │
│  └────────────┘ └────────────┘ └───────────────┘ └────────────┘ └─────────┘ │
│                                        │                                     │
│                              FUSION / SCORING LAYER                         │
│                     (weighted ensemble → severity + confidence)             │
└───────────────────────────────┬──────────────────────────────────────────────┘
┌───────────────────────────────▼──────────────────────────────────────────────┐
│  LAYER 5 — EXPLAINABILITY & ROOT-CAUSE CLASSIFICATION                       │
│  - SHAP/LIME feature attribution, rule-based root-cause tagger,             │
│    spatial cross-check against neighboring stations                        │
└───────────────────────────────┬──────────────────────────────────────────────┘
┌───────────────────────────────▼──────────────────────────────────────────────┐
│  LAYER 6 — DECISION & ACTION LAYER                                          │
│  - Alerting, corrected-value imputation, sensor-health scoring,             │
│    predictive maintenance signal                                            │
└───────────────────────────────┬──────────────────────────────────────────────┘
┌───────────────────────────────▼──────────────────────────────────────────────┐
│  LAYER 7 — STORAGE                                                          │
│  - Time-series DB (raw + cleaned), Anomaly event store, Model registry      │
└───────────────────────────────┬──────────────────────────────────────────────┘
┌───────────────────────────────▼──────────────────────────────────────────────┐
│  LAYER 8 — SERVING & PRESENTATION                                           │
│  - REST/WebSocket API, real-time dashboard, alert channels (SMS/Email/App)  │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Layer-by-Layer Feature Breakdown

### Layer 1 — Data Source
- Data arrives from the existing AWS network's own output — no custom hardware or firmware is built by this project.
- Two supported feed modes:
  - **Historical/batch mode:** CSV/database export of past readings, used for training and evaluation
  - **Live/streaming mode:** the AWS network's existing API or telemetry stream, polled or subscribed to, used for real-time detection
- Each record still assumed to contain (at minimum) Temperature, Pressure, Humidity, station ID, and timestamp; lat/long and altitude are used if the source provides them (needed for spatial checks and altitude-corrected pressure — otherwise those features are skipped, not fabricated).
- A **feed simulator** is a required project component regardless of live-feed availability — it replays historical data at real-time pace to let the whole pipeline (ingestion through dashboard) be demoed end-to-end without needing a live AWS network connection.

### Layer 2 — Data Ingestion
- Feed adapters: REST API poller, file-watcher (batch import), and/or streaming client — whichever the actual data source supports
- Message broker (Kafka, or a lighter queue for smaller scale) to decouple ingestion rate from processing rate and provide durability/replay
- Schema validation (reject malformed records, log to a dead-letter store)
- Timestamp normalization (detect out-of-order or stale timestamps — this becomes a communication-error signal)
- Station metadata join (station ID, lat/long if available, altitude, calibration history) from the metadata store

### Layer 3 — Stream Processing & Feature Engineering
- **Rolling statistical features:** rolling mean/std/median/MAD over multiple windows (5-min, 1-hr, 24-hr)
- **Rate of change features:** first and second derivative of each parameter
- **Seasonal/climatological baseline features:** expected value & bounds for this station, this time-of-day, this day-of-year (from historical climatology)
- **Physics-derived cross-features:** dew point (from T & RH — physically must be ≤ temperature), sea-level-reduced pressure (if altitude is available)
- **Missingness features:** gap duration, packet-loss rate over trailing window
- Feature store (online + offline) so training and inference use identical feature definitions

### Layer 4 — Anomaly Detection Engine (Ensemble)

| Detector | Technique | Targets |
|---|---|---|
| Rule/Physical Plausibility | Hard bounds + dew-point-vs-temperature physics checks | Impossible readings, gross faults |
| Frozen/Stuck-Value | Rolling variance == 0 / duplicate-run-length check | Sensor stuck, repeated/cached values |
| Statistical Point Anomaly | Isolation Forest / robust z-score (MAD) / Local Outlier Factor | Spikes, single-point outliers |
| Multivariate Consistency | Autoencoder (reconstruction error) or Mahalanobis distance across T/P/RH + derived features | Physically inconsistent combinations |
| Temporal/Seasonal Drift | STL decomposition + CUSUM/PELT change-point detection, or LSTM-Autoencoder | Calibration drift, slow bias |
| Spatial Consistency (optional, needs multi-station data with location) | Compare reading vs spatially-interpolated estimate from neighboring stations | Localized fault vs genuine regional weather event |

**Fusion/Scoring Layer:**
- Each detector outputs a normalized score (0–1)
- Weighted ensemble (or a shallow meta-model trained on injected-anomaly labels) → **Severity Score**
- Agreement across detectors → **Confidence Score**
- Hysteresis/cooldown to reduce alert flapping

### Layer 5 — Explainability & Root-Cause Classification
- **SHAP** for tree/ensemble-based detectors (Isolation Forest, fusion meta-model)
- **LIME** as fallback local-explanation for black-box models (autoencoder/LSTM)
- **Reconstruction-error breakdown** for the autoencoder (which parameter contributed most)
- **Rule-based root-cause tagger** mapping detector-firing patterns to a probable-cause label (frozen-only → sensor stuck; drift-only → calibration drift; multivariate + spatial-neighbors-normal → local fault; multivariate + spatial-neighbors-also-shifting → genuine weather event; high missingness → comms failure)
- Natural-language explanation generator (template-based) for human-readable alert text

### Layer 6 — Decision & Action Layer
- **Alert Manager:** severity-based routing, deduplication, hysteresis/cooldown
- **Corrected Value Estimator (optional):** interpolation for short gaps; autoencoder's reconstructed value as a plausible estimate; spatial interpolation if neighboring-station data exists — always flagged as estimated, never overwriting raw data
- **Sensor Health Scoring:** composite score from anomaly frequency, drift trend, missing-data rate, time since last calibration
- **Predictive Maintenance Signal:** heuristic trend analysis on the health score (rising anomaly rate/drift slope) — not a trained failure classifier, since no labeled failure-history dataset exists

### Layer 7 — Storage
- **Time-series database** (TimescaleDB/InfluxDB) — raw + cleaned/corrected readings per station
- **Anomaly Event Store** (relational/document DB) — every detected anomaly with full detector votes, severity, confidence, root cause, explanation, resolution status
- **Model Registry** — versioned models per detector, per station or per climate-cluster
- **Metadata store** — station registry (location if available, altitude, calibration history)

### Layer 8 — Serving & Presentation
- **Backend API** (REST + WebSocket) exposing current readings, anomaly feed, station health, historical queries
- **Dashboard:** live station map (if location data available) or list view, time-series charts with anomaly overlays, alert feed with severity/confidence/root-cause/explanation, sensor health leaderboard, drill-down per station, admin panel
- **Alerting channels:** Email, SMS, webhook/Slack, in-app push

---

## 4. Cross-Cutting Concerns

| Concern | How it's addressed |
|---|---|
| **Real-time capability** | Streaming ingestion (broker-based), sub-second to few-second latency for rule/statistical detectors; heavier models run on micro-batches (every 1–5 min) |
| **Scalability** | Stateless detector services scalable behind the stream processor; per-station or per-climate-cluster models; broker decouples ingestion rate from processing rate |
| **Efficiency** | Since there's no constrained edge hardware, "efficiency" now means computational/infrastructure efficiency — lightweight statistical detectors filter first so only genuinely ambiguous cases reach the heavier autoencoder/LSTM models, minimizing compute cost per reading |
| **Explainability** | SHAP/LIME always available server-side with no hardware constraint limiting it |
| **No ground-truth problem** | Synthetic anomaly injection framework used for training/validation (Section 5) |
| **Security** | API auth, TLS, input validation — see the dedicated security requirements |
| **Fault tolerance** | Message broker durability/replay, dead-letter queues for malformed data, feed-adapter retry logic if the live AWS feed is temporarily unreachable |

---

## 5. Synthetic Anomaly Injection Framework

Used for both training the fusion layer and evaluation (matches the brief's "evaluated on anomaly-injected data"):
- **Spike injection**, **frozen-value injection**, **drift injection**, **dropout/gap injection**, **noise injection**, **multivariate inconsistency injection** — same set as before, applied on top of the historical/simulated feed from Layer 1.
- Each injected anomaly logged with ground-truth label (type, station, magnitude) → enables precision/recall/F1 per anomaly type.

---

## 6. Model Architecture Choices (unchanged from detection standpoint)

| Component | Model | Why |
|---|---|---|
| Point anomaly | Isolation Forest / robust z-score (MAD) | Fast, unsupervised, interpretable |
| Multivariate consistency | Autoencoder (small feedforward) | Learns normal joint T/P/RH distribution; reconstruction error = anomaly signal |
| Temporal/seasonal | STL decomposition + CUSUM/PELT, or LSTM-Autoencoder | Captures slow drift distinct from spikes |
| Frozen-value | Rule-based | Deterministic, no ML needed |
| Fusion | Weighted ensemble, optional shallow meta-learner | Combines detector votes into calibrated severity/confidence |

---

## 7. Technology Stack (reconsolidated, no firmware/edge tooling)

- **Data Source Layer:** REST API client / file-watcher / streaming client (whichever the AWS network provides), plus a custom feed simulator for demo/offline use
- **Ingestion/Streaming:** Kafka (or a lighter message queue), schema validation library
- **Processing/ML:** Python — pandas/numpy, scikit-learn (Isolation Forest, LOF), PyTorch/TensorFlow (autoencoder, LSTM), statsmodels (STL), ruptures (change-point detection)
- **Explainability:** SHAP, LIME
- **Storage:** TimescaleDB or InfluxDB (time series), PostgreSQL/MongoDB (anomaly events + metadata)
- **Backend API:** FastAPI — REST + WebSocket
- **Dashboard:** React + charting library (Recharts/Plotly) + map (Leaflet/Mapbox, if location data is available)
- **Alerting:** Twilio (SMS), SMTP (email), Slack/webhook
- **Orchestration/Deployment:** Docker Compose (demo scale), Kubernetes (production scale)

---

## 8. Data Flow Summary (single reading, end to end)

1. AWS network feed (live or simulated) produces a reading
2. Ingestion validates schema, joins station metadata
3. Stream processor computes rolling/seasonal/physics features
4. All detectors score the reading in parallel
5. Fusion layer combines scores → severity + confidence
6. If anomalous: SHAP explanation + rule-based root-cause tag + optional spatial cross-check
7. Alert manager decides routing; corrected-value estimator runs if applicable
8. Everything persisted (raw, cleaned, event) to storage
9. Dashboard updates live via WebSocket; sensor health score recalculated

---

## 9. What Ties Back to Evaluation Criteria

- **Innovation (25%):** hybrid multi-detector ensemble + physics-informed features + spatial cross-check + predictive maintenance heuristic
- **Accuracy (20%):** synthetic injection framework enables real precision/recall/F1 measurement per anomaly type
- **Real-time (15%):** streaming architecture, cheap-detectors-first filtering before heavier models
- **Explainability (10%):** SHAP/LIME + rule-based root-cause tagger + natural-language alert text
- **Scalability (10%):** stateless services, per-cluster models, broker-decoupled ingestion
- **Deployability (10%):** Docker/Kubernetes-based software stack, no custom hardware dependency to source/manufacture
- **Visualization (5%):** live map/list + time series + alert feed dashboard
- **Efficiency (5%):** tiered cheap-to-expensive detector filtering minimizes unnecessary heavy-model compute per reading

---

*This document supersedes the earlier three-tier (edge/fog/cloud) version — the entire system is now a two-tier, software-only pipeline sitting on top of an existing AWS network's data feed.*
