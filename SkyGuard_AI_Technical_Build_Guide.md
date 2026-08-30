# SkyGuard AI — Complete Technical Build Guide
### Real Technologies, How Model Training Actually Works, and Exactly How Every Layer Talks to the Next

This is the deep, technology-specific version. Every layer names the actual tools, explains the theory behind how its models are trained (not just "train a model"), and specifies exactly what data format and protocol connects it to its neighbors — so you could hand this to a developer and they'd know precisely what to install and build.

---

## PART A — Overall Technology Stack (What You Install)

| Purpose | Technology | Why this one |
|---|---|---|
| Programming language (core pipeline) | Python 3.11+ | Best ML/data ecosystem, every library below is Python-native |
| Data source simulator | Python script + pandas | Reads historical CSV, replays it |
| Message broker | Apache Kafka (or Redis Streams for a smaller/simpler build) | Durable, replayable, decouples producers from consumers |
| Stream processing | Python consumer service (or Kafka Streams / Faust) | Computes features on each incoming message |
| Classical ML | scikit-learn, PyOD | Isolation Forest, Local Outlier Factor, robust statistics |
| Deep learning | PyTorch | Autoencoder, LSTM-Autoencoder |
| Time-series decomposition | statsmodels (STL) | Seasonal/trend decomposition |
| Change-point detection | ruptures | CUSUM/PELT algorithms for drift detection |
| Explainability | SHAP, LIME | Feature attribution |
| Time-series database | TimescaleDB (PostgreSQL extension) | SQL-familiar, purpose-built for time series |
| Event/metadata database | PostgreSQL (same instance, different tables/schema) | Relational, ACID, works well with TimescaleDB |
| Backend API framework | FastAPI | Async, built-in WebSocket support, auto-generates API docs |
| Frontend framework | React + Vite | Standard, large ecosystem |
| Charting | Recharts or Plotly.js | Time-series + anomaly overlay rendering |
| Mapping (if multi-station) | Leaflet.js | Free, no API key required (OpenStreetMap tiles) |
| Containerization | Docker + Docker Compose | Every service (broker, DB, API, frontend) runs as one container, wired together |
| Model serving/storage | MLflow (or a simple versioned file structure in the DB/disk) | Model registry with versioning |
| Secrets management | `.env` file + python-dotenv (dev), a real secrets manager (Vault/cloud KMS) in production | Keep credentials out of code |

---

## PART B — How Data Physically Moves Between Layers (The Contracts)

Before training anything, fix the **exact message format** every layer will send/receive. This is the single most important technical decision — get this right and every layer becomes swappable.

### B.1 — Raw Reading Message (Source → Ingestion)
A JSON object, one per reading, published to a Kafka topic called `raw-readings`:
```
station_id, timestamp (ISO 8601, UTC), temperature_c, pressure_hpa, humidity_pct,
latitude (optional), longitude (optional), altitude_m (optional)
```
The simulator (Part C) publishes to this topic. The ingestion service subscribes to it.

### B.2 — Validated + Enriched Reading (Ingestion → Feature Engineering)
Same fields as B.1, plus: `station_calibration_date`, `validation_status`. Published to a topic called `validated-readings`. Records that fail validation go to `dead-letter-readings` instead.

### B.3 — Feature Vector (Feature Engineering → Detection Engine)
A JSON object per reading containing every computed feature: rolling mean/std per window, rate-of-change, dew point, sea-level pressure, climatology deviation, missingness stats. Published to topic `feature-vectors`. This is also written to the **feature store** (a TimescaleDB table) so training jobs can pull historical feature vectors later.

### B.4 — Detector Output (Each Detector → Fusion Layer)
Each of the 5–6 detectors reads from `feature-vectors` and writes its own score to a shared in-memory/Redis structure or a topic `detector-scores`, keyed by `(station_id, timestamp, detector_name) → score (0–1)`.

### B.5 — Anomaly Event (Fusion → Explainability → Decision → Storage)
Once all detectors report in for a given reading, the fusion service assembles the final **Anomaly Event** object (severity, confidence, per-detector votes) and publishes it to topic `anomaly-events`. Explainability and Decision services both subscribe to this topic, enrich it, and the final enriched version is written to the PostgreSQL `anomaly_events` table.

### B.6 — API Layer (Storage → Dashboard)
The FastAPI backend never touches Kafka directly for reads — it only queries the PostgreSQL/TimescaleDB tables, and exposes that data over REST endpoints and a WebSocket channel (`/ws/live-feed`) that pushes new anomaly events to connected dashboard clients the moment they're written to the DB (via a PostgreSQL `LISTEN/NOTIFY` trigger, or by the fusion service also pushing directly to the WebSocket broadcaster).

This message-contract approach means: **any layer can be rebuilt or swapped later, as long as it still reads/writes the same topic format.**

---

## PART C — Building the Data Source / Simulator

**Technology:** Python script using `pandas` to read a historical CSV/dataset, and `kafka-python` (or `confluent-kafka`) to publish.

**How it works step by step:**
1. Load historical data (temperature/pressure/humidity time series per station) into a pandas DataFrame.
2. Sort by timestamp.
3. Loop through rows, publishing each as a `raw-readings` Kafka message, with a small delay between messages to simulate real-time pace (or no delay, for fast batch replay during evaluation).
4. **Anomaly injection mode:** before publishing, randomly select rows and apply a transformation:
   - Spike: add/subtract a large random offset
   - Frozen: repeat the previous value for N consecutive rows instead of the real one
   - Drift: add a slowly-increasing offset across a window of rows
   - Dropout: skip publishing entirely for a window (simulates comms failure)
   - Noise: add random Gaussian noise to a burst of rows
   - Multivariate inconsistency: perturb humidity without adjusting temperature, breaking the dew-point relationship
5. Log every injected anomaly (which row, what type, what magnitude) to a separate **ground-truth file** — this is what you'll later compare detector outputs against to compute accuracy.

**Connects to:** publishes directly onto the `raw-readings` Kafka topic (Contract B.1). Nothing downstream needs to know whether it's real or simulated data.

---

## PART D — Building the Ingestion Layer

**Technology:** A Python service (FastAPI background worker, or a plain Kafka consumer script) subscribed to `raw-readings`.

**How it works:**
1. **Schema validation:** use a library like `pydantic` to define the expected message shape; any message that fails validation (missing field, wrong type, value out of physically possible range) is published to `dead-letter-readings` instead of proceeding.
2. **Metadata join:** for each valid reading, look up the station's record in the PostgreSQL `stations` table (location, altitude, calibration date) and attach it to the message.
3. **Timestamp check:** compare the message timestamp to current time / to the last seen timestamp for that station; flag large jumps or out-of-order arrival as a `timestamp_anomaly` flag on the message (this becomes input to the communication-error detector later).
4. Publish the enriched result to `validated-readings` (Contract B.2).

**Connects to:** consumes `raw-readings`, reads from PostgreSQL `stations` table, produces `validated-readings`.

---

## PART E — Building the Feature Engineering Layer

**Technology:** A Python streaming consumer, using `pandas`/`numpy` for calculations, maintaining a small rolling window of recent readings per station in memory (or in Redis, for a multi-instance deployment).

**How each feature is actually computed:**

- **Rolling statistics:** maintain the last N readings per station in a buffer (e.g., a `collections.deque`). On each new reading, compute mean, standard deviation, and median absolute deviation (MAD) over that buffer for multiple window sizes (5-minute, 1-hour, 24-hour — meaning you keep multiple buffers of different lengths).
- **Rate of change:** simple subtraction — `current_value - previous_value`, divided by the time elapsed, gives you the first derivative; do it again on the derivative series for the second derivative.
- **Dew point:** computed using the Magnus formula, a standard meteorological equation that takes temperature and relative humidity and returns dew point in °C. This is a deterministic formula, not a trained model — you compute it directly.
- **Sea-level-reduced pressure:** a standard barometric formula that adjusts a station's raw pressure reading based on its altitude, so stations at different elevations become comparable. Also a deterministic formula.
- **Climatology deviation:** this one DOES require historical data and a small amount of "training" (really just statistics, not ML) — see Part F.1 below, since it's really the first of the "models."
- **Missingness features:** track, per station, the time since the last successfully received reading; if it exceeds the expected sampling interval by some multiple, that's your missingness signal.

**Connects to:** consumes `validated-readings`, writes to the `feature-vectors` topic AND to a permanent `feature_store` table in TimescaleDB (so historical features are available for model training later, not just live inference).

---

## PART F — Building and Training Each Detector (the core ML section)

This is the part that actually needs explaining in depth: **how do you "train" an anomaly detector when you don't have labeled examples of anomalies?** The answer, for most of these, is **unsupervised learning**: you train the model on data you believe is *mostly normal*, and it learns what "normal" looks like — anything that doesn't fit gets flagged. Here's exactly how, detector by detector.

### F.1 — Climatology Baseline (statistical model, not ML)
**Training process:** Group your historical dataset (Part 0.2 data) by station, by day-of-year (or month, if you don't have enough years of data), and by hour-of-day. For each group, compute the mean and standard deviation of temperature/pressure/humidity. This produces a lookup table: "for Station X, in July, around 2 PM, temperature is normally 28°C ± 4°C." At inference time, compare the live reading to this lookup table's expected range.
**Why this counts as "training":** you're literally learning the parameters (mean, std) of a normal distribution from historical data — this is the simplest form of statistical model fitting, just without gradient descent.

### F.2 — Rule/Physical Plausibility Detector
**No training needed.** This is pure logic: fixed physical bounds (e.g., temperature between -90°C and 60°C) plus the dew-point-must-be-≤-temperature check. You write these thresholds directly based on known physical limits, not learned from data.

### F.3 — Frozen/Stuck-Value Detector
**No training needed.** Deterministic rule: if the rolling window's standard deviation is exactly zero (or below a tiny epsilon), or if N consecutive readings are bit-for-bit identical, flag as frozen.

### F.4 — Statistical Point-Anomaly Detector (Isolation Forest)
**How Isolation Forest works (the theory):** It builds many random decision trees. Each tree repeatedly picks a random feature and a random split value to divide the data. The key insight: anomalies are "few and different," so they get isolated (separated into their own leaf) in far fewer random splits than normal points do. A point that gets isolated quickly (short average path length across all trees) is scored as more anomalous.

**Training process:**
1. Take your historical feature vectors (from the feature store, Part E) — ideally from a period you're confident is mostly normal, or just use everything and accept that a small amount of noise won't matter much since Isolation Forest is robust to some contamination.
2. Feed these feature vectors (rolling mean, std, rate-of-change) into scikit-learn's `IsolationForest`. You set a `contamination` parameter — your estimate of what fraction of the data is anomalous (start with a small guess like 1–5%, tune later using the injected-anomaly evaluation set).
3. The model builds its random trees purely from this data — this is the "fit" step, and it's fast (seconds to minutes even for large datasets).
4. At inference time, each new reading's feature vector gets a score from the trained forest — no retraining needed per reading, just a fast lookup through the trees.
5. **Retraining cadence:** periodically (e.g., weekly or monthly) retrain on the latest rolling window of historical data so the model adapts to genuinely-shifted normal conditions (e.g., seasonal transitions) rather than flagging every season change as anomalous forever.

**Alternative/complement:** robust z-score using MAD instead of standard deviation — simpler, no training at all, just a formula (`0.6745 * (x - median) / MAD`), useful as a fast first-pass filter before the heavier Isolation Forest runs.

### F.5 — Multivariate Consistency Detector (Autoencoder)
**How an autoencoder works (the theory):** It's a neural network with a bottleneck — it takes your input features (temperature, pressure, humidity, dew point, etc.), compresses them down to a small number of internal values (the "bottleneck," forcing the network to learn only the most essential relationships between the parameters), then tries to reconstruct the original input from that compressed version. If the network is trained only on normal data, it becomes very good at reconstructing normal combinations of T/P/RH — but when it sees a combination that violates the normal relationships it learned (e.g., humidity and temperature that don't physically go together), it reconstructs it poorly. The **reconstruction error** (how different the output is from the input) becomes your anomaly score.

**Training process, step by step:**
1. Take historical feature vectors — specifically the physics-relevant ones (temperature, pressure, humidity, dew point, sea-level pressure).
2. Normalize/scale all features to a similar range (e.g., 0 to 1) — neural networks train much better when inputs are on comparable scales. Save these scaling parameters; you must apply the exact same scaling at inference time.
3. Split into a training set and a validation set (e.g., 80/20).
4. Build a small feedforward network: input layer (size = number of features) → a smaller hidden layer → an even smaller "bottleneck" layer → back up through a mirrored expanding set of layers → output layer (same size as input).
5. **Loss function:** Mean Squared Error between the input and the reconstructed output — the network's entire objective during training is to minimize this reconstruction error on normal data.
6. Train using an optimizer (Adam is standard) over multiple passes through the data (epochs), watching the validation loss to make sure the network is generalizing and not just memorizing (stop training — "early stopping" — once validation loss stops improving).
7. After training, run the network on your validation set (still normal data) to see the typical/expected reconstruction error range — this becomes your **threshold**: anything reconstructed with error significantly above this normal range gets flagged.
8. **Retraining cadence:** similar to Isolation Forest — periodic retraining as more historical data accumulates.

### F.6 — Temporal/Seasonal Drift Detector
**How it works (the theory):** This isn't one algorithm but two working together:
- **STL decomposition** (Seasonal-Trend decomposition using Loess) mathematically splits a time series into three components: a smooth long-term Trend, a repeating Seasonal pattern, and leftover Residual noise. This isn't a trained model in the ML sense — it's a statistical decomposition method applied to a rolling window of recent data.
- **Change-point detection (CUSUM or PELT, via the `ruptures` library)** watches the Residual component (or the raw series) for a statistically significant shift in its average level or trend — this is what catches "the sensor has been drifting 0.5°C higher every week for the last month," which a simple point-anomaly detector would miss because no single reading looks that extreme.

**"Training" here means:** feeding a rolling window of recent history (e.g., last 30–90 days) into the STL decomposition and change-point algorithm each time you re-evaluate — there's no persistent trained model file the way there is with the autoencoder; it's recomputed fresh on each evaluation window. For very long-history stations, you can instead train an LSTM-Autoencoder (same reconstruction-error logic as F.5, but using a recurrent network that reads a *sequence* of past readings instead of a single reading, letting it learn temporal patterns, not just cross-parameter relationships).

### F.7 — Spatial Consistency Detector (optional)
**How it works:** Use spatial interpolation (Inverse Distance Weighting or Kriging) across neighboring stations' current readings to estimate "what should this location's reading be right now, based on what nearby stations are seeing." Compare the actual reading to this estimate. This requires station location data and at least a handful of nearby stations — it's a geostatistics technique, not a neural network, and doesn't require training in the ML sense, just a working set of neighboring stations' live data at inference time.

### F.8 — Fusion Layer (combining all detector scores)
**Two options, in increasing sophistication:**
1. **Simple weighted average (no training):** manually assign each detector a weight (e.g., Rule=1.0, Frozen=1.0, Statistical=0.8, Multivariate=1.0, Drift=0.7) reflecting how much you trust each one, and combine scores into one severity number. Start here — it's transparent and good enough for a first working version.
2. **Trained meta-model (logistic regression or small gradient-boosted model):** once you have the synthetic anomaly injection framework (Part C) with known ground-truth labels, treat "was this actually an injected anomaly, yes/no" as the target, and each detector's score as an input feature. Train a simple logistic regression (or `XGBoost`/`LightGBM` classifier) on this labeled data — this is genuinely *supervised* learning, made possible only because you have synthetic ground truth. The trained model learns the optimal weighting of each detector automatically, and can also learn detector *interactions* (e.g., "Statistical + Drift both firing together is much more serious than either alone") that a manual weighted average can't capture.

**Connects to:** reads every detector's output from `detector-scores`, writes the combined verdict to `anomaly-events` (Contract B.5).

---

## PART G — Building the Explainability Layer

**Technology:** SHAP (`shap` Python library), LIME (`lime` library) as fallback.

**How SHAP actually works (the theory):** SHAP is based on a concept from game theory called Shapley values — originally designed to fairly divide a reward among players who contributed unequally to a team's outcome. Applied to ML, each *feature* is treated like a "player" contributing to the model's prediction, and SHAP calculates each feature's fair share of responsibility for the final anomaly score by testing how the prediction changes when that feature is included versus excluded, across many different combinations of features. The result is a set of numbers, one per feature, showing exactly how much each feature pushed the anomaly score up or down for this specific reading.

**How you apply it here:**
1. For the Isolation Forest and any trained fusion meta-model, use SHAP's `TreeExplainer` (fast, exact, designed for tree-based models like these).
2. For the autoencoder, SHAP's `DeepExplainer` or `KernelExplainer` can be used, though a simpler and faster alternative is to just directly compare each individual feature's own reconstruction error (input vs output for that one feature) — since the autoencoder already naturally decomposes its error by feature, you often don't need full SHAP here at all.
3. Take the top 1–3 highest-contributing features from SHAP's output and plug them into a text template: *"Flagged primarily due to [feature name] deviating from expected pattern by [amount]."*

**Root-cause tagging (a separate, simpler piece — no ML at all):** a lookup table / decision tree written directly in code: `if frozen_detector_fired and nothing_else: root_cause = "stuck sensor"`, `if drift_detector_fired and nothing_else: root_cause = "calibration drift"`, and so on, based on the pattern of which detectors fired (from the fusion layer's per-detector vote breakdown).

**Connects to:** subscribes to `anomaly-events`, adds SHAP explanation + root-cause label, republishes the enriched event (or writes directly to the `anomaly_events` PostgreSQL table).

---

## PART H — Building the Decision & Action Layer

**Technology:** Plain Python service logic, no special ML library needed here (this layer mostly consumes outputs from earlier layers).

- **Corrected value estimation:** for short gaps, use `pandas`/`scipy` interpolation functions (linear or spline) on recent trusted history. For multivariate faults, take the autoencoder's own reconstructed output (F.5) — the network's "best guess at what a normal reading would look like" is literally sitting right there as a byproduct of detection, so reuse it directly rather than building a separate correction model.
- **Sensor health score:** a formula, not a trained model — e.g., a weighted combination of (recent anomaly frequency) + (drift magnitude trend) + (missing-data rate) + (time since calibration), each normalized to 0–1 and combined.
- **Predictive maintenance signal:** apply a simple trend test (e.g., linear regression slope, or Mann-Kendall trend test) on the health score's last several weeks of values — a statistically significant worsening trend triggers the maintenance flag. This is a lightweight statistical test, not a deep model, because there's no labeled failure-history dataset to train a real predictive model on.
- **Alert manager:** deduplication logic (don't re-alert on the same ongoing issue within a cooldown window) plus routing rules (severity thresholds mapped to channels).

**Connects to:** consumes `anomaly-events` (now enriched with explanation), writes the final complete record to the PostgreSQL `anomaly_events` table, and calls out to alerting integrations (SMTP library for email, Twilio SDK for SMS, a webhook POST request for Slack).

---

## PART I — Building the Storage Layer

**Technology:** PostgreSQL with the TimescaleDB extension enabled.

- `readings` table (a **hypertable** in TimescaleDB — a special table type optimized for time-series data, automatically partitioned by time): station_id, timestamp, temperature, pressure, humidity, and a flag for whether the value shown is raw or corrected.
- `anomaly_events` table: event_id, station_id, timestamp, severity, confidence, root_cause, explanation_text, per-detector scores (stored as a JSON column), resolution_status.
- `stations` table: station_id, name, latitude, longitude, altitude, install_date, last_calibration_date.
- `model_registry` table (or use MLflow's own tracking database): model_name, version, training_date, file path/reference, performance metrics from last evaluation.

**Why TimescaleDB specifically:** it's regular PostgreSQL (so you use normal SQL, no new query language to learn) but automatically handles the efficient storage and fast querying of time-ordered data at scale, which a plain relational table struggles with once you have millions of rows.

**Connects to:** every earlier layer writes here (ingestion writes readings, fusion/explainability/decision write anomaly events); the API layer (Part J) only ever reads/writes here, never touching Kafka directly.

---

## PART J — Building the Backend API

**Technology:** FastAPI (Python), running as its own Docker container.

**Endpoints to build:**
- `GET /stations` — list all stations and their current health status (reads `stations` + latest health score)
- `GET /stations/{id}/readings?from=&to=` — historical readings for charting
- `GET /anomalies?station_id=&severity=&from=&to=` — filterable anomaly event feed
- `GET /anomalies/{id}` — full detail of one anomaly, including SHAP explanation
- `WS /ws/live-feed` — a WebSocket connection the dashboard opens once and keeps open; the server pushes new anomaly events the moment they're written to the database (implemented either via PostgreSQL's `LISTEN/NOTIFY` feature, which lets the database itself announce new rows, or by having the Decision layer service directly call the API's broadcast function after writing)
- `POST /auth/login` — returns a JWT token
- `POST /admin/thresholds` — protected endpoint (requires admin JWT role) to adjust fusion layer weights/thresholds
- `POST /admin/retrain` — protected endpoint to trigger a retraining job (Part F's training steps, run as a background task)

**Connects to:** reads/writes PostgreSQL/TimescaleDB directly using an ORM (SQLAlchemy) or async driver (`asyncpg`); the frontend (Part K) talks to this API exclusively over HTTP/WebSocket — never touches the database directly.

---

## PART K — Building the Dashboard Frontend

**Technology:** React (with Vite as the build tool), Recharts/Plotly for charts, Leaflet for the map.

**How it connects, concretely:**
1. On page load, the React app calls `GET /stations` to populate the map/list.
2. It opens a WebSocket connection to `/ws/live-feed` once, and keeps a running list of the latest anomaly events in its local state, updating the UI instantly whenever a new message arrives over that socket — this is what makes the dashboard feel "live" without needing to constantly re-request data (polling).
3. Clicking a station triggers a `GET /stations/{id}/readings` call to populate that station's detail chart.
4. The admin panel's controls call the protected `POST /admin/...` endpoints, sending the JWT token obtained at login in the request header.

---

## PART L — Deployment: How All the Containers Are Wired Together

**Technology:** Docker Compose, defining one container per service, all on the same internal Docker network so they can reach each other by service name.

**Services in the compose file (conceptually, not code):**
1. `kafka` — the message broker
2. `timescaledb` — the database
3. `simulator` — the data source (Part C), connects to `kafka`
4. `ingestion` — connects to `kafka` (both subscribing and publishing) and `timescaledb`
5. `feature-engine` — connects to `kafka` and `timescaledb`
6. `detectors` — one service (or several) implementing all detectors from Part F, connects to `kafka`, loads trained model files from a shared volume or MLflow
7. `explainability` — connects to `kafka`
8. `decision` — connects to `kafka`, `timescaledb`, and external alert services (email/SMS/Slack)
9. `api` — connects to `timescaledb`, exposes port 8000 to the outside world
10. `frontend` — connects only to `api`, exposes port 80/443 to the outside world (through a reverse proxy)
11. `nginx` (reverse proxy) — sits in front of `api` and `frontend`, handles HTTPS/TLS termination, is the only container with ports exposed directly to the internet

**Every other container stays on the internal Docker network, unreachable from outside** — this is the practical implementation of the "network segmentation" security requirement discussed earlier: only `nginx` is internet-facing, everything else (database, broker, detectors) is only reachable from inside the Docker network.

---

## PART M — Putting It All Together: The Full Training & Evaluation Cycle

This ties Part F back to Part C's simulator, explaining the full loop you'll actually run:

1. Run the simulator in **injection mode** against your historical dataset, producing a labeled ground-truth file (which rows were tampered with, and how).
2. Feed the *non-injected* portion of your historical data through Parts D–E (ingestion, feature engineering) to populate the `feature_store` with clean, normal feature vectors.
3. Train each detector from Part F on this clean feature history (Isolation Forest's `.fit()`, the autoencoder's training loop, the climatology lookup table computation).
4. Run the *injected* (anomaly-containing) version of the dataset through the full live pipeline (Parts D through H) as if it were a real-time feed.
5. Compare each detector's (and the fusion layer's) flagged anomalies against the ground-truth injection log from step 1 — compute precision, recall, and F1-score per anomaly type.
6. Use these results to tune detector weights (or retrain the fusion meta-model), and repeat until performance is acceptable.
7. Only once this offline evaluation looks good do you point the simulator (or a real feed) at the live pipeline for an actual demo.

---

## Summary: The Complete Connection Chain, With Technology Names

```
[Simulator: Python+pandas]
   --publishes JSON to--> [Kafka topic: raw-readings]
        --consumed by--> [Ingestion: Python+pydantic, reads/writes PostgreSQL "stations" table]
             --publishes to--> [Kafka topic: validated-readings]
                  --consumed by--> [Feature Engine: Python+pandas/numpy/statsmodels]
                       --publishes to--> [Kafka topic: feature-vectors] + [TimescaleDB feature_store table]
                            --consumed by--> [Detectors: scikit-learn/PyOD IsolationForest, PyTorch Autoencoder,
                                               statsmodels STL + ruptures CUSUM, rule-based Python logic]
                                 --writes scores to--> [detector-scores]
                                      --read by--> [Fusion: weighted average or trained LogisticRegression/XGBoost]
                                           --publishes to--> [Kafka topic: anomaly-events]
                                                --consumed by--> [Explainability: SHAP TreeExplainer/DeepExplainer]
                                                     --enriches and passes to--> [Decision: Python logic + Twilio/SMTP/Slack SDKs]
                                                          --writes to--> [PostgreSQL/TimescaleDB anomaly_events table]
                                                               --read by--> [FastAPI backend]
                                                                    --served via REST/WebSocket to--> [React frontend]
                                                                         --all sitting behind--> [Nginx reverse proxy, HTTPS/TLS]
```

Every arrow above is a real, concrete technical connection — a Kafka topic name, a database table, or an HTTP/WebSocket call — not just a conceptual "hands off to." This is the level of specificity you'd need to actually start writing code for each service.
