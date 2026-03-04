import os
import hashlib
import base64
import bcrypt as _bcrypt
from datetime import datetime, timedelta
from jose import JWTError, jwt
from fastapi import HTTPException, status

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-please-use-a-long-random-string")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7


def _prep(plain: str) -> bytes:
    """SHA-256 pre-hash → base64 so bcrypt always receives ≤44 bytes."""
    digest = hashlib.sha256(plain.encode("utf-8")).digest()
    return base64.b64encode(digest)


def hash_password(plain: str) -> str:
    return _bcrypt.hashpw(_prep(plain), _bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(_prep(plain), hashed.encode("utf-8"))


def create_access_token(user_id: str, email: str) -> str:
    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "email": email,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
