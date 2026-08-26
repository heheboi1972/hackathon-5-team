from copy import deepcopy
from datetime import date
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.deps import AuthenticatedUser, current_user
from app.routers import couples


COUPLE_ID = UUID("11111111-1111-1111-1111-111111111111")
USER_ID = UUID("22222222-2222-2222-2222-222222222222")


def _couple_row(first_met_at: date | None = None) -> dict:
    return {
        "couple_id": COUPLE_ID,
        "status": "active",
        "user_a": USER_ID,
        "user_b": uuid4(),
        "display_name_a": "A",
        "display_name_b": "B",
        "kakao_name_a": None,
        "kakao_name_b": None,
        "started_at": date(2026, 3, 1),
        "first_met_at": first_met_at,
        "me": "a",
        "first_week": None,
        "last_week": None,
        "weeks_available": 0,
        "message_count": 0,
        "active_job_id": None,
        "active_job_kind": None,
        "active_job_done": None,
        "active_job_total": None,
    }


class CoupleSettingsRepository:
    def __init__(self) -> None:
        self.row = _couple_row()

    async def update_couple_first_met_at(
        self, couple_id, user_id, first_met_at
    ) -> bool:
        if couple_id != COUPLE_ID or user_id != USER_ID:
            return False
        self.row["first_met_at"] = first_met_at
        return True

    async def get_couple_me(self, user_id):
        if user_id != USER_ID:
            return None
        return deepcopy(self.row)


def _app(repository: CoupleSettingsRepository | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(couples.router)
    app.state.container = SimpleNamespace(
        postgres=repository or CoupleSettingsRepository()
    )
    if repository is not None:
        app.dependency_overrides[current_user] = lambda: AuthenticatedUser(
            user_id=USER_ID,
            email="a@example.com",
            display_name="A",
            couple_id=COUPLE_ID,
            member="a",
            couple_status="active",
        )
    return app


def test_authenticated_member_can_update_and_clear_first_met_at():
    repository = CoupleSettingsRepository()
    client = TestClient(_app(repository))

    updated = client.patch(
        "/api/couples/me", json={"first_met_at": "2024-01-17"}
    )

    assert updated.status_code == 200, updated.text
    assert updated.json()["first_met_at"] == "2024-01-17"
    assert repository.row["first_met_at"] == date(2024, 1, 17)

    fetched = client.get("/api/couples/me")
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["first_met_at"] == "2024-01-17"

    cleared = client.patch("/api/couples/me", json={"first_met_at": None})
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["first_met_at"] is None
    assert repository.row["first_met_at"] is None


def test_unauthenticated_first_met_at_update_is_rejected():
    app = _app()
    client = TestClient(app)

    response = client.patch(
        "/api/couples/me", json={"first_met_at": "2024-01-17"}
    )

    assert response.status_code == 401
