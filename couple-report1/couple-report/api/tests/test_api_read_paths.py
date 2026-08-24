"""읽기 응답이 Mock 계약의 기본 키를 유지하는지 확인한다."""

import unittest

from fastapi.testclient import TestClient

from app.main import app


class ReadPathTest(unittest.TestCase):
    def test_timeline_report_review(self) -> None:
        headers = {"Authorization": "Bearer mock-token"}
        with TestClient(app) as client:
            timeline = client.get("/api/couples/mock/timeline", headers=headers)
            report = client.get("/api/couples/mock/reports/2026-08-17", headers=headers)
            review = client.get(
                "/api/couples/mock/review",
                params={"start": "2026-08-17T00:00:00+09:00", "end": "2026-08-18T00:00:00+09:00"},
                headers=headers,
            )
        self.assertEqual(timeline.status_code, 200)
        self.assertEqual(report.status_code, 200)
        self.assertEqual(review.status_code, 200)
        self.assertIn("couple", timeline.json()["weeks"][0]["summary"]["question_rate"])
        self.assertNotIn("a", report.json()["metrics"]["question_rate"])


if __name__ == "__main__":
    unittest.main()

