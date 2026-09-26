from pathlib import Path

import pytest

from codetwin.analyzer import InvalidAnalysisRequest, analyze_repository


def test_analysis_is_deterministic_and_reports_transitive_python_dependencies():
    snapshot = {
        "app/payments.py": "def capture():\n    return True\n",
        "app/orders.py": "from app.payments import capture\ndef checkout():\n    return capture()\n",
        "app/routes/orders.py": (
            "from fastapi import APIRouter\n"
            "from app.orders import checkout\n"
            "router = APIRouter(prefix='/orders')\n"
            "@router.post('/checkout')\n"
            "def create_order():\n    return checkout()\n"
        ),
        "tests/test_orders.py": "from app.routes.orders import create_order\ndef test_checkout():\n    assert create_order()\n",
        "app/catalog.py": "def list_products():\n    return []\n",
    }

    report = analyze_repository(snapshot, ["app/payments.py"])

    assert report == analyze_repository(snapshot, ["app/payments.py"])
    assert report["predicted_impact"]["files"] == [
        "app/orders.py",
        "app/payments.py",
        "app/routes/orders.py",
        "tests/test_orders.py",
    ]
    assert report["predicted_impact"]["tests"] == ["tests/test_orders.py"]
    assert report["predicted_impact"]["api_routes"] == [
        {
            "file": "app/routes/orders.py",
            "method": "POST",
            "path": "/orders/checkout",
            "handler": "create_order",
        }
    ]
    assert report["not_affected"] == ["app/catalog.py"]
    assert report["dependency_edges"] == sorted(
        report["dependency_edges"], key=lambda edge: (edge["source"], edge["target"])
    )


def test_function_call_graph_reports_impacted_symbols_and_notification_consumer():
    ecommerce_root = Path(__file__).resolve().parents[2] / "examples" / "ecommerce"
    snapshot = {
        path.relative_to(ecommerce_root).as_posix(): path.read_text(encoding="utf-8")
        for path in ecommerce_root.rglob("*.py")
        if ".venv" not in path.parts and "__pycache__" not in path.parts
    }

    report = analyze_repository(snapshot, ["app/payments/service.py"])
    predicted = report["predicted_impact"]
    function_ids = {function["id"] for function in predicted["functions"]}

    assert "app/payments/service.py" in predicted["files"]
    assert "app/notifications/service.py" in predicted["files"]
    assert "app/orders/service.py" in predicted["files"]
    assert "app/routes/orders.py" in predicted["api_files"]
    assert "tests/test_payment_workflow.py" in predicted["tests"]
    assert "app/payments/service.py::PaymentService.capture" in function_ids
    assert "app/notifications/service.py::NotificationsService.on_payment_transition" in function_ids
    assert "app/orders/service.py::OrdersService.checkout" in function_ids
    assert {
        "file": "app/routes/orders.py",
        "method": "POST",
        "path": "/orders/checkout",
        "handler": "checkout",
    } in predicted["api_routes"]


def test_syntax_errors_are_reported_and_invalid_changed_paths_are_rejected():
    report = analyze_repository(
        {"app/broken.py": "def broken(:\n    pass\n", "app/other.py": "VALUE = 1\n"},
        ["app/broken.py"],
    )

    assert report["parse_errors"][0]["file"] == "app/broken.py"
    assert "line 1" in report["parse_errors"][0]["message"]
    with pytest.raises(InvalidAnalysisRequest):
        analyze_repository({"app/main.py": "pass\n"}, ["../outside.py"])


def test_missing_and_non_python_changed_files_are_rejected():
    with pytest.raises(InvalidAnalysisRequest, match="missing"):
        analyze_repository({"app/main.py": "pass\n"}, ["app/missing.py"])
    with pytest.raises(InvalidAnalysisRequest, match="Python"):
        analyze_repository({"README.md": "text"}, ["README.md"])
