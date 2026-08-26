@echo off
title SkyGuard AI - Launch Center
echo =======================================================================
echo                 SKYGUARD AI - FULL-STACK SYSTEM LAUNCHER
echo =======================================================================
echo.

echo [1/4] Checking & Starting Docker Services (TimescaleDB + Redis)...
docker compose up -d timescaledb redis
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Docker must be running! Please start Docker Desktop and retry.
    pause
    exit /b 1
)

echo.
echo [2/4] Starting FastAPI Backend on Port 8000...
start "SkyGuard AI - Backend API" cmd /k "python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000"

echo.
echo [3/4] Starting Real-Time Telemetry Stream Simulator...
start "SkyGuard AI - Telemetry Simulator" cmd /k "python -m simulator.run"

echo.
echo [4/4] Starting React + Vite Frontend Dashboard on Port 5173...
cd frontend
start "SkyGuard AI - Frontend UI" cmd /k "npm run dev"
cd ..

echo.
echo =======================================================================
echo   ALL SERVICES LAUNCHED SUCCESSFULLY!
echo.
echo   - Web Dashboard:    http://localhost:5173
echo   - Backend Swagger:  http://localhost:8000/docs
echo   - TimescaleDB:      localhost:5432 (skyguard_db)
echo   - Redis Buffer:     localhost:6379
echo   - Operator Login:   admin@skyguard.ai / admin123
echo =======================================================================
echo.
pause
