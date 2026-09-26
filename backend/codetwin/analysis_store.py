"""In-memory CodeTwin analysis sessions and evidence-based merge-gate state."""

from __future__ import annotations

from threading import RLock
from uuid import uuid4

from codetwin.analyzer import InvalidAnalysisRequest, analyze_repository, normalize_path
from codetwin.test_runner import run_targeted_tests

_sessions: dict[str, dict[str, object]] = {}
_snapshots: dict[str, dict[str, str]] = {}
_lock = RLock()


def create_analysis(files: dict[str, str], changed_files: list[str]) -> dict[str, object]:
    normalized_files: dict[str, str] = {}
    for original_path, source in files.items():
        path = normalize_path(original_path)
        if path in normalized_files:
            raise InvalidAnalysisRequest(f"Duplicate normalized repository path: {path}")
        normalized_files[path] = source
    report = analyze_repository(normalized_files, changed_files)
    analysis_id = uuid4().hex
    analysis: dict[str, object] = {
        "analysis_id": analysis_id,
        "status": "awaiting_bob_review",
        **report,
        "bob_review": None,
        "test_results": {"status": "not_run", "passed": False},
        "safe_to_merge": False,
    }
    with _lock:
        _sessions[analysis_id] = analysis
        _snapshots[analysis_id] = normalized_files
    return analysis


def get_analysis(analysis_id: str) -> dict[str, object] | None:
    with _lock:
        return _sessions.get(analysis_id)


def list_analyses() -> list[dict[str, object]]:
    with _lock:
        return [
            {
                "analysis_id": str(analysis["analysis_id"]),
                "status": str(analysis["status"]),
                "changed_files": list(analysis["changed_files"]),
            }
            for analysis in _sessions.values()
        ]


def get_analysis_context(analysis_id: str) -> dict[str, object] | None:
    with _lock:
        analysis = _sessions.get(analysis_id)
        snapshot = _snapshots.get(analysis_id)
        if analysis is None or snapshot is None:
            return None
        return {**analysis, "review_snapshot": dict(snapshot)}


def submit_bob_review(
    analysis_id: str,
    confirmed_files: list[str],
    possible_files: list[str],
    not_affected_files: list[str],
    rationale: str,
) -> dict[str, object] | None:
    with _lock:
        analysis = _sessions.get(analysis_id)
        if analysis is None:
            return None

        groups = {
            "bob_confirmed_impact": confirmed_files,
            "possible_impact": possible_files,
            "not_affected": not_affected_files,
        }
        all_classified: list[str] = []
        for group in groups.values():
            if len(group) != len(set(group)):
                raise ValueError("Each Bob classification list must contain unique file paths")
            all_classified.extend(group)
        if len(all_classified) != len(set(all_classified)):
            raise ValueError("A file can appear in only one Bob classification list")

        changed = set(analysis["changed_files"])
        if not changed.issubset(set(confirmed_files)):
            raise ValueError("Bob must confirm every changed file as impact")
        known = set(analysis["predicted_impact"]["files"]) | set(analysis["not_affected"])
        submitted = set(all_classified)
        missing = sorted(known - submitted)
        unknown = sorted(submitted - known)
        if missing or unknown:
            details = []
            if missing:
                details.append(f"missing classifications: {', '.join(missing)}")
            if unknown:
                details.append(f"unknown files: {', '.join(unknown)}")
            raise ValueError("Bob must classify every analyzed file; " + "; ".join(details))

        bob_status = {
            **{path: "bob_confirmed_impact" for path in confirmed_files},
            **{path: "possible_impact" for path in possible_files},
            **{path: "not_affected" for path in not_affected_files},
        }
        predicted = set(analysis["predicted_impact"]["files"])
        all_files = sorted(known)
        analysis["bob_review"] = {
            "status": "complete",
            **{name: sorted(paths) for name, paths in groups.items()},
            "rationale": rationale,
            "file_assessments": {
                path: {
                    "prediction": "predicted_impact" if path in predicted else "not_predicted",
                    "bob_assessment": bob_status[path],
                }
                for path in all_files
            },
        }
        analysis["test_results"] = {"status": "not_run", "passed": False}
        analysis["safe_to_merge"] = False
        analysis["status"] = "awaiting_tests"
        return analysis


def execute_targeted_tests(analysis_id: str) -> dict[str, object] | None:
    with _lock:
        analysis = _sessions.get(analysis_id)
        snapshot = _snapshots.get(analysis_id)
        if analysis is None or snapshot is None:
            return None
        if analysis["bob_review"] is None:
            raise ValueError("IBM Bob must complete semantic review before tests run")
        selected_tests = list(analysis["predicted_impact"]["tests"])

    result = run_targeted_tests(snapshot, selected_tests)
    with _lock:
        analysis = _sessions[analysis_id]
        analysis["test_results"] = result
        analysis["safe_to_merge"] = False
        if result["status"] == "no_tests":
            analysis["status"] = "no_targeted_tests"
        elif result["status"] in {"error", "timeout"}:
            analysis["status"] = "test_execution_error"
        elif not result["passed"]:
            analysis["status"] = "regression_detected"
        elif analysis["bob_review"]["possible_impact"]:
            analysis["status"] = "possible_impact_unresolved"
        elif analysis["parse_errors"]:
            analysis["status"] = "analysis_errors"
        else:
            analysis["status"] = "safe_to_merge"
            analysis["safe_to_merge"] = True
        return analysis
