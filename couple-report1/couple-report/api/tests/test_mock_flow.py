"""Mock 모드의 서버 기동과 OpenAPI 계약을 확인한다."""

import unittest

from fastapi.testclient import TestClient

from app.main import app


class MockFlowTest(unittest.TestCase):
    def test_health_endpoints(self) -> None:
        with TestClient(app) as client:
            self.assertEqual(client.get("/health/live").json(), {"status": "ok"})
            ready = client.get("/health/ready")
            self.assertEqual(ready.status_code, 200)
            self.assertEqual(ready.json()["watsonx"], "mock")

    def test_api_spec_operations_are_exposed(self) -> None:
        with TestClient(app) as client:
            schema = client.get("/openapi.json").json()
        operations = sum(
            method.lower() in {"get", "post", "put", "patch", "delete"}
            for path_item in schema["paths"].values()
            for method in path_item
        )
        self.assertEqual(operations, 18)


if __name__ == "__main__":
    unittest.main()

