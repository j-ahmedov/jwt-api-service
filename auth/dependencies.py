from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.jwt_handler import decode_token
from database import RevokedTokenORM, UserORM, get_session
from models.user import Role

_bearer = HTTPBearer()


async def _get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> UserORM:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(credentials.credentials)
    except JWTError:
        raise credentials_exception

    if payload.type != "access":
        raise credentials_exception

    revoked = await session.get(RevokedTokenORM, payload.jti)
    if revoked:
        raise credentials_exception

    result = await session.execute(select(UserORM).where(UserORM.id == int(payload.sub)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise credentials_exception

    return user


async def get_current_user(user: UserORM = Depends(_get_current_user)) -> UserORM:
    return user


async def require_admin(user: UserORM = Depends(_get_current_user)) -> UserORM:
    if user.role != Role.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return user
