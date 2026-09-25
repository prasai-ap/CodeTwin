"""Create the checked-in payment regression scenario for the UI demo."""

from pathlib import Path

from codetwin.analysis_store import create_analysis, get_analysis_context

_CHANGED_FILE = "app/payments/service.py"


def _load_payment_demo() -> tuple[dict[str, str], str, str]:
    project_root = Path(__file__).resolve().parents[2] / "examples" / "ecommerce"
    files = {
        path.relative_to(project_root).as_posix(): path.read_text(encoding="utf-8")
        for source_root in (project_root / "app", project_root / "tests")
        for path in source_root.rglob("*.py")
    }
    patch_path = project_root / "scenarios" / "payment_amount_regression.patch"
    patch_lines = patch_path.read_text(encoding="utf-8").splitlines()
    old_line = next(line[1:] for line in patch_lines if line.startswith("-") and not line.startswith("---"))
    new_line = next(line[1:] for line in patch_lines if line.startswith("+") and not line.startswith("+++"))
    return files, old_line, new_line


def create_payment_regression_demo() -> dict[str, object]:
    files, old_line, new_line = _load_payment_demo()
    source = files[_CHANGED_FILE]
    if source.count(old_line) != 1:
        raise RuntimeError("The payment regression patch no longer matches the demo service")
    files[_CHANGED_FILE] = source.replace(old_line, new_line, 1)

    analysis = create_analysis(files, [_CHANGED_FILE])
    analysis["demo_scenario"] = "payment_amount_regression"
    return analysis


def revalidate_payment_regression_demo(analysis_id: str) -> dict[str, object] | None:
    previous = get_analysis_context(analysis_id)
    if previous is None:
        return None
    if previous.get("demo_scenario") != "payment_amount_regression":
        raise ValueError("Only the payment regression demo can create this corrected revision")
    if previous.get("status") != "regression_detected":
        raise ValueError("Run the targeted tests and detect the regression before applying the demo fix")

    snapshot = previous.get("review_snapshot")
    if not isinstance(snapshot, dict) or not all(
        isinstance(path, str) and isinstance(source, str) for path, source in snapshot.items()
    ):
        raise RuntimeError("The payment regression snapshot is invalid")
    files = dict(snapshot)
    _, old_line, regression_line = _load_payment_demo()
    source = files.get(_CHANGED_FILE)
    if source is None or source.count(regression_line) != 1:
        raise RuntimeError("The captured payment regression no longer matches the demo fix")
    files[_CHANGED_FILE] = source.replace(regression_line, old_line, 1)

    changed_files = previous.get("changed_files")
    if not isinstance(changed_files, list) or not all(isinstance(path, str) for path in changed_files):
        raise RuntimeError("The captured changed file list is invalid")
    corrected = create_analysis(files, changed_files)
    corrected["demo_scenario"] = "payment_amount_regression_fixed"
    corrected["parent_analysis_id"] = analysis_id
    return corrected
