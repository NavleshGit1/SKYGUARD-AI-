import hmac
import hashlib
import json
import uuid
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Union
from jose import jwt
from backend.app.core.config import settings

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def create_access_token(
    subject: Union[str, Any],
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[dict] = None
) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    # VULN-08 FIX: Add unique JTI (JWT ID) for per-token revocation support
    to_encode = {"exp": expire, "sub": str(subject), "jti": str(uuid.uuid4())}
    if extra_claims:
        to_encode.update(extra_claims)
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_telemetry_signature(
    station_id: str,
    timestamp_iso: str,
    payload_dict: dict,
    signature: str,
    secret_key: Optional[str] = None
) -> bool:
    """
    Validates HMAC-SHA256 signature for incoming telemetry.
    Signature = HMAC_SHA256(secret, station_id:timestamp_iso:payload_json)
    """
    key = secret_key or settings.TELEMETRY_HMAC_SECRET
    payload_str = json.dumps({
        "temperature_c": payload_dict.get("temperature_c"),
        "pressure_hpa": payload_dict.get("pressure_hpa"),
        "humidity_pct": payload_dict.get("humidity_pct")
    }, sort_keys=True)
    
    expected_msg = f"{station_id}:{timestamp_iso}:{payload_str}".encode("utf-8")
    expected_sig = hmac.new(key.encode("utf-8"), expected_msg, hashlib.sha256).hexdigest()
    
    return hmac.compare_digest(expected_sig, signature)
