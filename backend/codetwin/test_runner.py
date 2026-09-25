"""Run only the tests selected by CodeTwin in a temporary repository snapshot."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

from codetwin.analyzer import InvalidAnalysisRequest, _normalize_path

_OUTPUT_LIMIT = 8000
_TEST_TIMEOUT_SECONDS = 30


def _execution_environment(repository_root: Path) -> dict[str, str]:
    allowed = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP"}
    environment = {key: value for key, value in os.environ.items() if key in allowed}
    environment["PYTHONPATH"] = str(repository_root)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    return environment


def _decode_output(output: str | bytes | None) -> str:
    if output is None:
        return ""
    if isinstance(output, bytes):
        output = output.decode("utf-8", errors="replace")
    return output[-_OUTPUT_LIMIT:]


def run_targeted_tests(files: dict[str, str], test_files: list[str]) -> dict[str, object]:
    """Write a normalized source snapshot to a temp directory and run impacted tests.

    Pytest is preferred when installed. The synthetic demo tests also support unittest,
    which keeps the prototype runnable in minimal Python environments.
    """
    normalized_files: dict[str, str] = {}
    for path, source in files.items():
        normalized = _normalize_path(path)
        if normalized == "." or normalized in normalized_files:
            raise InvalidAnalysisRequest(f"Invalid or duplicate repository file path: {path!r}")
        normalized_files[normalized] = source

    targets = sorted({_normalize_path(path) for path in test_files})
    if not targets:
        return {
            "status": "no_tests",
            "passed": False,
            "targeted_tests": [],
            "results": [],
        }

    missing = [path for path in targets if path not in normalized_files]
    if missing:
        raise InvalidAnalysisRequest(f"Targeted test files are missing: {', '.join(missing)}")

    use_pytest = importlib.util.find_spec("pytest") is not None
    results: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="codetwin-test-run-") as directory:
        repository_root = Path(directory).resolve()
        for path, source in normalized_files.items():
            relative_path = PurePosixPath(path)
            target = repository_root.joinpath(*relative_path.parts).resolve()
            if repository_root not in target.parents:
                raise InvalidAnalysisRequest(f"Repository path escapes the test snapshot: {path!r}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source, encoding="utf-8")

        environment = _execution_environment(repository_root)
        for test_file in targets:
            relative_path = PurePosixPath(test_file)
            if relative_path.suffix != ".py":
                raise InvalidAnalysisRequest(f"Targeted tests must be Python files: {test_file}")
            if use_pytest:
                command = [sys.executable, "-B", "-m", "pytest", "-q", test_file]
                runner = "pytest"
            else:
                test_directory = relative_path.parent.as_posix() if len(relative_path.parts) > 1 else "."
                command = [
                    sys.executable,
                    "-B",
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    test_directory,
                    "-p",
                    relative_path.name,
                    "-v",
                ]
                runner = "unittest"

            try:
                completed = subprocess.run(
                    command,
                    cwd=repository_root,
                    env=environment,
                    capture_output=True,
                    text=True,
                    timeout=_TEST_TIMEOUT_SECONDS,
                    check=False,
                )
                output = _decode_output(completed.stdout + completed.stderr)
                discovered_no_tests = (
                    runner == "unittest" and "Ran 0 tests" in output
                ) or (runner == "pytest" and completed.returncode == 5)
                passed = completed.returncode == 0 and not discovered_no_tests
                result = {
                    "file": test_file,
                    "runner": runner,
                    "status": "passed" if passed else "failed",
                    "exit_code": completed.returncode,
                    "output": output,
                }
                if discovered_no_tests:
                    result["status"] = "error"
                    result["output"] += "\nNo tests were discovered for this targeted file."
            except subprocess.TimeoutExpired as error:
                passed = False
                result = {
                    "file": test_file,
                    "runner": runner,
                    "status": "timeout",
                    "exit_code": None,
                    "output": _decode_output(error.stdout) + _decode_output(error.stderr),
                }
            except OSError as error:
                passed = False
                result = {
                    "file": test_file,
                    "runner": runner,
                    "status": "error",
                    "exit_code": None,
                    "output": str(error),
                }
            results.append(result)

    statuses = {str(result["status"]) for result in results}
    if statuses == {"passed"}:
        overall_status = "passed"
    elif "timeout" in statuses:
        overall_status = "timeout"
    elif "error" in statuses:
        overall_status = "error"
    else:
        overall_status = "failed"
    return {
        "status": overall_status,
        "passed": overall_status == "passed",
        "targeted_tests": targets,
        "results": results,
    }
