"""Create the checked-in payment regression scenario for the UI demo."""

from pathlib import Path

from codetwin.analysis_store import create_analysis


def create_payment_regression_demo() -> dict[str, object]:
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
    changed_file = "app/payments/service.py"
    source = files[changed_file]
    if source.count(old_line) != 1:
        raise RuntimeError("The payment regression patch no longer matches the demo service")
    files[changed_file] = source.replace(old_line, new_line, 1)

    analysis = create_analysis(files, [changed_file])
    analysis["demo_scenario"] = "payment_amount_regression"
    return analysis
