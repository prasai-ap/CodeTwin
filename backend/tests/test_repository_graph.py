from codetwin.analysis_models import APIEndpoint, Class, DependencyEdge, File, Function, Module, Test as TestModel
from codetwin.analyzer import analyze_repository, build_repository_graph


def test_repository_graph_contains_typed_nodes_and_evidence_for_relationships():
    files = {
        "app/__init__.py": "",
        "app/orders.py": (
            "class OrderService:\n"
            "    def complete(self):\n"
            "        return 'completed'\n"
        ),
        "app/payments.py": (
            "from app.orders import OrderService\n"
            "class PaymentService:\n"
            "    def __init__(self, orders: OrderService | None = None):\n"
            "        self.orders = orders or OrderService()\n"
            "    def capture(self):\n"
            "        return self.orders.complete()\n"
        ),
        "app/api.py": (
            "from fastapi import APIRouter\n"
            "from app.payments import PaymentService\n"
            "router = APIRouter(prefix='/payments')\n"
            "service = PaymentService()\n"
            "@router.post('/capture')\n"
            "def capture():\n"
            "    return service.capture()\n"
        ),
        "tests/test_payments.py": (
            "from app.api import capture\n"
            "def test_capture():\n"
            "    assert capture() == 'completed'\n"
        ),
        "README.md": "Synthetic repository snapshot.\n",
    }

    graph = build_repository_graph(files)

    assert isinstance(graph.files[0], File)
    assert isinstance(graph.modules[0], Module)
    assert isinstance(graph.functions[0], Function)
    assert isinstance(graph.classes[0], Class)
    assert isinstance(graph.api_endpoints[0], APIEndpoint)
    assert isinstance(graph.tests[0], TestModel)
    readme = next(item for item in graph.files if item.path == "README.md")
    assert readme.language == "markdown"
    assert readme.parse_status == "not_python"

    import_edge = next(
        edge for edge in graph.edges
        if edge.kind == "imports" and edge.source == "app/payments.py"
    )
    assert isinstance(import_edge, DependencyEdge)
    assert import_edge.target == "app/orders.py"
    assert import_edge.line == 1
    assert import_edge.evidence == "from app.orders import OrderService"
    assert import_edge.reason

    service_call = next(
        edge for edge in graph.edges
        if edge.kind == "calls" and edge.source == "app/payments.py::PaymentService.capture"
    )
    assert service_call.target == "app/orders.py::OrderService.complete"
    assert service_call.evidence == "self.orders.complete()"
    assert "constructor assignment" in service_call.reason
    assert any(
        item.kind == "dynamic_dispatch" and item.evidence == "self.orders.complete()"
        for item in graph.limitations
    )

    route_call = next(
        edge for edge in graph.edges
        if edge.kind == "calls" and edge.source == "app/api.py::capture"
    )
    assert route_call.target == "app/payments.py::PaymentService.capture"
    endpoint = graph.api_endpoints[0]
    assert endpoint.method == "POST"
    assert endpoint.path == "/payments/capture"
    assert endpoint.handler_id == "app/api.py::capture"
    assert any(edge.kind == "handled_by" and edge.target == endpoint.handler_id for edge in graph.edges)
    assert graph.tests[0].name == "test_capture"


def test_unresolved_instance_calls_are_reported_instead_of_guessed():
    graph = build_repository_graph({
        "app/service.py": (
            "class OrderService:\n"
            "    def complete(self):\n"
            "        return True\n"
            "class PaymentService:\n"
            "    def capture(self):\n"
            "        return self.unknown_service.complete()\n"
        ),
    })

    assert not any(
        edge.kind == "calls"
        and edge.source == "app/service.py::PaymentService.capture"
        and edge.target == "app/service.py::OrderService.complete"
        for edge in graph.edges
    )
    limitation = next(item for item in graph.limitations if item.kind == "unresolved_internal_call")
    assert limitation.evidence == "self.unknown_service.complete()"
    assert "no call edge was invented" in limitation.detail


def test_ambiguous_module_names_do_not_create_import_edges():
    graph = build_repository_graph({
        "app/payments.py": "def capture(): pass\n",
        "app/payments/__init__.py": "def capture(): pass\n",
        "app/client.py": "from app.payments import capture\n",
    })

    assert not any(
        edge.kind == "imports" and edge.source == "app/client.py"
        for edge in graph.edges
    )
    assert len([module for module in graph.modules if module.name == "app.payments"]) == 2
    assert any(item.kind == "ambiguous_module" for item in graph.limitations)


def test_relative_aliased_imports_resolve_calls_without_short_name_guessing():
    graph = build_repository_graph({
        "shop/__init__.py": "",
        "shop/core.py": "def calculate():\n    return 42\n",
        "shop/client.py": (
            "from .core import calculate as compute\n"
            "def run():\n"
            "    return compute()\n"
        ),
        "shop/shadow.py": (
            "def calculate():\n"
            "    return 42\n"
            "def run(calculate):\n"
            "    return calculate()\n"
        ),
    })

    aliased = next(edge for edge in graph.edges if edge.source == "shop/client.py::run")
    assert aliased.kind == "calls"
    assert aliased.target == "shop/core.py::calculate"
    assert "import binding" in aliased.reason

    assert not any(
        edge.kind == "calls"
        and edge.source == "shop/shadow.py::run"
        and edge.target == "shop/shadow.py::calculate"
        for edge in graph.edges
    )
    assert any(
        item.kind == "unresolved_internal_call"
        and item.evidence == "calculate()"
        for item in graph.limitations
    )


def test_chained_constructor_method_calls_resolve_to_declared_repository_method():
    graph = build_repository_graph({
        "shop/__init__.py": "",
        "shop/worker.py": (
            "class Worker:\n"
            "    def execute(self):\n"
            "        return True\n"
        ),
        "shop/handler.py": (
            "from shop.worker import Worker\n"
            "def run():\n"
            "    return Worker().execute()\n"
        ),
    })

    call = next(
        edge for edge in graph.edges
        if edge.kind == "calls" and edge.source == "shop/handler.py::run"
    )
    assert call.target == "shop/worker.py::Worker.execute"
    assert call.evidence == "Worker().execute()"
    assert "receiver expression" in call.reason
    assert any(
        edge.kind == "instantiates"
        and edge.source == "shop/handler.py::run"
        and edge.target == "shop/worker.py::Worker"
        for edge in graph.edges
    )


def test_builtin_call_is_not_reported_as_an_unresolved_repository_call():
    graph = build_repository_graph({
        "app/catalog.py": (
            "class Catalog:\n"
            "    def list(self):\n"
            "        return []\n"
            "def render(values):\n"
            "    return list(values)\n"
        ),
    })

    assert not any(
        item.kind == "unresolved_internal_call" and item.evidence == "list(values)"
        for item in graph.limitations
    )


def test_repository_snapshot_prefix_does_not_break_package_import_resolution():
    graph = build_repository_graph({
        "synthetic-checkout/shop/__init__.py": "",
        "synthetic-checkout/shop/worker.py": (
            "class Worker:\n"
            "    def execute(self):\n"
            "        return True\n"
        ),
        "synthetic-checkout/shop/handler.py": (
            "from shop.worker import Worker\n"
            "class Handler:\n"
            "    def __init__(self, worker: Worker | None = None):\n"
            "        self.worker = worker or Worker()\n"
            "    def run(self):\n"
            "        return self.worker.execute()\n"
        ),
    })

    import_edge = next(
        edge for edge in graph.edges
        if edge.kind == "imports" and edge.source == "synthetic-checkout/shop/handler.py"
    )
    call_edge = next(
        edge for edge in graph.edges
        if edge.kind == "calls" and edge.source == "synthetic-checkout/shop/handler.py::Handler.run"
    )
    assert import_edge.target == "synthetic-checkout/shop/worker.py"
    assert call_edge.target == "synthetic-checkout/shop/worker.py::Worker.execute"
    assert call_edge.evidence == "self.worker.execute()"


def test_pytest_fixtures_connect_affected_code_to_tests_without_direct_imports():
    files = {
        "snapshot-copy/shop/__init__.py": "",
        "snapshot-copy/shop/domain.py": "def calculate():\n    return 42\n",
        "snapshot-copy/shop/api.py": (
            "from shop.domain import calculate\n"
            "def handle():\n"
            "    return calculate()\n"
        ),
        "snapshot-copy/tests/conftest.py": (
            "import pytest\n"
            "from shop.api import handle\n"
            "@pytest.fixture\n"
            "def client():\n"
            "    return handle\n"
            "@pytest.fixture(autouse=True)\n"
            "def reset_state():\n"
            "    return None\n"
        ),
        "snapshot-copy/tests/test_api.py": (
            "def test_handle(client):\n"
            "    assert client() == 42\n"
        ),
    }

    graph = build_repository_graph(files)
    fixture_edge = next(
        edge for edge in graph.edges
        if edge.kind == "fixture_for" and edge.evidence == "client"
    )
    autouse_edge = next(
        edge for edge in graph.edges
        if edge.kind == "fixture_for" and edge.evidence == "pytest.fixture(autouse=True)"
    )
    assert fixture_edge.source == "snapshot-copy/tests/conftest.py::client"
    assert fixture_edge.target == "test::snapshot-copy/tests/test_api.py::test_handle"
    assert autouse_edge.target == fixture_edge.target

    report = analyze_repository(files, ["snapshot-copy/shop/domain.py"])
    assert "snapshot-copy/tests/test_api.py" in report["predicted_impact"]["tests"]


def test_dynamic_api_route_path_is_a_limitation_not_a_guessed_endpoint():
    graph = build_repository_graph({
        "app/routes.py": (
            "from fastapi import APIRouter\n"
            "PREFIX = '/items'\n"
            "router = APIRouter(prefix=PREFIX)\n"
            "@router.get('/search')\n"
            "def search():\n"
            "    return []\n"
        ),
    })

    assert len(graph.api_endpoints) == 1
    assert graph.api_endpoints[0].path is None
    assert any(item.kind == "dynamic_api_route" for item in graph.limitations)


def test_route_like_decorator_without_fastapi_binding_is_not_reported_as_an_endpoint():
    graph = build_repository_graph({
        "app/routes.py": (
            "router = CustomRouter()\n"
            "@router.get('/items')\n"
            "def list_items():\n"
            "    return []\n"
        ),
    })

    assert graph.api_endpoints == ()
    assert any(item.kind == "unverified_api_route_decorator" for item in graph.limitations)


def test_reassigned_router_binding_is_not_reported_as_a_fastapi_endpoint():
    graph = build_repository_graph({
        "app/routes.py": (
            "from fastapi import APIRouter\n"
            "router = APIRouter(prefix='/items')\n"
            "router = CustomRouter()\n"
            "@router.get('')\n"
            "def list_items():\n"
            "    return []\n"
        ),
    })

    assert graph.api_endpoints == ()
    assert any(item.kind == "unverified_api_route_decorator" for item in graph.limitations)


def test_aliased_fastapi_imports_still_identify_router_and_app_routes():
    graph = build_repository_graph({
        "app/routes.py": (
            "import fastapi as fa\n"
            "from fastapi import APIRouter as Router\n"
            "router = Router(prefix='/items')\n"
            "app = fa.FastAPI()\n"
            "@router.get('')\n"
            "def list_items():\n"
            "    return []\n"
            "@app.get('/health')\n"
            "def health():\n"
            "    return {'ok': True}\n"
        ),
    })

    assert {(item.method, item.path) for item in graph.api_endpoints} == {
        ("GET", "/items"),
        ("GET", "/health"),
    }


def test_rebound_import_and_instance_receivers_do_not_create_false_call_edges():
    graph = build_repository_graph({
        "app/target.py": "def complete():\n    return True\n",
        "app/client.py": (
            "from app.target import complete\n"
            "complete = resolve_runtime_callback()\n"
            "def invoke():\n"
            "    return complete()\n"
            "class Service:\n"
            "    def run(self):\n"
            "        self = resolve_runtime_service()\n"
            "        return self.run()\n"
        ),
    })

    assert not any(
        edge.kind == "calls"
        and edge.target == "app/target.py::complete"
        for edge in graph.edges
    )
    assert any(
        item.kind == "unresolved_internal_call"
        and item.evidence == "complete()"
        for item in graph.limitations
    )
    assert not any(
        edge.kind == "calls"
        and edge.source == "app/client.py::Service.run"
        and edge.target == "app/client.py::Service.run"
        for edge in graph.edges
    )
