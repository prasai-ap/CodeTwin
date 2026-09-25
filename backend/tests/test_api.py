import unittest
from pathlib import Path

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

    def test_analysis_session_keeps_bob_review_separate_from_prediction(self):
        snapshot = {
            "app/payments.py": "def capture():\n    return True\n",
            "app/orders.py": "from app.payments import capture\n",
            "app/routes/orders.py": "from app.orders import checkout\n@router.post('/orders')\ndef create():\n    pass\n",
            "tests/test_orders.py": "from app.orders import checkout\n",
            "app/catalog.py": "def list_products():\n    return []\n",
        }
        created = client.post(
            "/analyses",
            json={"files": snapshot, "changed_files": ["app/payments.py"]},
        )

        self.assertEqual(created.status_code, 200)
        report = created.json()
        self.assertEqual(report["status"], "awaiting_bob_review")
        self.assertFalse(report["safe_to_merge"])
        self.assertIn("app/routes/orders.py", report["predicted_impact"]["api_files"])

        reviewed = client.post(
            f"/analyses/{report['analysis_id']}/bob-review",
            json={
                "confirmed_files": ["app/payments.py", "app/orders.py"],
                "possible_files": ["app/routes/orders.py", "tests/test_orders.py"],
                "not_affected_files": ["app/catalog.py"],
                "rationale": "Checkout passes the payment amount to the order total; the catalog path is separate.",
            },
        )

        self.assertEqual(reviewed.status_code, 200)
        final_report = reviewed.json()
        self.assertEqual(final_report["status"], "awaiting_tests")
        self.assertFalse(final_report["safe_to_merge"])
        self.assertEqual(
            final_report["bob_review"]["file_assessments"]["app/orders.py"],
            {"prediction": "predicted_impact", "bob_assessment": "bob_confirmed_impact"},
        )
        self.assertEqual(
            final_report["bob_review"]["file_assessments"]["app/catalog.py"],
            {"prediction": "not_predicted", "bob_assessment": "not_affected"},
        )
        stored = client.get(f"/analyses/{report['analysis_id']}")
        self.assertEqual(stored.status_code, 200)
        self.assertEqual(stored.json()["bob_review"], final_report["bob_review"])

    def test_bob_review_requires_a_complete_non_overlapping_classification(self):
        created = client.post(
            "/analyses",
            json={"files": {"payments.py": "VALUE = 1\n", "catalog.py": "VALUE = 2\n"}, "changed_files": ["payments.py"]},
        ).json()

        incomplete = client.post(
            f"/analyses/{created['analysis_id']}/bob-review",
            json={
                "confirmed_files": ["payments.py"],
                "possible_files": [],
                "not_affected_files": [],
                "rationale": "The changed file is directly involved.",
            },
        )
        overlapping = client.post(
            f"/analyses/{created['analysis_id']}/bob-review",
            json={
                "confirmed_files": ["payments.py"],
                "possible_files": ["payments.py"],
                "not_affected_files": ["catalog.py"],
                "rationale": "Conflicting classifications.",
            },
        )

        self.assertEqual(incomplete.status_code, 422)
        self.assertEqual(overlapping.status_code, 422)


class BobConfigurationTests(unittest.TestCase):
    def test_project_mcp_manifest_registers_codetwin_server(self):
        import json

        manifest = Path(__file__).resolve().parents[2] / ".bob" / "mcp.json"
        config = json.loads(manifest.read_text(encoding="utf-8"))

        server = config["mcpServers"]["codetwin"]
        self.assertEqual(server["command"], "python")
        self.assertEqual(server["args"], ["-m", "codetwin.bob_mcp"])
