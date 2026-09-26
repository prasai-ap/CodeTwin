"""Load and prepare the synthetic e-commerce payment regression scenario."""

from __future__ import annotations

from pathlib import Path

from codetwin.analysis_store import create_analysis, get_analysis
from codetwin.analyzer import InvalidAnalysisRequest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ECOMMERCE_ROOT = PROJECT_ROOT / "examples" / "ecommerce"


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
    if not removed or not added:
        raise InvalidAnalysisRequest(f"Demo patch is empty or malformed: {patch_path.name}")
    return "\n".join(removed), "\n".join(added)


def _snapshot() -> dict[str, str]:
    files: dict[str, str] = {}
    for folder in ("app", "tests"):
        for path in sorted((ECOMMERCE_ROOT / folder).rglob("*.py")):
            if ".venv" in path.parts or "__pycache__" in path.parts:
                continue
            files[path.relative_to(ECOMMERCE_ROOT).as_posix()] = path.read_text(encoding="utf-8")
    if not files:
        raise FileNotFoundError("Synthetic e-commerce demo files are unavailable")
    return files


def _apply_patch(files: dict[str, str], patch_name: str, target: str) -> dict[str, str]:
    old_block, new_block = _patch_blocks(ECOMMERCE_ROOT / "scenarios" / patch_name)
    source = files.get(target)
    if source is None or source.count(old_block) != 1:
        raise InvalidAnalysisRequest(f"Demo patch does not match {target}")
    updated = dict(files)
    updated[target] = source.replace(old_block, new_block, 1)
    return updated


def create_payment_regression() -> dict[str, object]:
    files = _apply_patch(
        _snapshot(), "payment_authorization_regression.patch", "app/payments/service.py"
    )
    analysis = create_analysis(files, ["app/payments/service.py"])
    analysis["demo_scenario"] = {
        "name": "payment_authorization_regression",
        "description": "Payment capture now passes through authorized, while notifications still expect a direct pending-to-completed transition.",
        "parent_analysis_id": None,
    }
    return analysis


def create_payment_fix(analysis_id: str) -> dict[str, object] | None:
    parent = get_analysis(analysis_id)
    if parent is None:
        return None
    demo_scenario = parent.get("demo_scenario")
    if not isinstance(demo_scenario, dict) or demo_scenario.get("name") != "payment_authorization_regression":
        raise ValueError("The demo fix is available only for the payment authorization scenario")
    if parent["status"] != "regression_detected":
        raise ValueError("Run Bob review and targeted tests; the payment regression must be reproduced before applying the demo fix")

    files = _apply_patch(
        _snapshots_for_fix(analysis_id), "payment_notification_fix.patch", "app/notifications/service.py"
    )
    analysis = create_analysis(files, ["app/notifications/service.py"])
    analysis["demo_scenario"] = {
        "name": "payment_authorization_regression_fixed",
        "description": "The notification consumer accepts the authorized-to-completed transition; Bob must revalidate the new snapshot.",
        "parent_analysis_id": analysis_id,
    }
    return analysis


def _snapshots_for_fix(analysis_id: str) -> dict[str, str]:
    """Return the immutable source snapshot held by the analysis store."""
    from codetwin.analysis_store import get_analysis_context

    context = get_analysis_context(analysis_id)
    if context is None:
        raise InvalidAnalysisRequest("Analysis snapshot is unavailable")
    snapshot = context.get("review_snapshot")
    if not isinstance(snapshot, dict) or not all(
        isinstance(path, str) and isinstance(content, str) for path, content in snapshot.items()
    ):
        raise InvalidAnalysisRequest("Analysis snapshot is invalid")
    return snapshot
