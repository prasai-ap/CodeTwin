import pytest

from codetwin.impact_engine import (
    PREDICTED_IMPACT,
    InvalidImpactRequest,
    ProposedChange,
    predict_impact,
)
from codetwin.repository_graph import build_repository_graph


@pytest.fixture
def graph():
    return build_repository_graph({
        "app/__init__.py": "",
        "app/domain.py": (
            "def calculate_total():\n"
            "    return 42\n"
        ),
        "app/service.py": (
            "from app.domain import calculate_total\n"
            "def get_total():\n"
            "    return calculate_total()\n"
        ),
        "app/api.py": (
            "from fastapi import APIRouter\n"
            "from app.service import get_total\n"
            "router = APIRouter(prefix='/totals')\n"
            "@router.get('')\n"
            "def read_total():\n"
            "    return get_total()\n"
        ),
        "tests/test_api.py": (
            "from app.api import read_total\n"
            "def test_read_total():\n"
            "    assert read_total() == 42\n"
        ),
        "app/unrelated.py": (
            "def list_products():\n"
            "    return []\n"
        ),
    })


@pytest.fixture
def prediction(graph):
    return predict_impact(
        graph,
        ProposedChange(
            component_kind="function",
            component_id="app/domain.py::calculate_total",
            description="Change total calculation behavior",
        ),
    )


def test_direct_dependency_has_evidence_and_a_predicted_label(prediction):
    direct = next(
        item for item in prediction.affected_functions
        if item.component_id == "app/service.py::get_total"
    )

    assert direct.label == PREDICTED_IMPACT
    assert direct.dependency_path.node_ids == (
        "app/domain.py::calculate_total",
        "app/service.py::get_total",
    )
    assert direct.dependency_path.steps[0].relationship == "called_by"
    assert direct.dependency_path.steps[0].evidence == "calculate_total()"
    assert direct.reasons


def test_indirect_dependency_reaches_api_through_service(prediction):
    api = next(
        item for item in prediction.affected_functions
        if item.component_id == "app/api.py::read_total"
    )

    assert api.dependency_path.node_ids == (
        "app/domain.py::calculate_total",
        "app/service.py::get_total",
        "app/api.py::read_total",
    )
    assert [step.relationship for step in api.dependency_path.steps] == [
        "called_by",
        "called_by",
    ]
    assert any("::GET::read_total::" in item.component_id for item in prediction.affected_apis)


def test_related_test_is_predicted_with_a_dependency_path(prediction):
    test = next(
        item for item in prediction.affected_tests
        if item.component_id == "test::tests/test_api.py::test_read_total"
    )

    assert test.label == "PREDICTED IMPACT"
    assert test.dependency_path.node_ids[0] == "app/domain.py::calculate_total"
    assert test.dependency_path.node_ids[-1] == test.component_id
    assert "tests/test_api.py" in {
        item.component_id for item in prediction.affected_files
    }


def test_pytest_fixture_links_an_affected_route_to_an_http_style_test():
    graph = build_repository_graph({
        "checkout-demo/shop/__init__.py": "",
        "checkout-demo/shop/domain.py": "def calculate_total():\n    return 42\n",
        "checkout-demo/shop/api.py": (
            "from shop.domain import calculate_total\n"
            "def read_total():\n"
            "    return calculate_total()\n"
        ),
        "checkout-demo/tests/conftest.py": (
            "import pytest\n"
            "from shop.api import read_total\n"
            "@pytest.fixture\n"
            "def client():\n"
            "    return read_total\n"
        ),
        "checkout-demo/tests/test_http.py": (
            "def test_total(client):\n"
            "    assert client() == 42\n"
        ),
    })

    prediction = predict_impact(
        graph,
        ProposedChange("function", "checkout-demo/shop/domain.py::calculate_total"),
    )

    assert any(
        item.component_id == "test::checkout-demo/tests/test_http.py::test_total"
        for item in prediction.affected_tests
    )


def test_unrelated_component_is_not_in_the_impact_set(prediction):
    impacted_ids = {
        item.component_id
        for group in (
            prediction.affected_files,
            prediction.affected_modules,
            prediction.affected_functions,
            prediction.affected_classes,
            prediction.affected_apis,
            prediction.affected_tests,
        )
        for item in group
    }

    assert "app/unrelated.py::list_products" not in impacted_ids
    assert "app/unrelated.py" not in impacted_ids
    assert all(item.label == PREDICTED_IMPACT for group in (
        prediction.affected_files,
        prediction.affected_modules,
        prediction.affected_functions,
        prediction.affected_classes,
        prediction.affected_apis,
        prediction.affected_tests,
    ) for item in group)
    assert prediction.label == PREDICTED_IMPACT
    assert all(path.label == PREDICTED_IMPACT for path in prediction.dependency_paths)
    assert all(
        step.label == PREDICTED_IMPACT
        for path in prediction.dependency_paths
        for step in path.steps
    )
    assert all(item.label == PREDICTED_IMPACT for item in prediction.risk_indicators)


def test_method_change_does_not_spread_to_sibling_routes_through_shared_class():
    graph = build_repository_graph({
        "app/__init__.py": "",
        "app/service.py": (
            "class Service:\n"
            "    def changed(self):\n"
            "        return 'changed'\n"
            "    def unrelated(self):\n"
            "        return 'unrelated'\n"
        ),
        "app/auth.py": (
            "class AuthService:\n"
            "    def authenticate(self):\n"
            "        return 'user'\n"
        ),
        "app/api.py": (
            "from fastapi import APIRouter\n"
            "from app.auth import AuthService\n"
            "from app.service import Service\n"
            "router = APIRouter()\n"
            "@router.post('/change')\n"
            "def change():\n"
            "    return Service().changed(), AuthService().authenticate()\n"
            "@router.get('/unrelated')\n"
            "def unrelated():\n"
            "    return Service().unrelated()\n"
            "@router.get('/profile')\n"
            "def profile():\n"
            "    return AuthService().authenticate()\n"
        ),
    })

    prediction = predict_impact(
        graph,
        ProposedChange("function", "app/service.py::Service.changed"),
    )

    expected_api = next(
        endpoint.id for endpoint in graph.api_endpoints
        if endpoint.handler_id == "app/api.py::change"
    )
    assert {
        item.component_id for item in prediction.affected_apis
    } == {expected_api}
    assert "app/api.py::unrelated" not in {
        item.component_id for item in prediction.affected_functions
    }
    assert "app/api.py::profile" not in {
        item.component_id for item in prediction.affected_functions
    }
    assert "app/auth.py::AuthService.authenticate" not in {
        item.component_id for item in prediction.affected_functions
    }


def test_file_change_includes_methods_declared_in_that_file():
    graph = build_repository_graph({
        "app/service.py": (
            "class Service:\n"
            "    def run(self):\n"
            "        return True\n"
        ),
    })

    prediction = predict_impact(graph, ProposedChange("file", "app/service.py"))

    assert "app/service.py::Service" in {
        item.component_id for item in prediction.affected_classes
    }
    assert "app/service.py::Service.run" in {
        item.component_id for item in prediction.affected_functions
    }


def test_class_change_reaches_subclasses_and_instantiating_functions():
    graph = build_repository_graph({
        "app/__init__.py": "",
        "app/base.py": "class BaseRecord:\n    pass\n",
        "app/child.py": "from app.base import BaseRecord\nclass ChildRecord(BaseRecord):\n    pass\n",
        "app/service.py": "from app.child import ChildRecord\ndef create_record():\n    return ChildRecord()\n",
    })

    prediction = predict_impact(
        graph,
        ProposedChange("class", "app/base.py::BaseRecord"),
    )

    assert "app/child.py::ChildRecord" in {
        item.component_id for item in prediction.affected_classes
    }
    assert "app/service.py::create_record" in {
        item.component_id for item in prediction.affected_functions
    }
    assert prediction.affected_modules


def test_missing_related_tests_are_reported_as_a_predicted_risk():
    graph = build_repository_graph({
        "app/worker.py": "def run_job():\n    return True\n",
    })

    prediction = predict_impact(
        graph,
        ProposedChange("function", "app/worker.py::run_job"),
    )

    risk = next(item for item in prediction.risk_indicators if item.code == "no_affected_tests_found")
    assert risk.label == PREDICTED_IMPACT
    assert risk.severity == "medium"


def test_change_must_identify_a_component_in_the_supplied_graph(graph):
    with pytest.raises(InvalidImpactRequest, match="not present"):
        predict_impact(
            graph,
            ProposedChange(component_kind="function", component_id="app/missing.py::missing"),
        )

    with pytest.raises(InvalidImpactRequest, match="not `class`"):
        predict_impact(
            graph,
            ProposedChange(component_kind="class", component_id="app/domain.py::calculate_total"),
        )


def test_prediction_serializes_only_predicted_impact_labels(prediction):
    payload = prediction.to_dict()
    assert payload["label"] == "PREDICTED IMPACT"
    assert all(item["label"] == "PREDICTED IMPACT" for item in payload["affected_functions"])
    assert "CONFIRMED IMPACT" not in str(payload)
