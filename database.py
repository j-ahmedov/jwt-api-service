from sqlalchemy import Boolean, Column, Enum, Integer, String, UniqueConstraint, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

import config
from auth.password import hash_password

engine = create_async_engine(config.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class UserORM(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum("admin", "user", name="user_role"), nullable=False, default="user")
    is_active = Column(Boolean, nullable=False, default=True)

    __table_args__ = (UniqueConstraint("username"),)


class ItemORM(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    price = Column(Integer, nullable=False)  # stored as cents to avoid float imprecision
    owner_id = Column(Integer, nullable=False)


class RevokedTokenORM(Base):
    __tablename__ = "revoked_tokens"

    jti = Column(String(36), primary_key=True)


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _seed_admin()


async def _seed_admin() -> None:
    """Create the bootstrap admin from env vars, only if no admin exists yet."""
    if not (config.ADMIN_USERNAME and config.ADMIN_PASSWORD):
        return
    async with AsyncSessionLocal() as session:
        existing_admin = await session.execute(select(UserORM).where(UserORM.role == "admin"))
        if existing_admin.scalar_one_or_none():
            return
        taken = await session.execute(
            select(UserORM).where(UserORM.username == config.ADMIN_USERNAME)
        )
        if taken.scalar_one_or_none():
            return  # username already used by a non-admin; skip rather than clobber
        session.add(
            UserORM(
                username=config.ADMIN_USERNAME,
                email=config.ADMIN_EMAIL,
                hashed_password=hash_password(config.ADMIN_PASSWORD),
                role="admin",
            )
        )
        await session.commit()
