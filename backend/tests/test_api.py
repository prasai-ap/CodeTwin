from fastapi.testclient import TestClient

from codetwin.api import create_app


def _classify_every_file(analysis: dict[str, object]) -> dict[str, object]:
    predicted = analysis["predicted_impact"]["files"]
    not_affected = analysis["not_affected"]
    return {
        "confirmed_files": predicted,
        "possible_files": [],
        "not_affected_files": not_affected,
        "rationale": "Reviewed the changed source and its callers, routes, and tests in the repository snapshot.",
    }


def test_health_analysis_and_bob_review_are_separate_from_predictions():
    client = TestClient(create_app(frontend_origins="https://demo.example"))

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert client.options(
        "/health",
        headers={
            "Origin": "https://demo.example",
            "Access-Control-Request-Method": "GET",
        },
    ).headers["access-control-allow-origin"] == "https://demo.example"

    response = client.post("/analyze", json={
        "files": {
            "app/payments.py": "def capture(): return True\n",
            "app/orders.py": "from app.payments import capture\ndef checkout(): return capture()\n",
            "tests/test_orders.py": "from app.orders import checkout\ndef test_checkout(): assert checkout()\n",
            "app/catalog.py": "def list_products(): return []\n",
        },
        "changed_files": ["app/payments.py"],
    })
    assert response.status_code == 200
    analysis = response.json()
    assert analysis["status"] == "awaiting_bob_review"
    assert analysis["predicted_impact"]["files"] == [
        "app/orders.py", "app/payments.py", "tests/test_orders.py"
    ]
    assert analysis["bob_review"] is None
    assert analysis["safe_to_merge"] is False
    assert client.post(f"/analyses/{analysis['analysis_id']}/run-tests").status_code == 409

    review = client.post(
        f"/analyses/{analysis['analysis_id']}/bob-review",
        json=_classify_every_file(analysis),
    )
    assert review.status_code == 200
    body = review.json()
    assert body["status"] == "awaiting_tests"
    assert body["bob_review"]["file_assessments"]["app/catalog.py"] == {
        "prediction": "not_predicted",
        "bob_assessment": "not_affected",
    }

    tested = client.post(f"/analyses/{analysis['analysis_id']}/run-tests")
    assert tested.status_code == 200
    assert tested.json()["status"] == "safe_to_merge"
    assert tested.json()["safe_to_merge"] is True


def test_payment_regression_is_detected_then_fix_requires_fresh_bob_and_tests():
    client = TestClient(create_app())
    analysis = client.post("/demo/payment-regression").json()
    analysis_id = analysis["analysis_id"]

    context = client.get(f"/analyses/{analysis_id}/context").json()
    assert "PaymentStatus.AUTHORIZED" in context["review_snapshot"]["app/payments/service.py"]
    assert "previous.status == PaymentStatus.PENDING" in context["review_snapshot"]["app/notifications/service.py"]
    assert any(route["path"] == "/orders/checkout" for route in analysis["predicted_impact"]["api_routes"])

    reviewed = client.post(
        f"/analyses/{analysis_id}/bob-review",
        json=_classify_every_file(analysis),
    )
    assert reviewed.status_code == 200
    failed = client.post(f"/analyses/{analysis_id}/run-tests")
    assert failed.status_code == 200
    assert failed.json()["status"] == "regression_detected"
    assert failed.json()["safe_to_merge"] is False
    assert any(
        result["file"] == "tests/test_payment_workflow.py"
        and "payment completion notification is missing" in result["output"]
        for result in failed.json()["test_results"]["results"]
    )

    fixed = client.post(f"/analyses/{analysis_id}/demo-fix")
    assert fixed.status_code == 200
    fixed_analysis = fixed.json()
    assert fixed_analysis["demo_scenario"]["parent_analysis_id"] == analysis_id
    assert fixed_analysis["status"] == "awaiting_bob_review"
    assert fixed_analysis["safe_to_merge"] is False
    assert client.post(f"/analyses/{fixed_analysis['analysis_id']}/run-tests").status_code == 409

    fixed_review = client.post(
        f"/analyses/{fixed_analysis['analysis_id']}/bob-review",
        json=_classify_every_file(fixed_analysis),
    )
    assert fixed_review.status_code == 200
    validated = client.post(f"/analyses/{fixed_analysis['analysis_id']}/run-tests").json()
    assert validated["status"] == "safe_to_merge"
    assert validated["safe_to_merge"] is True
    assert validated["test_results"]["passed"] is True


def test_bob_must_classify_every_known_file_once():
    client = TestClient(create_app())
    analysis = client.post("/analyze", json={
        "files": {"app/main.py": "def run(): return 1\n", "app/other.py": "VALUE = 1\n"},
        "changed_files": ["app/main.py"],
    }).json()

    incomplete = client.post(
        f"/analyses/{analysis['analysis_id']}/bob-review",
        json={
            "confirmed_files": ["app/main.py"],
            "possible_files": [],
            "not_affected_files": [],
            "rationale": "One file was omitted.",
        },
    )
    assert incomplete.status_code == 422


def test_analysis_rejects_paths_that_normalize_to_the_same_file():
    client = TestClient(create_app())
    response = client.post("/analyze", json={
        "files": {"app/main.py": "VALUE = 1\n", "app\\main.py": "VALUE = 2\n"},
        "changed_files": ["app/main.py"],
    })

    assert response.status_code == 422
    assert "Duplicate normalized repository path" in response.json()["detail"]


def test_passing_tests_do_not_clear_possible_bob_impact():
    client = TestClient(create_app())
    analysis = client.post("/analyze", json={
        "files": {
            "app/main.py": "def run(): return 1\n",
            "tests/test_main.py": "from app.main import run\ndef test_run(): assert run() == 1\n",
            "app/other.py": "VALUE = 1\n",
        },
        "changed_files": ["app/main.py"],
    }).json()
    review = client.post(
        f"/analyses/{analysis['analysis_id']}/bob-review",
        json={
            "confirmed_files": ["app/main.py", "tests/test_main.py"],
            "possible_files": ["app/other.py"],
            "not_affected_files": [],
            "rationale": "The isolated file has a possible dynamic relationship requiring maintainer review.",
        },
    )
    assert review.status_code == 200

    result = client.post(f"/analyses/{analysis['analysis_id']}/run-tests").json()
    assert result["test_results"]["passed"] is True
    assert result["status"] == "possible_impact_unresolved"
    assert result["safe_to_merge"] is False
