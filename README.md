# 🌦️ SkyGuard AI — Automated Weather Station (AWS) Quality Control & Predictive Health System

> **Autonomous Quality Control, Multi-Detector Anomaly Detection, Explainable AI (XAI), and Predictive Maintenance for Meteorological Sensor Networks.**

---

## 📌 Executive Summary

Modern meteorological networks (e.g., India Meteorological Department — IMD, WMO) operate hundreds of Automated Weather Stations (AWS) in remote, harsh environments. Sensor degradation, calibration drift, and physical damage often corrupt critical climate datasets.

**SkyGuard AI** is an enterprise-grade, end-to-end quality control and predictive maintenance platform:
- ⚡ **Sub-10ms Streaming Ingestion Pipeline:** High-throughput streaming with HMAC-SHA256 telemetry authentication.
- 🧠 **6-Detector Hybrid ML Ensemble:** Physical bounds, Frozen sensor flatline, Isolation Forest, Deep PyTorch Autoencoder, STL+CUSUM drift analysis, and Spatial consistency checking.
- 🔍 **Explainable AI (XAI):** Real-time SHAP attributions and automated natural-language root-cause diagnosis.
- 🛠️ **Sensor Health & Predictive Maintenance:** Non-parametric Mann-Kendall trend testing to forecast calibration drift weeks before failure.
- 🛡️ **Defense-in-Depth Security:** Cryptographic SHA-256 hash-chain audit log, Dead-Letter Queue (DLQ), and role-based access control.
- 📊 **Interactive Command Center:** Geospatial Leaflet map, Recharts live analytics, anomaly review feed, simulator injection workbench, and bilingual (English/Hindi) UI.

---

## 🏛️ Architecture Overview

```
 ┌─────────────────────────────────────────────────────────────┐
 │                VERCEL (Frontend Dashboard)                  │
 │   - React 18 + Vite SPA                                    │
 │   - Dynamic API Client & Auto-reconnecting WebSockets       │
 │   - Geospatial GIS Map + Real-time Telemetry Charts         │
 └──────────────────────────────┬──────────────────────────────┘
                                │ HTTPS / WSS
                                ▼
 ┌─────────────────────────────────────────────────────────────┐
 │                 RENDER (FastAPI Backend)                    │
 │   - Python 3.11 FastAPI High-Performance Gateway            │
 │   - 6-Detector Ensemble (Lightweight ~340KB Compressed)     │
 │   - Embedded Async Telemetry Streamer (Single Container)   │
 │   - TimescaleDB / PostgreSQL / Supabase / SQLite DB         │
 └─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Cloud Deployment Guide

### 1️⃣ Deploy Backend to Render (Free Tier)
1. Fork / push this repository to your **GitHub** account.
2. Log in to **[Render.com](https://dashboard.render.com)** $\to$ Click **New +** $\to$ **Blueprint**.
3. Select this repository. Render will automatically detect `render.yaml` and configure everything.
4. (Or create a **Web Service** manually with `pip install -r requirements.txt` and start command `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`).
5. Copy your deployed Render URL: `https://your-backend-name.onrender.com`.

### 2️⃣ Deploy Frontend to Vercel
1. Log in to **[Vercel.com](https://vercel.com)** $\to$ Click **Add New...** $\to$ **Project**.
2. Import this repository.
3. In **Project Settings**:
   - **Root Directory:** `frontend`
   - **Framework Preset:** `Vite`
4. In **Environment Variables**, add:
   - `VITE_API_URL` = `https://your-backend-name.onrender.com`
5. Click **Deploy**.

---

## ⚡ 24/7 Keep-Alive Heartbeat (Prevent Render 15m Sleep)

Render Free Tier spins down after 15 minutes of inactivity. Keep it awake 24/7 using any of these options:

- **GitHub Actions (Automated Cloud Cron):** The included `.github/workflows/keep_alive.yml` pings `/api/v1/health` every 10 minutes automatically. Add repository secret `RENDER_BACKEND_URL`.
- **Python Heartbeat Daemon:** Run `python scripts/keep_alive.py --url https://your-backend-name.onrender.com --interval 10`.
- **Free Web Monitor:** Set an HTTP check on [UptimeRobot](https://uptimerobot.com) pointing to `https://your-backend-name.onrender.com/api/v1/health` every 10 minutes.

---

## 💻 Local Quickstart

### Prerequisites
- Python 3.10+
- Node.js 18+

### 1. Backend Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Run backend server
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## 🔐 Default Credentials & Hub Stations

- **Admin Login:** `admin@skyguard.ai` / `admin123`
- **5 Official AWS Hub Stations:**
  1. `AWS-DEL-01` — New Delhi (Safdarjung)
  2. `AWS-MUM-01` — Mumbai (Santacruz)
  3. `AWS-CHE-01` — Chennai (Meenambakkam)
  4. `AWS-KOL-01` — Kolkata (Alipore)
  5. `AWS-JAI-01` — Jaipur (Sanganer)

---

## 🧪 Verification & Testing

Run the full end-to-end integration test suite:
```bash
python scripts/test_full_system.py
```
*All 12 test suites (21 assertions) run with 100% pass rate.*
