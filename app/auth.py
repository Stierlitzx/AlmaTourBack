"""
Authentication & Authorization
- JWT access tokens (python-jose)
- bcrypt password hashing (passlib)
- RBAC: require_permission(permission)
- ABAC helper: guide can only touch their own tours
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models import User

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# ── Role → permissions map (mirrors original RBAC) ───────────────────────────
ROLE_PERMISSIONS: dict[str, list[str]] = {
    "tourist": ["read:tours", "create:booking", "read:booking_own", "cancel:booking_own"],
    "guide":   ["read:tours", "create:tour", "update:tour_own", "read:booking_own_tour",
                "read:analytics_own"],
    "admin":   ["read:tours", "create:tour", "update:tour", "delete:tour",
                "create:booking", "read:booking", "cancel:booking",
                "read:analytics", "manage:users", "read:audit_log"],
}


# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    import bcrypt as _bcrypt
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    import hashlib
    import bcrypt as _bcrypt
    # Legacy SHA-256 check
    legacy = hashlib.sha256(plain.encode()).hexdigest()
    if hashed == legacy:
        return True
    # Direct bcrypt check (bypasses passlib)
    try:
        return _bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False

# ── JWT ───────────────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


# ── Current-user dependency ───────────────────────────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> dict:
    payload = decode_token(credentials.credentials)
    user_id: int | None = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return {"user_id": user.id, "role": user.role, "email": user.email, "name": user.name}


# ── RBAC dependency factory ───────────────────────────────────────────────────

def require_permission(permission: str):
    async def checker(user: dict = Depends(get_current_user)) -> dict:
        allowed = ROLE_PERMISSIONS.get(user["role"], [])
        if permission not in allowed:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{user['role']}' lacks permission: {permission}",
            )
        return user
    return checker


# ── ABAC helper ───────────────────────────────────────────────────────────────

async def assert_guide_owns_tour(tour_id: int, user: dict, db: AsyncSession) -> None:
    """Raises 403 if a guide tries to modify a tour they didn't create."""
    if user["role"] == "admin":
        return
    from app.models import Tour
    result = await db.execute(select(Tour.guide_id).where(Tour.id == tour_id))
    guide_id = result.scalar_one_or_none()
    if guide_id != user["user_id"]:
        raise HTTPException(status_code=403, detail="You can only modify your own tours (ABAC)")
