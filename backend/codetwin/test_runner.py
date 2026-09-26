"""Execute only AST-selected tests against an immutable temporary snapshot."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

from codetwin.analyzer import InvalidAnalysisRequest, normalize_path

_OUTPUT_LIMIT = 8000
_TEST_TIMEOUT_SECONDS = 30


def _environment(repository_root: Path) -> dict[str, str]:
    allowed = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP"}
    environment = {key: value for key, value in os.environ.items() if key in allowed}
    environment["PYTHONPATH"] = str(repository_root)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    return environment


def _tail(output: str | bytes | None) -> str:
    if output is None:
        return ""
    if isinstance(output, bytes):
        output = output.decode("utf-8", errors="replace")
    return output[-_OUTPUT_LIMIT:]


def _write_snapshot(files: dict[str, str], root: Path) -> None:
    for path, source in files.items():
        normalized = normalize_path(path)
        relative = PurePosixPath(normalized)
        target = root.joinpath(*relative.parts).resolve()
        if root not in target.parents:
            raise InvalidAnalysisRequest(f"Repository path escapes the test snapshot: {path!r}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")


def run_targeted_tests(files: dict[str, str], test_files: list[str]) -> dict[str, object]:
    normalized_files: dict[str, str] = {}
    for original_path, source in files.items():
        path = normalize_path(original_path)
        if path in normalized_files:
            raise InvalidAnalysisRequest(f"Duplicate normalized repository path: {path}")
        normalized_files[path] = source
    targets = sorted({normalize_path(path) for path in test_files})
    if not targets:
        return {"status": "no_tests", "passed": False, "targeted_tests": [], "results": []}
    missing = [path for path in targets if path not in normalized_files]
    if missing:
        raise InvalidAnalysisRequest(f"Targeted tests are missing from the snapshot: {', '.join(missing)}")
    if any(PurePosixPath(path).suffix != ".py" for path in targets):
        raise InvalidAnalysisRequest("Targeted test files must be Python files")

    use_pytest = importlib.util.find_spec("pytest") is not None
    results: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="codetwin-test-run-") as directory:
        repository_root = Path(directory).resolve()
        _write_snapshot(normalized_files, repository_root)
        environment = _environment(repository_root)
        for test_file in targets:
            if use_pytest:
                command = [sys.executable, "-B", "-m", "pytest", "-q", test_file]
                runner = "pytest"
            else:
                parent = PurePosixPath(test_file).parent.as_posix()
                command = [
                    sys.executable,
                    "-B",
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    parent if parent != "." else ".",
                    "-p",
                    PurePosixPath(test_file).name,
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
                output = _tail(completed.stdout + completed.stderr)
                discovered_none = (
                    runner == "unittest" and "Ran 0 tests" in output
                ) or (runner == "pytest" and completed.returncode == 5)
                passed = completed.returncode == 0 and not discovered_none
                status = "passed" if passed else "failed"
                if discovered_none:
                    status = "error"
                    output += "\nNo tests were discovered for this file."
                results.append({
                    "file": test_file,
                    "runner": runner,
                    "status": status,
                    "exit_code": completed.returncode,
                    "output": output,
                })
            except subprocess.TimeoutExpired as error:
                results.append({
                    "file": test_file,
                    "runner": runner,
                    "status": "timeout",
                    "exit_code": None,
                    "output": _tail(error.stdout) + _tail(error.stderr),
                })
            except OSError as error:
                results.append({
                    "file": test_file,
                    "runner": runner,
                    "status": "error",
                    "exit_code": None,
                    "output": str(error),
                })

    statuses = {str(result["status"]) for result in results}
    if statuses == {"passed"}:
        status = "passed"
    elif "timeout" in statuses:
        status = "timeout"
    elif "error" in statuses:
        status = "error"
    else:
        status = "failed"
    return {
        "status": status,
        "passed": status == "passed",
        "targeted_tests": targets,
        "results": results,
    }
