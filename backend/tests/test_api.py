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

    def test_tests_cannot_run_before_bob_review(self):
        created = client.post(
            "/analyses",
            json={"files": {"payments.py": "VALUE = 1\n"}, "changed_files": ["payments.py"]},
        ).json()

        response = client.post(f"/analyses/{created['analysis_id']}/run-tests", json={})

        self.assertEqual(response.status_code, 409)

    def test_demo_payment_regression_can_be_fixed_and_revalidated(self):
        created = client.post("/demo/payment-regression")

        self.assertEqual(created.status_code, 200)
        report = created.json()
        analysis_id = report["analysis_id"]
        self.assertEqual(report["demo_scenario"], "payment_amount_regression")
        self.assertIn("app/routes/orders.py", report["predicted_impact"]["api_files"])
        self.assertIn("tests/test_payment_workflow.py", report["predicted_impact"]["tests"])

        context = client.get(f"/analyses/{analysis_id}/context").json()
        self.assertIn("amount_cents=amount_cents // 100", context["review_snapshot"]["app/payments/service.py"])

        reviewed = client.post(
            f"/analyses/{analysis_id}/bob-review",
            json={
                "confirmed_files": report["predicted_impact"]["files"],
                "possible_files": [],
                "not_affected_files": report["not_affected"],
                "rationale": "The cents conversion changes checkout charges; the remaining files are unrelated.",
            },
        )
        self.assertEqual(reviewed.status_code, 200)
        tested = client.post(f"/analyses/{analysis_id}/run-tests", json={})

        self.assertEqual(tested.json()["status"], "regression_detected")
        self.assertFalse(tested.json()["safe_to_merge"])

        fixed_response = client.post(f"/analyses/{analysis_id}/demo-fix")
        self.assertEqual(fixed_response.status_code, 200)
        fixed = fixed_response.json()
        self.assertEqual(fixed["status"], "awaiting_bob_review")
        self.assertEqual(fixed["demo_scenario"], "payment_amount_regression_fixed")
        self.assertEqual(fixed["parent_analysis_id"], analysis_id)
        fixed_context = client.get(f"/analyses/{fixed['analysis_id']}/context").json()
        self.assertIn("amount_cents=amount_cents", fixed_context["review_snapshot"]["app/payments/service.py"])
        self.assertNotIn("amount_cents=amount_cents // 100", fixed_context["review_snapshot"]["app/payments/service.py"])

        reviewed_fix = client.post(
            f"/analyses/{fixed['analysis_id']}/bob-review",
            json={
                "confirmed_files": fixed["predicted_impact"]["files"],
                "possible_files": [],
                "not_affected_files": fixed["not_affected"],
                "rationale": "The corrected payment service preserves cents through checkout.",
            },
        )
        self.assertEqual(reviewed_fix.status_code, 200)
        safe = client.post(f"/analyses/{fixed['analysis_id']}/run-tests", json={}).json()
        self.assertEqual(safe["status"], "safe_to_merge")
        self.assertTrue(safe["safe_to_merge"])

        original_after_fix = client.get(f"/analyses/{analysis_id}/context").json()
        self.assertEqual(original_after_fix["status"], "regression_detected")
        self.assertIn(
            "amount_cents=amount_cents // 100",
            original_after_fix["review_snapshot"]["app/payments/service.py"],
        )

    def test_frontend_development_origin_is_allowed(self):
        response = client.options(
            "/analyses",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], "http://localhost:5173")

    def test_passing_tests_do_not_clear_unresolved_possible_impact(self):
        files = {
            "payments.py": "def total_cents(value):\n    return value\n",
            "tests/test_payments.py": (
                "import unittest\n"
                "from payments import total_cents\n"
                "class PaymentTests(unittest.TestCase):\n"
                "    def test_amount_is_preserved(self):\n"
                "        self.assertEqual(total_cents(5000), 5000)\n"
            ),
        }
        created = client.post(
            "/analyses",
            json={"files": files, "changed_files": ["payments.py"]},
        ).json()
        reviewed = client.post(
            f"/analyses/{created['analysis_id']}/bob-review",
            json={
                "confirmed_files": ["payments.py"],
                "possible_files": ["tests/test_payments.py"],
                "not_affected_files": [],
                "rationale": "The unit test passes, but its broader caller context remains uncertain.",
            },
        )
        self.assertEqual(reviewed.status_code, 200)

        tested = client.post(f"/analyses/{created['analysis_id']}/run-tests", json={})

        self.assertTrue(tested.json()["test_results"]["passed"])
        self.assertEqual(tested.json()["status"], "possible_impact_unresolved")
        self.assertFalse(tested.json()["safe_to_merge"])

    def test_only_passing_targeted_tests_can_produce_safe_to_merge(self):
        ecommerce_root = Path(__file__).resolve().parents[2] / "examples" / "ecommerce"
        files = {
            path.relative_to(ecommerce_root).as_posix(): path.read_text(encoding="utf-8")
            for path in ecommerce_root.rglob("*.py")
        }

        baseline = self._create_reviewed_analysis(files)
        safe = client.post(f"/analyses/{baseline['analysis_id']}/run-tests", json={})

        self.assertEqual(safe.status_code, 200)
        self.assertTrue(safe.json()["test_results"]["passed"])
        self.assertIn("tests/test_payment_workflow.py", safe.json()["test_results"]["targeted_tests"])
        self.assertTrue(safe.json()["safe_to_merge"])
        self.assertEqual(safe.json()["status"], "safe_to_merge")

        regression_files = dict(files)
        patch_lines = (ecommerce_root / "scenarios" / "payment_amount_regression.patch").read_text(
            encoding="utf-8"
        ).splitlines()
        old_line = next(line[1:] for line in patch_lines if line.startswith("-") and not line.startswith("---"))
        new_line = next(line[1:] for line in patch_lines if line.startswith("+") and not line.startswith("+++"))
        regression_files["app/payments/service.py"] = regression_files["app/payments/service.py"].replace(
            old_line,
            new_line,
            1,
        )
        regression = self._create_reviewed_analysis(regression_files)
        failed = client.post(f"/analyses/{regression['analysis_id']}/run-tests", json={})

        self.assertEqual(failed.status_code, 200)
        self.assertFalse(failed.json()["test_results"]["passed"])
        self.assertEqual(failed.json()["status"], "regression_detected")
        self.assertFalse(failed.json()["safe_to_merge"])
        self.assertTrue(
            any(
                result["file"] == "tests/test_payment_workflow.py" and result["status"] == "failed"
                for result in failed.json()["test_results"]["results"]
            )
        )

    def _create_reviewed_analysis(self, files):
        created_response = client.post(
            "/analyses",
            json={"files": files, "changed_files": ["app/payments/service.py"]},
        )
        self.assertEqual(created_response.status_code, 200)
        created = created_response.json()
        prediction = created["predicted_impact"]["files"]
        reviewed = client.post(
            f"/analyses/{created['analysis_id']}/bob-review",
            json={
                "confirmed_files": prediction,
                "possible_files": [],
                "not_affected_files": created["not_affected"],
                "rationale": "The payment service is semantically related to checkout; remaining files are outside this flow.",
            },
        )
        self.assertEqual(reviewed.status_code, 200)
        return created


class BobConfigurationTests(unittest.TestCase):
    def test_project_mcp_manifest_registers_codetwin_server(self):
        import json

        manifest = Path(__file__).resolve().parents[2] / ".bob" / "mcp.json"
        config = json.loads(manifest.read_text(encoding="utf-8"))

        server = config["mcpServers"]["codetwin"]
        self.assertEqual(server["command"], "python")
        self.assertEqual(server["args"], ["-m", "codetwin.bob_mcp"])
        bob_server = Path(__file__).resolve().parents[1] / "codetwin" / "bob_mcp.py"
        compile(bob_server.read_text(encoding="utf-8"), str(bob_server), "exec")
