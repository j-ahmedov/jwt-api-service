"""Objective (d) JWT integrated into the RESTful item service."""
from conftest import auth_header


async def test_items_require_authentication(client):
    assert (await client.get("/items/")).status_code in (401, 403)
    assert (await client.post("/items/", json={"name": "x", "price": 1.0})).status_code in (401, 403)


async def test_create_and_get_item_price_is_float(client, user_token):
    resp = await client.post(
        "/items/", headers=auth_header(user_token), json={"name": "Widget", "price": 19.99}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["price"] == 19.99
    assert isinstance(body["price"], float)

    got = await client.get(f"/items/{body['id']}", headers=auth_header(user_token))
    assert got.status_code == 200
    assert got.json()["price"] == 19.99


async def test_whole_dollar_price_returns_float(client, user_token):
    resp = await client.post(
        "/items/", headers=auth_header(user_token), json={"name": "Round", "price": 20}
    )
    assert resp.json()["price"] == 20.0


async def test_create_sets_owner_to_caller(client, user_token):
    me = await client.get("/users/me", headers=auth_header(user_token))
    resp = await client.post(
        "/items/", headers=auth_header(user_token), json={"name": "Mine", "price": 5.5}
    )
    assert resp.json()["owner_id"] == me.json()["id"]


async def test_list_items(client, user_token):
    await client.post("/items/", headers=auth_header(user_token), json={"name": "A", "price": 1.0})
    await client.post("/items/", headers=auth_header(user_token), json={"name": "B", "price": 2.0})
    resp = await client.get("/items/", headers=auth_header(user_token))
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_delete_item_admin_only(client, admin_token, user_token):
    created = await client.post(
        "/items/", headers=auth_header(user_token), json={"name": "Temp", "price": 1.0}
    )
    item_id = created.json()["id"]

    # regular user forbidden
    assert (await client.delete(f"/items/{item_id}", headers=auth_header(user_token))).status_code == 403

    # admin succeeds, gets 200 + message
    ok = await client.delete(f"/items/{item_id}", headers=auth_header(admin_token))
    assert ok.status_code == 200
    assert ok.json()["detail"] == f"Item {item_id} deleted"

    # gone now
    assert (await client.get(f"/items/{item_id}", headers=auth_header(user_token))).status_code == 404


async def test_delete_missing_item_404(client, admin_token):
    resp = await client.delete("/items/999999", headers=auth_header(admin_token))
    assert resp.status_code == 404
