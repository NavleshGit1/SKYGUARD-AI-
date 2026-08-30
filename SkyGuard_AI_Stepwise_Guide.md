# SkyGuard AI — Complete Step-by-Step Implementation Guide (Theory Only, No Custom Hardware)
### How to Build the Entire Project: Components, Order of Construction, and How Everything Connects

This is the reconsolidated build plan with the ESP32/custom-edge-hardware layer removed. The system is now a **software-only pipeline** that consumes data from an existing AWS network (or a simulator standing in for one) — no firmware, no sensor wiring, no on-device ML.

---

## PHASE 0 — Planning & Scoping

**Step 0.1 — Define deployment scope**
Decide: single-station prototype, or multi-station network demo. This determines whether spatial-consistency detection and the station map are in scope. Document this as an explicit assumption, since the brief's guaranteed inputs are only per-station T/P/RH, while the worked example implies multi-station comparison.

**Step 0.2 — Source or simulate historical data**
Obtain historical AWS-style time series (public sources: NOAA ISD, IMD, Kaggle weather datasets) or generate synthetic seasonal data. This dataset underlies every downstream component — feature engineering, model training, and evaluation.

**Step 0.3 — Define the Anomaly Event Schema**
Fix the common output format up front (station ID, timestamp, parameter, raw value, severity score, confidence score, root-cause label, detector votes, explanation text). Every detector, the fusion layer, storage, dashboard, and alerting all speak this schema.

**Step 0.4 — Build the Data Feed Simulator**
Since there's no hardware being built, this becomes the project's stand-in "data source." It replays the historical dataset (Step 0.2) at a configurable pace (e.g., real-time speed or accelerated) to simulate a live AWS network feed, and it's also where synthetic anomalies get injected. This single component powers both live demos and evaluation — everything from Phase 1 onward treats its output identically to a real live feed.

---

## PHASE 1 — Data Source Layer

**Step 1.1 — Identify or connect the real feed (if available)**
If an actual AWS network's API or database export is accessible, build a feed adapter for it (REST client, file-watcher for batch exports, or a streaming subscription). If not accessible, the simulator from Step 0.4 is the sole source — the rest of the architecture doesn't need to know the difference, since both produce the same schema of raw readings.

**Step 1.2 — Normalize the input format**
Whatever the source, convert incoming records into one internal raw-reading format (station ID, timestamp, temperature, pressure, humidity, and location/altitude if available). This normalization step is what lets Phase 2 onward remain agnostic to whether data came from a live feed, a file export, or the simulator.

---

## PHASE 2 — Data Ingestion Layer

**Step 2.1 — Stand up the message broker**
Deploy a broker/queue (Kafka, or a lighter alternative for smaller scale) as the single entry point for all incoming readings from Phase 1. Decouples how fast data arrives from how fast it's processed.

**Step 2.2 — Schema validation**
Every incoming message is checked against the raw-reading schema from Step 1.2. Malformed messages go to a dead-letter queue rather than the main pipeline, protecting every downstream component.

**Step 2.3 — Station metadata join**
Attach station ID, location (if available), altitude, and calibration history — pulled from the metadata store (Phase 7) — to each incoming reading. This join is what later enables altitude-corrected pressure and the spatial cross-check detector.

**Step 2.4 — Timestamp normalization**
Check each reading's timestamp for ordering/consistency; anomalous timestamps become one of the signals the communication-error detector consumes in Phase 4.

---

## PHASE 3 — Stream Processing & Feature Engineering

**Step 3.1 — Set up windowing**
Establish sliding/rolling windows (5-min, 1-hr, 24-hr) per station over the incoming stream — the computational basis for every statistical detector in Phase 4.

**Step 3.2 — Compute rolling statistical features**
Rolling mean/std/median/MAD per window, per parameter — feeds the statistical point-anomaly detector.

**Step 3.3 — Compute rate-of-change features**
First/second derivatives per parameter — feeds both the spike/rule detector and the frozen-value detector (zero derivative sustained = flatline signal).

**Step 3.4 — Build the climatology baseline**
From the historical dataset (Step 0.2), compute expected value + normal range per station, time-of-day, and day-of-year. Feeds the temporal/seasonal drift detector, and is what lets the system judge extreme-but-plausible values (e.g., high desert temperatures) correctly instead of flagging every extreme as a fault.

**Step 3.5 — Compute physics-derived cross-features**
Dew point from temperature and humidity (physically must be ≤ temperature); sea-level-reduced pressure if altitude is available from Step 2.3. Feeds the multivariate consistency detector directly.

**Step 3.6 — Compute missingness features**
Gap duration and packet-loss rate per station over a trailing window — the primary input to the communication-error detector.

**Step 3.7 — Persist to a feature store**
Store computed features (online for live inference, offline for training) so training and inference always use identical feature definitions — this connects Phase 3 to both Phase 4 and model training.

---

## PHASE 4 — Anomaly Detection Engine

Each detector reads from the feature store (Phase 3) and writes to the fusion layer (Step 4.6).

**Step 4.1 — Rule/Physical Plausibility detector**
Hard bounds per parameter + dew-point-vs-temperature physics rule. No training needed.

**Step 4.2 — Frozen/Stuck-Value detector**
Consumes the rate-of-change feature (Step 3.3): zero variance across a window, or repeated identical values, flags as frozen. Deterministic.

**Step 4.3 — Statistical Point-Anomaly detector**
Trained on rolling statistical features (Step 3.2) using an unsupervised method (Isolation Forest or robust z-score). Trained on historical "mostly normal" data, since real fault labels don't exist.

**Step 4.4 — Multivariate Consistency detector**
An autoencoder trained on the physics-derived cross-features (Step 3.5) to learn normal joint T/P/RH behavior; high reconstruction error at inference signals an anomaly. This directly answers the brief's worked example (implausible T+RH+Pressure combination).

**Step 4.5 — Temporal/Seasonal Drift detector**
Built on the climatology baseline (Step 3.4) using STL decomposition plus change-point detection (CUSUM/PELT), or an LSTM-Autoencoder for stations with long history. Distinguishes slow calibration drift from a sudden spike.

**Step 4.5a — (Optional) Spatial Consistency detector**
Only buildable if Step 0.1 scoped in multi-station data with location. Compares a station's reading against a spatially interpolated estimate from neighboring stations. Resolves the worked-example question of genuine regional event vs single faulty sensor.

**Step 4.6 — Fusion/Scoring layer**
Combines every detector's normalized (0–1) score into a weighted ensemble — or a shallow meta-model trained on synthetic injection labels — producing a **severity score**; detector agreement produces a **confidence score**. This is the single convergence point: everything before runs in parallel, everything after treats the ensemble output as one unified signal.

---

## PHASE 4a — Synthetic Anomaly Injection & Evaluation (built alongside Phase 4)

**Step 4a.1 — Build the injection logic into the simulator**
Extend the Data Feed Simulator (Step 0.4) to optionally inject spikes, frozen-value runs, drift, gaps, noise bursts, and multivariate inconsistencies, each tagged with a ground-truth label. Building this into the simulator (rather than as a separate tool) means the same component serves both demo playback and evaluation.

**Step 4a.2 — Use injected data for training where needed**
The fusion meta-model (Step 4.6) and any supervised threshold tuning use this labeled data — the only place labeled anomalies exist in the whole system.

**Step 4a.3 — Use injected data for evaluation**
Run the full detection engine against held-out injected anomalies to compute precision/recall/F1 per anomaly type, producing the accuracy numbers for the evaluation criteria.

---

## PHASE 5 — Explainability & Root-Cause Classification

**Step 5.1 — Attach SHAP to tree/ensemble detectors**
Run SHAP on the Isolation Forest (Step 4.3) and fusion meta-model (Step 4.6) for feature attribution.

**Step 5.2 — Attach reconstruction-error attribution to the autoencoder**
For the multivariate detector (Step 4.4), break down reconstruction error by parameter.

**Step 5.3 — Build the rule-based root-cause tagger**
Map the pattern of which detectors fired (from Step 4.6's per-detector votes) to a root-cause label (frozen-only → sensor stuck; drift-only → calibration drift; multivariate + spatial-neighbors-normal → local fault; multivariate + spatial-neighbors-also-shifting → genuine weather event; high missingness → comms failure).

**Step 5.4 — Generate natural-language explanations**
Template-based text combining SHAP/reconstruction attribution and the root-cause label into a human-readable sentence — becomes the explanation field in the Anomaly Event Schema.

---

## PHASE 6 — Decision & Action Layer

**Step 6.1 — Corrected-value estimator (optional)**
Short gaps use interpolation from recent trusted history; multivariate faults use the autoencoder's reconstructed value (Step 4.4); spatial interpolation if location data exists. Stored separately and flagged as estimated, never overwriting raw values.

**Step 6.2 — Sensor health scoring**
Composite score from anomaly frequency (Phase 7's event history), drift magnitude trend (Step 4.5), missing-data rate (Step 3.6), and time since last calibration (Phase 7's metadata).

**Step 6.3 — Predictive maintenance signal**
Trend analysis on the health score over weeks — rising anomaly rate/drift slope triggers a maintenance-recommended flag. Heuristic, not a trained failure classifier, since no labeled failure-history dataset exists.

**Step 6.4 — Alert manager**
Reads severity/confidence (Step 4.6) and explanation (Step 5.4), applies deduplication and cooldown/hysteresis, routes to the appropriate channel by severity.

---

## PHASE 7 — Storage Layer

**Step 7.1 — Time-series database**
TimescaleDB or InfluxDB storing raw and cleaned/corrected readings, tagged by station. Written to continuously by Phases 2 and 3.

**Step 7.2 — Anomaly Event store**
Relational/document database storing every anomaly event per the Step 0.3 schema. Written to by Phase 4 (fusion) and Phase 5 (explainability); read by Phase 8 (dashboard/API).

**Step 7.3 — Model registry**
Versioned storage for every trained model. Phase 4's detectors load from here at inference time; Step 4a.2's retraining writes new versions back.

**Step 7.4 — Metadata store**
Station registry (location if available, altitude, calibration dates) — what Step 2.3 joins against and what Phase 5's spatial root-cause logic depends on.

---

## PHASE 8 — Serving & Presentation Layer

**Step 8.1 — Backend API**
REST + WebSocket API (e.g., FastAPI) exposing current readings, anomaly feed, and station health — reads from Phase 7, is the single interface every frontend/alert component connects through.

**Step 8.2 — Dashboard frontend**
Live station map or list view (color-coded by health from Step 6.2), time-series charts with anomaly overlays (Step 7.2), alert feed with explanations (Step 5.4), and admin panel — connects to the backend exclusively via the Step 8.1 API.

**Step 8.3 — Alert channel integrations**
Wire the Alert Manager (Step 6.4) to SMTP (email), an SMS gateway, and webhook/Slack.

**Step 8.4 — Admin controls**
Model retraining triggers (connecting to Step 4a.2 and the model registry) and threshold tuning (connecting to Step 4.6's fusion weights), gated behind authentication built in Phase 9.

---

## PHASE 9 — Security Layer (wrapped around Phases 2, 7, 8)

**Step 9.1 — Secure the feed-to-broker connection**
If a real AWS network API is used (Step 1.1), authenticate that connection (API keys/OAuth) and validate the source; the simulator path (Step 0.4) doesn't need this since it's internal.

**Step 9.2 — Secure the API layer**
Authentication (JWT/OAuth2) and RBAC on every endpoint (Step 8.1), input validation/sanitization against injection and XSS, CSRF protection on state-changing requests, rate limiting.

**Step 9.3 — Secure transport**
HTTPS/TLS with valid certificates and HSTS across the dashboard and API; a restrictive CORS policy.

**Step 9.4 — Secure the data layer**
Encrypt sensitive data at rest (Phase 7), apply least-privilege database credentials to the API's service account, manage all secrets (DB passwords, SMTP/SMS keys, any AWS-network API key) via a secrets manager.

**Step 9.5 — Secure the infrastructure**
Reverse proxy/WAF in front of the API and dashboard, security headers, containers run with least privilege, network segmentation so the database is never directly internet-facing.

**Step 9.6 — Monitoring & governance**
Audit logging of authentication and admin actions, anomalous-access alerting (separate from weather-anomaly alerting), automated dependency vulnerability scanning, periodic penetration testing before go-live.

---

## PHASE 10 — Testing, Documentation & Handover

**Step 10.1 — End-to-end test**
Run the simulator (Step 0.4) through every phase — ingestion → features → detection ensemble → fusion → explainability → storage → dashboard → alert — to confirm every connection point works.

**Step 10.2 — Evaluate against injected anomalies**
Use Phase 4a's held-out test set to produce precision/recall/F1 per anomaly type and latency benchmarks.

**Step 10.3 — Write documentation**
Architecture document (already produced), use-case document, setup/installation guide, evaluation results, and an explicit assumptions/limitations section (synthetic vs real fault data, single- vs multi-station scope, heuristic vs trained maintenance prediction, simulator-vs-real-feed distinction).

---

## Master Connection Map

```
AWS Network Feed (live API) OR Data Feed Simulator (with injection capability)
   → Ingestion (broker, schema validation, metadata join, timestamp check)
      → Feature Engineering (rolling stats, physics features, climatology, missingness)
         → [Detector 1: Rule] [Detector 2: Frozen] [Detector 3: Statistical]
            [Detector 4: Multivariate] [Detector 5: Drift] [Detector 6: Spatial*]
               → Fusion/Scoring Layer (severity + confidence)
                  → Explainability (SHAP/LIME) + Root-Cause Tagger
                     → Decision Layer (correction, health score, maintenance signal, alert manager)
                        → Storage (time-series DB, event store, model registry, metadata store)
                           → Backend API
                              → Dashboard  |  Alert Channels (email/SMS/webhook)
      (security wraps: feed auth → API auth/RBAC → TLS → data encryption → infra hardening → monitoring)
```

*Spatial detector only if multi-station scope with location data was chosen in Step 0.1.

This removes every hardware/firmware/edge-compute element from the earlier plan — the entire build is now software from the data-feed layer upward, which also removes the earlier hardware requirements list, the edge-security requirements, and the on-device energy-efficiency work; everything else (detection ensemble, explainability, storage, dashboard, alerting, and the general software/API/infrastructure security measures) carries over unchanged.
