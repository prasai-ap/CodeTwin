import unittest
from pathlib import Path

from codetwin.analyzer import InvalidAnalysisRequest, analyze_repository


class AnalyzerTests(unittest.TestCase):
    def test_finds_transitive_dependents_tests_and_api_files(self):
        files = {
            "app/payments.py": "def charge():\n    return True\n",
            "app/orders.py": "from app.payments import charge\n\ndef checkout():\n    return charge()\n",
            "app/routes/orders.py": (
                "from app.orders import checkout\n"
                "@router.post('/orders')\n"
                "def create_order():\n    return checkout()\n"
            ),
            "tests/test_orders.py": "from app.orders import checkout\n",
            "app/catalog.py": "def list_products():\n    return []\n",
            "README.md": "Demo repository",
        }

        result = analyze_repository(files, ["app\\payments.py"])

        self.assertEqual(result["changed_files"], ["app/payments.py"])
        self.assertEqual(
            result["predicted_impact"],
            {
                "files": [
                    "app/orders.py",
                    "app/payments.py",
                    "app/routes/orders.py",
                    "tests/test_orders.py",
                ],
                "tests": ["tests/test_orders.py"],
                "api_files": ["app/routes/orders.py"],
                "components": ["orders", "payments", "routes", "tests"],
            },
        )
        self.assertEqual(result["not_affected"], ["app/catalog.py"])
        self.assertEqual(result["parse_errors"], [])

    def test_reports_syntax_errors_and_keeps_analysis_deterministic(self):
        files = {
            "service.py": "def run(:\n    pass\n",
            "unrelated.py": "VALUE = 1\n",
        }

        result = analyze_repository(files, ["service.py"])

        self.assertEqual(result["predicted_impact"]["files"], ["service.py"])
        self.assertEqual(
            result["parse_errors"],
            [{"file": "service.py", "message": "line 1: invalid syntax"}],
        )
        self.assertEqual(result["not_affected"], ["unrelated.py"])

    def test_rejects_invalid_change_requests(self):
        cases = [
            ({"service.py": "pass"}, []),
            ({"service.py": "pass"}, ["../service.py"]),
            ({"service.py": "pass"}, ["missing.py"]),
            ({"service.py": "pass"}, ["README.md"]),
        ]
        for files, changed_files in cases:
            with self.subTest(changed_files=changed_files):
                with self.assertRaises(InvalidAnalysisRequest):
                    analyze_repository(files, changed_files)


class EcommerceFixtureTests(unittest.TestCase):
    def test_payment_change_reaches_order_api_and_targeted_tests(self):
        project_root = Path(__file__).resolve().parents[2] / "examples" / "ecommerce"
        files = {
            path.relative_to(project_root).as_posix(): path.read_text(encoding="utf-8")
            for path in project_root.rglob("*.py")
        }

        result = analyze_repository(files, ["app/payments/service.py"])
        impact = result["predicted_impact"]

        self.assertIn("app/orders/service.py", impact["files"])
        self.assertIn("app/routes/orders.py", impact["api_files"])
        self.assertIn("tests/test_payment_workflow.py", impact["tests"])
        self.assertIn("app/routes/products.py", result["not_affected"])
