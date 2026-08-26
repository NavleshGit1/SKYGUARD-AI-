from fastapi import APIRouter
from backend.app.api.v1.auth import router as auth_router
from backend.app.api.v1.stations import router as stations_router
from backend.app.api.v1.anomalies import router as anomalies_router
from backend.app.api.v1.ingest import router as ingest_router
from backend.app.api.v1.simulator import router as simulator_router
from backend.app.api.v1.websocket import router as ws_router
from backend.app.api.v1.audit import router as audit_router
from backend.app.api.v1.models import router as models_router
from backend.app.api.v1.admin import router as admin_router
from backend.app.api.v1.metrics import router as metrics_router
from backend.app.api.v1.dlq import router as dlq_router

router = APIRouter()

router.include_router(auth_router,      tags=["Authentication"])
router.include_router(stations_router,  tags=["Stations & Telemetry"])
router.include_router(anomalies_router, tags=["Anomalies & Alerts"])
router.include_router(ingest_router,    tags=["Data Ingestion Pipeline"])
router.include_router(metrics_router,   tags=["Observability & Metrics"])
router.include_router(simulator_router, tags=["Simulator Controls"])
router.include_router(ws_router,        tags=["WebSocket Live Feed"])
router.include_router(audit_router,     tags=["Cryptographic Audit Trail"])
router.include_router(models_router,    tags=["Model Registry & Evaluation Store"])
router.include_router(admin_router,     tags=["Admin Controls"])
router.include_router(dlq_router,       tags=["Dead-Letter Queue"])

