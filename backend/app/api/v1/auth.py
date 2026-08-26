from fastapi import APIRouter, Depends, HTTPException, status, Body, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import Any
from pydantic import BaseModel, EmailStr

from backend.app.core.database import get_db
from backend.app.core.config import settings
from backend.app.core.security import verify_password, create_access_token
from backend.app.models.user import User
from jose import jwt, JWTError
from backend.app.core.limiter import limiter
from backend.app.core.cache import is_token_revoked, revoke_token_jti

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict

class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: str

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        # VULN-08 FIX: Check Redis JTI revocation blocklist
        jti: str = payload.get("jti")
        if jti and is_token_revoked(jti):
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.email == email).first()
    if user is None or not user.is_active:
        raise credentials_exception
    return user

@router.post("/auth/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
) -> Any:
    """OAuth2 compatible token login, gets an access token for future requests"""
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user account")
        
    access_token_expires  = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_token_expires = timedelta(days=7)

    access_token  = create_access_token(user.email, expires_delta=access_token_expires)
    refresh_token = create_access_token(
        user.email,
        expires_delta=refresh_token_expires,
        extra_claims={"type": "refresh"}
    )

    return {
        "access_token":  access_token,
        "refresh_token": refresh_token,
        "token_type":    "bearer",
        "user": {
            "id":        user.id,
            "email":     user.email,
            "full_name": user.full_name or "",
            "role":      user.role
        }
    }


@router.post("/auth/refresh", response_model=RefreshResponse)
def refresh_access_token(
    refresh_token: str = Body(..., embed=True),
    db: Session = Depends(get_db)
) -> Any:
    """Exchange a valid refresh token for a fresh short-lived access token."""
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "refresh":
            raise credentials_exc
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    user = db.query(User).filter(User.email == email).first()
    if user is None or not user.is_active:
        raise credentials_exc

    new_access = create_access_token(
        user.email,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": new_access, "token_type": "bearer"}

@router.get("/users/me", response_model=UserResponse)
@router.get("/auth/me", response_model=UserResponse)
def read_users_me(current_user: User = Depends(get_current_user)) -> Any:
    """Get current logged in operator profile"""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name or "",
        "role": current_user.role
    }


@router.post("/auth/logout", summary="Revoke current session token")
def logout(
    token: str = Depends(oauth2_scheme),
) -> Any:
    """
    VULN-08 FIX: Invalidate the current access token immediately.
    The JTI is added to the Redis revocation blocklist for its remaining TTL.
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"verify_exp": False}  # Still read expired tokens to extract JTI
        )
        jti = payload.get("jti")
        exp = payload.get("exp")
        if jti:
            import time
            ttl = max(int(exp - time.time()), 60) if exp else 3600
            revoke_token_jti(jti, ttl_seconds=ttl)
    except JWTError:
        pass  # Token already invalid; logout is idempotent
    return {"status": "LOGGED_OUT", "message": "Token has been revoked."}
