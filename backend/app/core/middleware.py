import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from backend.app.core.logging import logger

class RequestTracingMiddleware(BaseHTTPMiddleware):
    """
    Enterprise request tracing and telemetry middleware:
    1. Attaches unique X-Request-ID for distributed tracing across microservices.
    2. Calculates precise server processing duration (X-Process-Time-Ms).
    3. Injects defensive HTTP security headers.
    4. Logs slow requests (> 150ms) for observability.
    """
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Extract or generate Request ID
        request_id = request.headers.get("X-Request-ID") or f"req-{uuid.uuid4().hex[:12]}"
        request.state.request_id = request_id
        
        start_time = time.perf_counter()
        
        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            logger.error(
                f"{request.method} {request.url.path} failed with unhandled exception: {exc}",
                extra={"request_id": request_id, "duration_ms": duration_ms}
            )
            raise exc

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        
        # Attach tracing and timing headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-Ms"] = f"{duration_ms:.2f}"
        
        # Defensive Security Headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Structured log for slow requests or errors
        if duration_ms > 200.0 or response.status_code >= 400:
            logger.warning(
                f"{request.method} {request.url.path} -> {response.status_code} ({duration_ms:.2f}ms)",
                extra={"request_id": request_id, "duration_ms": duration_ms}
            )
            
        return response
