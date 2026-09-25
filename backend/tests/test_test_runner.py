import unittest

from codetwin.test_runner import run_targeted_tests


class TargetedTestRunnerTests(unittest.TestCase):
    def test_runs_a_targeted_unittest_file(self):
        files = {
            "app/__init__.py": "",
            "app/payments.py": "def total_cents(value):\n    return value\n",
            "tests/test_payments.py": (
                "import unittest\n"
                "from app.payments import total_cents\n"
                "class PaymentTests(unittest.TestCase):\n"
                "    def test_amount_is_preserved(self):\n"
                "        self.assertEqual(total_cents(5000), 5000)\n"
            ),
        }

        result = run_targeted_tests(files, ["tests/test_payments.py"])

        self.assertEqual(result["status"], "passed")
        self.assertTrue(result["passed"])
        self.assertEqual(result["targeted_tests"], ["tests/test_payments.py"])

    def test_failing_pytest_style_test_cannot_be_reported_as_passed(self):
        files = {
            "tests/test_payments.py": "def test_payment_amount():\n    assert 50 == 5000\n",
        }

        result = run_targeted_tests(files, ["tests/test_payments.py"])

        self.assertIn(result["status"], {"failed", "error"})
        self.assertFalse(result["passed"])

    def test_empty_test_file_is_an_execution_error(self):
        result = run_targeted_tests({"tests/test_empty.py": "VALUE = 1\n"}, ["tests/test_empty.py"])

        self.assertEqual(result["status"], "error")
        self.assertFalse(result["passed"])
        self.assertIn("No tests were discovered", result["results"][0]["output"])

    def test_rejects_snapshot_paths_that_escape_the_temp_directory(self):
        with self.assertRaises(ValueError):
            run_targeted_tests({"../outside.py": "pass\n"}, ["test_outside.py"])
