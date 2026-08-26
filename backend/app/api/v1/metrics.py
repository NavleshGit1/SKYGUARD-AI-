import time
import os
import threading
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Dict, Any

from backend.app.core.database import get_db, engine
from backend.app.core.cache import station_cache
from backend.app.services.metrics import metrics
from backend.app.api.v1.websocket import ws_manager

router = APIRouter(tags=["Observability & Metrics"])

@router.get("/metrics", response_model=Dict[str, Any], summary="Real-Time Performance & Pipeline Telemetry")
async def get_system_metrics():
    """
    Returns real-time pipeline latency percentiles (P50, P95, P99),
    QPS throughput, anomaly classification breakdown, and cache hit ratios.
    """
    summary = metrics.get_summary()
    summary["cache"] = station_cache.stats
    summary["websocket_active_connections"] = ws_manager.active_connections_count
    return summary

@router.get("/metrics/prometheus", summary="Prometheus Scraping Metrics")
async def get_prometheus_metrics():
    """
    Prometheus-formatted text exposition for scraping by Prometheus, Grafana, or Datadog.
    """
    summary = metrics.get_summary()
    lines = [
        "# HELP skyguard_ingest_total Total number of telemetry records ingested",
        "# TYPE skyguard_ingest_total counter",
        f"skyguard_ingest_total {summary['total_readings_ingested']}",
        "",
        "# HELP skyguard_anomalies_total Total anomalies detected by hybrid ensemble",
        "# TYPE skyguard_anomalies_total counter",
        f"skyguard_anomalies_total {summary['total_anomalies_flagged']}",
        "",
        "# HELP skyguard_pipeline_latency_ms Ingestion pipeline latency in milliseconds",
        "# TYPE skyguard_pipeline_latency_ms gauge",
        f"skyguard_pipeline_latency_ms{{quantile=\"0.50\"}} {summary['latency_profile_ms']['p50']}",
        f"skyguard_pipeline_latency_ms{{quantile=\"0.95\"}} {summary['latency_profile_ms']['p95']}",
        f"skyguard_pipeline_latency_ms{{quantile=\"0.99\"}} {summary['latency_profile_ms']['p99']}",
        "",
        "# HELP skyguard_cache_hit_ratio_percent Station metadata cache hit ratio",
        "# TYPE skyguard_cache_hit_ratio_percent gauge",
        f"skyguard_cache_hit_ratio_percent {station_cache.stats['hit_ratio_pct']}",
        "",
        "# HELP skyguard_active_ws_clients Number of active live feed WebSocket dashboard connections",
        "# TYPE skyguard_active_ws_clients gauge",
        f"skyguard_active_ws_clients {ws_manager.active_connections_count}"
    ]
    return Response(content="\n".join(lines), media_type="text/plain; version=0.0.4")

@router.get("/system/diagnostics", summary="Deep Infrastructure & Database Diagnostics")
async def get_system_diagnostics(db: Session = Depends(get_db)):
    """
    Comprehensive health check testing TimescaleDB connection latency,
    connection pool occupancy, memory utilization, and thread statistics.
    """
    # 1. Test Database Round-Trip Latency
    db_start = time.perf_counter()
    db_status = "UNKNOWN"
    db_latency_ms = 0.0
    try:
        db.execute(text("SELECT 1"))
        db_latency_ms = round((time.perf_counter() - db_start) * 1000.0, 2)
        db_status = "HEALTHY"
    except Exception as e:
        db_status = f"ERROR: {str(e)}"

    # 2. Process & Thread stats
    mem_mb = None
    try:
        import psutil
        proc = psutil.Process(os.getpid())
        mem_mb = round(proc.memory_info().rss / (1024 * 1024), 2)
    except ImportError:
        pass

    # 3. Connection Pool Info
    pool = engine.pool

    return {
        "status": "OPERATIONAL" if db_status == "HEALTHY" else "DEGRADED",
        "database": {
            "status": db_status,
            "latency_ms": db_latency_ms,
            "pool_size": pool.size(),
            "checked_in_connections": pool.checkedin(),
            "checked_out_connections": pool.checkedout(),
            "overflow_connections": pool.overflow()
        },
        "cache": station_cache.stats,
        "websocket_active_clients": ws_manager.active_connections_count,
        "process": {
            "pid": os.getpid(),
            "memory_rss_mb": mem_mb,
            "active_threads": threading.active_count()
        }
    }
