"""로그인 응답이 DB의 커플 연결 상태를 함께 전달하는지 검증한다."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import auth


class AuthRepository:
    def __init__(self, *, couple_status: str | None) -> None:
        self.user_id = uuid4()
        self.couple_id = uuid4() if couple_status else None
        self.couple_status = couple_status

    async def get_user_by_email(self, email: str):
        return {
            "user_id": self.user_id,
            "email": email,
            "password_hash": "test-hash",
            "display_name": "테스트",
            "couple_id": self.couple_id,
            "couple_status": self.couple_status,
        }


def _client(monkeypatch, *, couple_status: str | None) -> tuple[TestClient, AuthRepository]:
    repository = AuthRepository(couple_status=couple_status)
    app = FastAPI()
    app.include_router(auth.router)
    app.state.container = SimpleNamespace(
        postgres=repository,
        settings=SimpleNamespace(jwt_secret="test-secret", jwt_expire_minutes=5),
    )
    monkeypatch.setattr(auth, "verify_password", lambda password, password_hash: True)
    return TestClient(app), repository


def test_login_returns_active_couple_state(monkeypatch):
    client, repository = _client(monkeypatch, couple_status="active")

    response = client.post(
        "/api/auth/login",
        json={"email": "couple@example.com", "password": "password123"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["user_id"] == str(repository.user_id)
    assert payload["couple_id"] == str(repository.couple_id)
    assert payload["couple_status"] == "active"
    assert payload["token"]


def test_login_returns_null_couple_state_for_unconnected_user(monkeypatch):
    client, repository = _client(monkeypatch, couple_status=None)

    response = client.post(
        "/api/auth/login",
        json={"email": "single@example.com", "password": "password123"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["user_id"] == str(repository.user_id)
    assert payload["couple_id"] is None
    assert payload["couple_status"] is None
