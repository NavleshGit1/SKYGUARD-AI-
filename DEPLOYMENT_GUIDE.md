# 🚀 SkyGuard AI — Cloud Deployment Guide (Render + Vercel)

This guide walks you through deploying **SkyGuard AI** to the cloud:
- **Backend (FastAPI + AI/ML Engine + WebSockets)** on **[Render](https://render.com/)**
- **Frontend (React 18 SPA + Vite + TailwindCSS)** on **[Vercel](https://vercel.com/)**

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────┐
│           Vercel Frontend               │
│   https://skyguard.vercel.app           │
│   (React 18 SPA + Vite + Recharts)      │
└──────────────┬──────────────────────────┘
               │
               │ HTTPS (REST API) & WSS (Live WebSocket Feed)
               ▼
┌─────────────────────────────────────────┐
│            Render Backend               │
│   https://skyguard-backend.onrender.com │
│   (FastAPI + ML Ensemble + WebSocket)   │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│        Render Managed PostgreSQL        │
│   (TimescaleDB / Relational Store)      │
└─────────────────────────────────────────┘
```

---

## 📦 Part 1: Deploy Backend to Render

### Option A: Using Render Blueprints (1-Click Deploy)
1. Push your repository to **GitHub** or **GitLab**.
2. Go to your [Render Dashboard](https://dashboard.render.com/).
3. Click **"New"** → **"Blueprint"**.
4. Connect your repository. Render will automatically detect [`render.yaml`](./render.yaml) and configure:
   - **`skyguard-backend`** (FastAPI Web Service)
   - **`skyguard-timescale`** (Managed PostgreSQL Database)
   - **`skyguard-simulator`** (Background Telemetry Generator Worker)
5. Click **"Apply"** to deploy.

---

### Option B: Manual Web Service Setup on Render
If configuring manually:
1. In Render, click **"New"** → **"Web Service"** and connect your repo.
2. Fill in the service configuration:
   - **Name**: `skyguard-backend`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`
   - **Health Check Path**: `/api/v1/health`
3. Add the following **Environment Variables**:
   | Key | Value / Instructions |
   | :--- | :--- |
   | `PYTHON_VERSION` | `3.11.9` |
   | `ENVIRONMENT` | `production` |
   | `DEBUG` | `false` |
   | `SECRET_KEY` | *(Click "Generate" on Render or use `python -c "import secrets; print(secrets.token_hex(32))"`)* |
   | `TELEMETRY_HMAC_SECRET` | *(Click "Generate" on Render)* |
   | `ALGORITHM` | `HS256` |
   | `ACCESS_TOKEN_EXPIRE_MINUTES` | `120` |
   | `DATABASE_URL` | *(Paste your Render PostgreSQL connection string or external DB URL)* |
   | `FRONTEND_URL` | `https://your-app-name.vercel.app` *(update after Vercel deploy)* |
4. Click **"Create Web Service"**.
5. Once deployed, copy your backend URL (e.g., `https://skyguard-backend.onrender.com`).

---

## ⚡ Part 2: Deploy Frontend to Vercel

1. Log into your [Vercel Dashboard](https://vercel.com/).
2. Click **"Add New..."** → **"Project"** and import your Git repository.
3. In the project setup screen:
   - **Framework Preset**: `Vite`
   - **Root Directory**: Click "Edit" and select `frontend` (or leave default if using root [`vercel.json`](./vercel.json))
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
4. Expand **"Environment Variables"** and add:
   | Key | Value | Description |
   | :--- | :--- | :--- |
   | `VITE_API_BASE_URL` | `https://skyguard-backend.onrender.com` | Your Render backend HTTPS URL |
   | `VITE_WS_BASE_URL` | `wss://skyguard-backend.onrender.com/api/v1/ws/live-feed` | *(Optional)* Render backend WSS URL |
5. Click **"Deploy"**.

---

## 🔗 Part 3: Connect Frontend & Backend CORS

1. Return to your **Render Backend Web Service** settings.
2. Set the `FRONTEND_URL` environment variable to your live Vercel domain:
   ```
   FRONTEND_URL = https://skyguard.vercel.app
   ```
3. Render will redeploy and automatically whitelist your Vercel URL for CORS and WebSockets.

---

---

## ⏰ Part 4: 24/7 Render Anti-Sleep Keep-Alive (Zero Spin-Down)

Render Free Web Services spin down into sleep mode after 15 minutes of inactivity. We have implemented **3 automatic layers** to keep your backend awake 24/7:

### 1. Built-in FastAPI Self-Pinger (Automatic)
The backend includes a background pinger in [`backend/app/services/keep_alive.py`](./backend/app/services/keep_alive.py). When deployed on Render, it automatically detects `RENDER_EXTERNAL_URL` and issues an inbound `GET /api/v1/health` request every **10 minutes (600s)**, resetting the 15-minute inactivity timer.

### 2. GitHub Actions 24/7 Free Scheduled Pinger (Cloud-Native)
A GitHub Actions workflow is included at [`.github/workflows/keep_alive.yml`](./.github/workflows/keep_alive.yml).
- Automatically triggers every **10 minutes** via GitHub's free runners.
- **Setup**:
  1. In your GitHub repository, go to **Settings** → **Secrets and variables** → **Actions**.
  2. Add a new repository secret:
     - **Name**: `RENDER_BACKEND_URL`
     - **Value**: `https://your-backend.onrender.com` (your Render URL)
  3. GitHub Actions will ping your Render backend every 10 minutes, keeping it online 24/7 with zero maintenance.

### 3. External Monitoring (Optional / Backup)
You can also register your backend on free ping monitors:
- **[UptimeRobot](https://uptimerobot.com/)**: Add a free HTTP(s) monitor for `https://your-backend.onrender.com/api/v1/health` with a 5-minute interval.
- **[Cron-Job.org](https://cron-job.org/)**: Create a free cron job targeting `https://your-backend.onrender.com/api/v1/health` every 10 minutes.

---

## ✅ Post-Deployment Verification Checklist

1. **Backend Health Check**:
   Navigate to `https://your-backend.onrender.com/api/v1/health` in your browser. It should return:
   ```json
   { "status": "healthy", "service": "SkyGuard AI", "version": "1.0.0", "database": "connected" }
   ```
2. **Frontend Live Feed**:
   Open `https://your-app.vercel.app`.
   - The top header indicator will display **LIVE FEED** (green dot).
   - All 5 AWS stations (Delhi, Mumbai, Chennai, Kolkata, Jaipur) will appear on the GIS map.
   - Real-time telemetry will scroll in the live ticker.
3. **Operator Authentication**:
   - Click **"Operator Login"**.
   - Default credentials: `admin@skyguard.ai` / `admin123`.

