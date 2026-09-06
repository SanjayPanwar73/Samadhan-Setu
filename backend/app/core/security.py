from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

# Using the `bcrypt` library directly instead of passlib's CryptContext:
# passlib's bcrypt backend has a known incompatibility with bcrypt>=4.1
# (it probes a version attribute that no longer exists), so direct use is
# more reliable here.
_BCRYPT_MAX_BYTES = 72  # bcrypt silently ignores anything past 72 bytes


def _password_bytes(password: str) -> bytes:
    encoded = password.encode("utf-8")
    if len(encoded) > _BCRYPT_MAX_BYTES:
        raise ValueError("Password exceeds bcrypt's 72-byte limit")
    return encoded


def hash_password(password: str) -> str:
    password_bytes = _password_bytes(password)
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        password_bytes = _password_bytes(plain_password)
        return bcrypt.checkpw(password_bytes, hashed_password.encode("utf-8"))
    except (TypeError, ValueError):
        # A corrupted legacy hash must behave like an invalid password, not
        # become an unhandled 500 from the login endpoint.
        return False


def create_access_token(data: dict, expires_minutes: int | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None
