import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from backend.app.core.logging import logger

class SkyGuardException(Exception):
    """Base application exception for SkyGuard AI"""
    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_SERVER_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}

class StationNotFoundError(SkyGuardException):
    def __init__(self, station_id: str):
        super().__init__(
            message=f"Weather Station '{station_id}' was not found in the registry.",
            code="STATION_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"station_id": station_id}
        )

class SignatureVerificationError(SkyGuardException):
    def __init__(self, station_id: str, reason: str = "HMAC signature mismatch"):
        super().__init__(
            message=f"Cryptographic authentication failed for station '{station_id}': {reason}",
            code="AUTHENTICATION_FAILED",
            status_code=status.HTTP_401_UNAUTHORIZED,
            details={"station_id": station_id, "reason": reason}
        )

class InvalidTelemetryError(SkyGuardException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="INVALID_TELEMETRY",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details or {}
        )

def build_error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {
                "code": code,
                "message": message,
                "details": details or {}
            },
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        },
        headers={"X-Request-ID": request_id}
    )

async def app_exception_handler(request: Request, exc: SkyGuardException) -> JSONResponse:
    logger.warning(f"Domain Exception [{exc.code}]: {exc.message}")
    return build_error_response(
        request=request,
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.details
    )

async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return build_error_response(
        request=request,
        status_code=exc.status_code,
        code=f"HTTP_{exc.status_code}",
        message=str(exc.detail)
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = []
    for err in exc.errors():
        loc = " -> ".join([str(x) for x in err.get("loc", [])])
        errors.append({
            "field": loc,
            "message": err.get("msg"),
            "type": err.get("type")
        })
    return build_error_response(
        request=request,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        code="SCHEMA_VALIDATION_ERROR",
        message="The request payload failed Pydantic meteorological schema validation.",
        details={"validation_errors": errors}
    )
