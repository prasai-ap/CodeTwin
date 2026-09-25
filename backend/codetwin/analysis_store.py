"""In-memory analysis sessions for the local hackathon prototype."""

from __future__ import annotations

from uuid import uuid4

from codetwin.analyzer import analyze_repository

_sessions: dict[str, dict[str, object]] = {}


def create_analysis(files: dict[str, str], changed_files: list[str]) -> dict[str, object]:
    report = analyze_repository(files, changed_files)
    analysis_id = uuid4().hex
    analysis: dict[str, object] = {
        "analysis_id": analysis_id,
        "status": "awaiting_bob_review",
        **report,
        "bob_review": None,
        "test_results": {"status": "not_run", "passed": False},
        "safe_to_merge": False,
    }
    _sessions[analysis_id] = analysis
    return analysis


def get_analysis(analysis_id: str) -> dict[str, object] | None:
    return _sessions.get(analysis_id)


def submit_bob_review(
    analysis_id: str,
    confirmed_files: list[str],
    possible_files: list[str],
    not_affected_files: list[str],
    rationale: str,
) -> dict[str, object] | None:
    analysis = get_analysis(analysis_id)
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

    predicted = analysis["predicted_impact"]["files"]
    known_files = set(predicted) | set(analysis["not_affected"])
    submitted = set(all_classified)
    unknown = sorted(submitted - known_files)
    missing = sorted(known_files - submitted)
    if unknown or missing:
        details = []
        if missing:
            details.append(f"missing classifications: {', '.join(missing)}")
        if unknown:
            details.append(f"unknown files: {', '.join(unknown)}")
        raise ValueError("Bob must classify every analyzed Python file; " + "; ".join(details))

    bob_status = {
        **{path: "bob_confirmed_impact" for path in confirmed_files},
        **{path: "possible_impact" for path in possible_files},
        **{path: "not_affected" for path in not_affected_files},
    }
    prediction_status = {
        path: "predicted_impact" if path in predicted else "not_predicted"
        for path in sorted(known_files)
    }
    analysis["bob_review"] = {
        "status": "complete",
        **{name: sorted(paths) for name, paths in groups.items()},
        "rationale": rationale,
        "file_assessments": {
            path: {
                "prediction": prediction_status[path],
                "bob_assessment": bob_status[path],
            }
            for path in sorted(known_files)
        },
    }
    analysis["status"] = "awaiting_tests"
    return analysis
