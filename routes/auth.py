from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.jwt_handler import create_access_token, create_refresh_token, decode_token
from auth.password import hash_password, verify_password
from database import RevokedTokenORM, UserORM, get_session
from models.token import Token
from models.user import Role, UserCreate, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])
_bearer = HTTPBearer()


class LoginRequest(BaseModel):
    username: str = Field(examples=["demo"])
    password: str = Field(examples=["demo1234"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(body: UserCreate, session: AsyncSession = Depends(get_session)):
    existing = await session.execute(select(UserORM).where(UserORM.username == body.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already taken")
    user = UserORM(
        username=body.username,
        email=body.email,
        hashed_password=hash_password(body.password),
        role=Role.user,  # public registration can never self-assign admin
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@router.post("/login", response_model=Token)
async def login(body: LoginRequest, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(UserORM).where(UserORM.username == body.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Account is disabled")
    return Token(
        access_token=create_access_token(user.id, user.role),
        refresh_token=create_refresh_token(user.id, user.role),
    )


@router.post("/refresh", response_model=Token)
async def refresh(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
):
    exc = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")
    try:
        payload = decode_token(credentials.credentials)
    except JWTError:
        raise exc

    if payload.type != "refresh":
        raise exc

    revoked = await session.get(RevokedTokenORM, payload.jti)
    if revoked:
        raise exc

    result = await session.execute(select(UserORM).where(UserORM.id == int(payload.sub)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise exc

    # Rotate: revoke used refresh token
    session.add(RevokedTokenORM(jti=payload.jti))
    await session.commit()

    return Token(
        access_token=create_access_token(user.id, user.role),
        refresh_token=create_refresh_token(user.id, user.role),
    )


class LogoutRequest(BaseModel):
    refresh_token: str


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: LogoutRequest,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
):
    for token in (credentials.credentials, body.refresh_token):
        try:
            payload = decode_token(token)
            if not await session.get(RevokedTokenORM, payload.jti):
                session.add(RevokedTokenORM(jti=payload.jti))
        except JWTError:
            pass
    await session.commit()
