"""Mock API의 업로드→타임라인→리포트→챗봇 축약 흐름."""

import os

import httpx


BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
COUPLE_ID = "00000000-0000-4000-8000-000000000001"


def main() -> None:
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        ready = client.get("/health/ready")
        ready.raise_for_status()
        assert ready.json()["watsonx"] == "mock"

        login = client.post("/api/auth/login", json={"email": "mock@example.com", "password": "mock-password"})
        login.raise_for_status()
        headers = {"Authorization": f"Bearer {login.json()['token']}"}

        upload = client.post(
            f"/api/couples/{COUPLE_ID}/upload",
            headers=headers,
            files={"file": ("mock.txt", "Mock님과 카카오톡 대화", "text/plain")},
            data={"name_map": '{"a":"Mock A","b":"Mock B"}'},
        )
        upload.raise_for_status()

        job = client.get(f"/api/jobs/{upload.json()['job_id']}", headers=headers)
        job.raise_for_status()
        assert job.json()["status"] == "done"

        timeline = client.get(f"/api/couples/{COUPLE_ID}/timeline", headers=headers)
        timeline.raise_for_status()
        week_start = timeline.json()["weeks"][-1]["week_start"]

        report = client.get(f"/api/couples/{COUPLE_ID}/reports/{week_start}", headers=headers)
        report.raise_for_status()
        assert report.json()["status"] == "generated"

        chat = client.post(
            f"/api/couples/{COUPLE_ID}/chat",
            headers=headers,
            json={"message": "우리 언제 제주도 얘기했지?"},
        )
        chat.raise_for_status()
        assert chat.json()["intent"] == "fact_query"

    print("Mock smoke test passed")


if __name__ == "__main__":
    main()

