import uuid
from datetime import datetime, timezone

from jose import JWTError, jwt

import config
from models.token import TokenPayload


def _now() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def create_access_token(user_id: int, role: str) -> str:
    now = _now()
    payload = {
        "sub": str(user_id),  # RFC 7519: sub must be a string
        "role": role,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + int(config.access_token_expires.total_seconds()),
        "type": "access",
    }
    return jwt.encode(payload, config.SECRET_KEY, algorithm=config.ALGORITHM)


def create_refresh_token(user_id: int, role: str) -> str:
    now = _now()
    payload = {
        "sub": str(user_id),  # RFC 7519: sub must be a string
        "role": role,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + int(config.refresh_token_expires.total_seconds()),
        "type": "refresh",
    }
    return jwt.encode(payload, config.SECRET_KEY, algorithm=config.ALGORITHM)


def decode_token(token: str) -> TokenPayload:
    """Raises JWTError on any validation failure (expired, bad sig, etc.)."""
    raw = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
    return TokenPayload(**raw)
