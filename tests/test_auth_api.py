"""Login, first-password change, and administrator user flow tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from laoliuliu.db import SessionLocal
from laoliuliu.main import app
from laoliuliu.models import User
from laoliuliu.security import hash_password


def create_admin(*, must_change_password: bool) -> None:
    with SessionLocal() as db:
        db.add(
            User(
                username="admin",
                password_hash=hash_password("Initial-admin-12345"),
                role="admin",
                status="active",
                must_change_password=must_change_password,
            )
        )
        db.commit()


def login(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "Initial-admin-12345"},
    )
    assert response.status_code == 200
    return response.json()["data"]


def test_first_login_requires_password_change() -> None:
    create_admin(must_change_password=True)
    with TestClient(app) as client:
        data = login(client)
        blocked = client.get("/api/v1/admin/users")
        assert blocked.status_code == 403
        changed = client.post(
            "/api/v1/auth/change-password",
            headers={"X-CSRF-Token": data["csrf_token"]},
            json={
                "current_password": "Initial-admin-12345",
                "new_password": "Changed-admin-67890",
            },
        )
        assert changed.status_code == 200
        listed = client.get("/api/v1/admin/users")
        assert listed.status_code == 200


def test_admin_creates_and_disables_child_user() -> None:
    create_admin(must_change_password=False)
    with TestClient(app) as client:
        data = login(client)
        csrf = str(data["csrf_token"])
        created = client.post(
            "/api/v1/admin/users",
            headers={"X-CSRF-Token": csrf},
            json={"username": "child_01"},
        )
        assert created.status_code == 201
        body = created.json()["data"]
        assert body["user"]["role"] == "user"
        assert body["temporary_password"]
        user_id = body["user"]["id"]
        disabled = client.patch(
            f"/api/v1/admin/users/{user_id}/status",
            headers={"X-CSRF-Token": csrf},
            json={"status": "disabled"},
        )
        assert disabled.status_code == 200
        assert disabled.json()["data"]["user"]["status"] == "disabled"


def test_state_change_requires_csrf() -> None:
    create_admin(must_change_password=False)
    with TestClient(app) as client:
        login(client)
        response = client.post("/api/v1/admin/users", json={"username": "child_02"})
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "CSRF_INVALID"
