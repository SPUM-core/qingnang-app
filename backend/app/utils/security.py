"""JWT / 密码哈希 - 直接用 bcrypt + pyjose"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt, JWTError
import bcrypt
from ..config import settings


def hash_pwd(password: str) -> str:
    """bcrypt 哈希"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=10)).decode("utf-8")


def verify_pwd(plain: str, hashed: str) -> bool:
    """验证密码"""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(sub: str, expires_hours: Optional[int] = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        hours=expires_hours or settings.ACCESS_TOKEN_EXPIRE_HOURS
    )
    to_encode = {"sub": sub, "exp": expire}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")


def decode_access_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload.get("sub")
    except JWTError:
        return None
