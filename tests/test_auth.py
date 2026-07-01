"""Objective (a) generate/validate tokens and (b) secure authentication."""
from conftest import USER_CREDS, auth_header, login


async def test_register_returns_user_without_password(client):
    resp = await client.post("/auth/register", json=USER_CREDS)
    assert resp.status_code == 201
    body = resp.json()
    assert body["username"] == "demo"
    assert body["role"] == "user"
    assert "hashed_password" not in body and "password" not in body


async def test_register_duplicate_username_rejected(client):
    await client.post("/auth/register", json=USER_CREDS)
    resp = await client.post("/auth/register", json=USER_CREDS)
    assert resp.status_code == 400


async def test_register_validation(client):
    short_pw = {**USER_CREDS, "password": "short"}
    assert (await client.post("/auth/register", json=short_pw)).status_code == 422
    bad_name = {**USER_CREDS, "username": "a b!"}
    assert (await client.post("/auth/register", json=bad_name)).status_code == 422


async def test_login_success_returns_token_pair(client):
    await client.post("/auth/register", json=USER_CREDS)
    tokens = await login(client, USER_CREDS["username"], USER_CREDS["password"])
    assert tokens["token_type"] == "bearer"
    assert tokens["access_token"] and tokens["refresh_token"]


async def test_login_wrong_password_401(client):
    await client.post("/auth/register", json=USER_CREDS)
    resp = await client.post(
        "/auth/login", json={"username": "demo", "password": "WrongPass1"}
    )
    assert resp.status_code == 401


async def test_protected_endpoint_requires_token(client):
    assert (await client.get("/users/me")).status_code in (401, 403)


async def test_protected_endpoint_rejects_garbage_token(client):
    resp = await client.get("/users/me", headers=auth_header("not.a.jwt"))
    assert resp.status_code == 401


async def test_access_token_works_on_protected_endpoint(client, user_token):
    resp = await client.get("/users/me", headers=auth_header(user_token))
    assert resp.status_code == 200
    assert resp.json()["username"] == "demo"


async def test_refresh_rotates_and_revokes_old(client):
    await client.post("/auth/register", json=USER_CREDS)
    tokens = await login(client, USER_CREDS["username"], USER_CREDS["password"])
    refresh = tokens["refresh_token"]

    first = await client.post("/auth/refresh", headers=auth_header(refresh))
    assert first.status_code == 200
    assert first.json()["access_token"] != tokens["access_token"]

    # Re-using the now-rotated refresh token must fail.
    second = await client.post("/auth/refresh", headers=auth_header(refresh))
    assert second.status_code == 401


async def test_access_token_cannot_be_used_to_refresh(client, user_token):
    resp = await client.post("/auth/refresh", headers=auth_header(user_token))
    assert resp.status_code == 401


async def test_refresh_token_cannot_access_protected_endpoint(client):
    await client.post("/auth/register", json=USER_CREDS)
    tokens = await login(client, USER_CREDS["username"], USER_CREDS["password"])
    resp = await client.get("/users/me", headers=auth_header(tokens["refresh_token"]))
    assert resp.status_code == 401


async def test_logout_revokes_access_token(client):
    await client.post("/auth/register", json=USER_CREDS)
    tokens = await login(client, USER_CREDS["username"], USER_CREDS["password"])
    access, refresh = tokens["access_token"], tokens["refresh_token"]

    # token works before logout
    assert (await client.get("/users/me", headers=auth_header(access))).status_code == 200

    logout = await client.post(
        "/auth/logout", headers=auth_header(access), json={"refresh_token": refresh}
    )
    assert logout.status_code == 204

    # token rejected after logout
    assert (await client.get("/users/me", headers=auth_header(access))).status_code == 401
    # revoked refresh token can no longer mint new tokens
    assert (await client.post("/auth/refresh", headers=auth_header(refresh))).status_code == 401
