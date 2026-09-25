import unittest

from fastapi.testclient import TestClient

from codetwin.api import app


client = TestClient(app)


class ApiTests(unittest.TestCase):
    def test_health_endpoint(self):
        response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_analyze_endpoint_returns_deterministic_impact(self):
        response = client.post(
            "/analyze",
            json={
                "files": {
                    "app/payments.py": "def charge():\n    return True\n",
                    "app/orders.py": "from app.payments import charge\n",
                },
                "changed_files": ["app/payments.py"],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["predicted_impact"]["files"],
            ["app/orders.py", "app/payments.py"],
        )

    def test_analyze_endpoint_rejects_missing_changes(self):
        response = client.post(
            "/analyze",
            json={"files": {"app/main.py": "pass"}, "changed_files": []},
        )

        self.assertEqual(response.status_code, 422)
