from datetime import datetime, timedelta, timezone
import bcrypt
from jose import jwt
from typing import Any


def hash_password(password: str) -> str:
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str, settings: Any) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(seconds=settings.jwt_expiry_seconds)
    claims = {"sub": user_id, "exp": expire, "iat": now}
    return jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

