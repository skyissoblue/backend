"""JWT issue and verification."""
from datetime import datetime, timedelta, timezone
import jwt
from ..config import JWT_ALGORITHM, JWT_EXPIRE_DAYS, JWT_SECRET


def create_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(user_id), "iat": now, "exp": now + timedelta(days=JWT_EXPIRE_DAYS)}, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> int:
    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    return int(payload["sub"])
