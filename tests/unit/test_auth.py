"""Unit tests: authentication & authorization."""

from __future__ import annotations

BAD_LOGIN = {"username": "admin", "password": "wrong-password"}
GOOD_LOGIN = {"username": "admin", "password": "Demo@12345"}


def test_login_rejects_bad_credentials(client, auth_headers):
    r = client.post("/auth/login", json=BAD_LOGIN)
    assert r.status_code in (401, 400), r.text
    assert "access_token" not in r.json()


def test_login_returns_bearer_token(client, auth_headers):
    r = client.post("/auth/login", json=GOOD_LOGIN)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["username"] == "admin"


def test_me_requires_token(client):
    assert client.get("/auth/me").status_code == 401


def test_me_with_valid_token(client, auth_headers):
    r = client.get("/auth/me", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["role"] == "admin"


def test_protected_route_requires_auth(client):
    assert client.get("/projects").status_code == 401


def test_rbac_blocks_end_user_from_training(client, auth_headers):
    r = client.post("/auth/login", json={"username": "enduser", "password": "Demo@12345"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.post("/training/start", headers=headers, json={
        "project_id": 1, "base_model": "distilgpt2", "epochs": 1})
    assert resp.status_code == 403