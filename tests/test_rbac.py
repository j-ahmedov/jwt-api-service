"""Objective (c) access control based on token attributes and roles."""
from conftest import USER_CREDS, auth_header, login


async def test_self_registration_cannot_grant_admin(client):
    # Even if the client sends role=admin, it must be ignored.
    payload = {**USER_CREDS, "role": "admin"}
    resp = await client.post("/auth/register", json=payload)
    assert resp.status_code == 201
    assert resp.json()["role"] == "user"


async def test_list_users_admin_only(client, admin_token, user_token):
    assert (await client.get("/users/", headers=auth_header(admin_token))).status_code == 200
    assert (await client.get("/users/", headers=auth_header(user_token))).status_code == 403


async def test_promote_user_requires_admin(client, user_token):
    # a non-admin cannot promote anyone
    resp = await client.patch(
        "/users/1/role", headers=auth_header(user_token), json={"role": "admin"}
    )
    assert resp.status_code == 403


async def test_admin_can_promote_user(client, admin_token):
    # register a fresh user, find their id, promote them
    reg = await client.post("/auth/register", json=USER_CREDS)
    user_id = reg.json()["id"]

    resp = await client.patch(
        f"/users/{user_id}/role", headers=auth_header(admin_token), json={"role": "admin"}
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"

    # the promoted user can now reach an admin-only endpoint
    tokens = await login(client, USER_CREDS["username"], USER_CREDS["password"])
    assert (await client.get("/users/", headers=auth_header(tokens["access_token"]))).status_code == 200


async def test_admin_cannot_change_own_role(client, admin_token):
    me = await client.get("/users/me", headers=auth_header(admin_token))
    admin_id = me.json()["id"]
    resp = await client.patch(
        f"/users/{admin_id}/role", headers=auth_header(admin_token), json={"role": "user"}
    )
    assert resp.status_code == 400


async def test_promote_unknown_user_404(client, admin_token):
    resp = await client.patch(
        "/users/999999/role", headers=auth_header(admin_token), json={"role": "admin"}
    )
    assert resp.status_code == 404


async def test_invalid_role_value_rejected(client, admin_token):
    resp = await client.patch(
        "/users/1/role", headers=auth_header(admin_token), json={"role": "superadmin"}
    )
    assert resp.status_code == 422
