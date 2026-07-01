"""Shared pytest fixtures.

Env vars are set BEFORE importing the app so config.py picks up the test
database and a deterministic secret/admin. The schema is dropped and recreated
(plus the bootstrap admin re-seeded) before every test for full isolation.
"""
import os

os.environ["DATABASE_URL"] = "postgresql+asyncpg://capitano@localhost:5432/jwt_api_test"
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
os.environ["REFRESH_TOKEN_EXPIRE_DAYS"] = "7"
# NOTE: test-only throwaway credentials. The suite seeds its own admin from
# these env vars and logs in with the same values, so they are self-contained
# and intentionally unrelated to the real bootstrap admin in .env.
os.environ["ADMIN_USERNAME"] = "testadmin"
os.environ["ADMIN_PASSWORD"] = "testadmin-pw"
os.environ["ADMIN_EMAIL"] = "testadmin@example.test"

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from database import Base, engine, init_db
from main import app

ADMIN_CREDS = {"username": os.environ["ADMIN_USERNAME"], "password": os.environ["ADMIN_PASSWORD"]}
USER_CREDS = {"username": "demo", "email": "demo@example.test", "password": "testuser-pw"}


@pytest_asyncio.fixture(autouse=True)
async def reset_db():
    """Fresh schema + seeded admin before each test.

    Each test runs in its own event loop, so we dispose the engine's
    connection pool on teardown — otherwise the next test would inherit a
    connection bound to the previous (now-closed) loop.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await init_db()  # create_all + seed bootstrap admin
    yield
    await engine.dispose()


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# --- helpers -----------------------------------------------------------------

async def login(client: AsyncClient, username: str, password: str) -> dict:
    resp = await client.post("/auth/login", json={"username": username, "password": password})
    return resp.json()


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def admin_token(client) -> str:
    tokens = await login(client, **ADMIN_CREDS)
    return tokens["access_token"]


@pytest_asyncio.fixture
async def user_token(client) -> str:
    """Register a regular 'demo' user and return its access token."""
    await client.post("/auth/register", json=USER_CREDS)
    tokens = await login(client, USER_CREDS["username"], USER_CREDS["password"])
    return tokens["access_token"]
