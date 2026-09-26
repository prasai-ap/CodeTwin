"""Reproduce the payment regression, then verify its downstream fix in a temp copy."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_COMMAND = [
    sys.executable,
    "-B",
    "-m",
    "unittest",
    "discover",
    "-s",
    "tests",
    "-p",
    "test_payment_workflow.py",
    "-v",
]


def _patch_blocks(patch_path: Path) -> tuple[str, str]:
    removed: list[str] = []
    added: list[str] = []
    for line in patch_path.read_text(encoding="utf-8").splitlines():
        if line.startswith(("---", "+++", "@@")):
            continue
        if line.startswith("-"):
            removed.append(line[1:])
        elif line.startswith("+"):
            added.append(line[1:])
    return "\n".join(removed), "\n".join(added)


def main() -> int:
    source_path = PROJECT_ROOT / "app" / "payments" / "service.py"
    old_block, new_block = _patch_blocks(
        PROJECT_ROOT / "scenarios" / "payment_authorization_regression.patch"
    )
    source = source_path.read_text(encoding="utf-8")
    if source.count(old_block) != 1:
        raise RuntimeError("The payment regression patch no longer matches the checkout service")

    with tempfile.TemporaryDirectory(prefix="codetwin-payment-state-regression-") as directory:
        copy_root = Path(directory) / "ecommerce"
        shutil.copytree(PROJECT_ROOT / "app", copy_root / "app")
        shutil.copytree(PROJECT_ROOT / "tests", copy_root / "tests")
        copied_service = copy_root / "app" / "payments" / "service.py"
        copied_service.write_text(source.replace(old_block, new_block, 1), encoding="utf-8")
        failed_run = subprocess.run(
            TEST_COMMAND,
            cwd=copy_root,
            capture_output=True,
            text=True,
            check=False,
        )

        failure_output = failed_run.stdout + failed_run.stderr
        if failed_run.returncode == 0 or "payment completion notification is missing" not in failure_output:
            sys.stderr.write(failure_output)
            raise RuntimeError("Expected stale notification behavior was not reproduced")

        fix_path = copy_root / "app" / "notifications" / "service.py"
        old_fix, new_fix = _patch_blocks(
            PROJECT_ROOT / "scenarios" / "payment_notification_fix.patch"
        )
        fix_source = fix_path.read_text(encoding="utf-8")
        if fix_source.count(old_fix) != 1:
            raise RuntimeError("The notification fix patch no longer matches the consumer")
        fix_path.write_text(fix_source.replace(old_fix, new_fix, 1), encoding="utf-8")
        fixed_run = subprocess.run(
            TEST_COMMAND,
            cwd=copy_root,
            capture_output=True,
            text=True,
            check=False,
        )
        fixed_output = fixed_run.stdout + fixed_run.stderr
        if fixed_run.returncode != 0:
            sys.stderr.write(fixed_output)
            raise RuntimeError("The notification fix did not pass the targeted workflow test")

    sys.stdout.write(failure_output)
    sys.stdout.write(fixed_output)
    print("Confirmed: the payment regression fails and the downstream notification fix passes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
