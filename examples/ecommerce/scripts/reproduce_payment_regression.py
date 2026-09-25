"""Apply the proposed payment change to a temporary copy and prove its test fails."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="codetwin-payment-regression-") as temporary_directory:
        demo_copy = Path(temporary_directory) / "ecommerce"
        shutil.copytree(
            PROJECT_ROOT,
            demo_copy,
            ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"),
        )
        patch_path = demo_copy / "scenarios" / "payment_amount_regression.patch"
        patch_lines = patch_path.read_text(encoding="utf-8").splitlines()
        removed_lines = [line[1:] for line in patch_lines if line.startswith("-") and not line.startswith("---")]
        added_lines = [line[1:] for line in patch_lines if line.startswith("+") and not line.startswith("+++")]
        if len(removed_lines) != 1 or len(added_lines) != 1:
            print("The demo patch must contain exactly one changed source line.", file=sys.stderr)
            return 1

        payment_service = demo_copy / "app" / "payments" / "service.py"
        service_text = payment_service.read_text(encoding="utf-8")
        if service_text.count(removed_lines[0]) != 1:
            print("The demo patch no longer matches the payment service.", file=sys.stderr)
            return 1
        payment_service.write_text(
            service_text.replace(removed_lines[0], added_lines[0], 1),
            encoding="utf-8",
        )
        result = subprocess.run(
            [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-p", "test_payment_workflow.py", "-v"],
            cwd=demo_copy,
            capture_output=True,
            text=True,
            check=False,
        )
        print(result.stdout, end="")
        print(result.stderr, end="")
        if result.returncode == 0:
            print("Expected the targeted payment test to fail, but it passed.", file=sys.stderr)
            return 1
        if "amount_cents" not in result.stdout + result.stderr:
            print("The targeted test failed for an unexpected reason.", file=sys.stderr)
            return 1
        print("Payment regression reproduced: the targeted workflow test caught the amount mismatch.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
