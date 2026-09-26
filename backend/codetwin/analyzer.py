"""Deterministic Python dependency and impact analysis using the standard AST."""

from __future__ import annotations

import ast
import posixpath
import re
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from pathlib import PurePosixPath


class InvalidAnalysisRequest(ValueError):
    """Raised when a proposed repository snapshot cannot be analyzed safely."""


@dataclass(frozen=True, order=True)
class FunctionInfo:
    file: str
    qualname: str
    line: int
    owner: str | None

    @property
    def node_id(self) -> str:
        return f"{self.file}::{self.qualname}"


@dataclass(frozen=True, order=True)
class ClassInfo:
    file: str
    qualname: str
    line: int

    @property
    def node_id(self) -> str:
        return f"{self.file}::{self.qualname}"


def normalize_path(path: str) -> str:
    normalized = posixpath.normpath(path.replace("\\", "/"))
    if (
        not path
        or PurePosixPath(normalized).is_absolute()
        or normalized == ".."
        or normalized.startswith("../")
        or re.match(r"^[A-Za-z]:", normalized)
    ):
        raise InvalidAnalysisRequest(f"Repository paths must be relative: {path!r}")
    return normalized


def _module_for_path(path: str) -> str | None:
    pure_path = PurePosixPath(path)
    if pure_path.suffix != ".py":
        return None
    parts = list(pure_path.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    if not parts or not all(part.isidentifier() for part in parts):
        return None
    return ".".join(parts)


def _package_for_file(path: str) -> list[str]:
    module = _module_for_path(path)
    if module is None:
        return []
    parts = module.split(".")
    return parts if PurePosixPath(path).name == "__init__.py" else parts[:-1]


def _resolve_relative_module(path: str, node: ast.ImportFrom) -> str | None:
    package = _package_for_file(path)
    if node.level == 0:
        return node.module
    keep = len(package) - node.level + 1
    if keep < 0:
        return None
    prefix = package[:keep]
    if node.module:
        prefix.extend(node.module.split("."))
    return ".".join(prefix)


def _imports(path: str, tree: ast.Module, module_to_path: dict[str, str]) -> set[str]:
    dependencies: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                target = module_to_path.get(alias.name)
                if target:
                    dependencies.add(target)
        elif isinstance(node, ast.ImportFrom):
            base = _resolve_relative_module(path, node)
            if base is None:
                continue
            if base in module_to_path:
                dependencies.add(module_to_path[base])
            for alias in node.names:
                target = module_to_path.get(f"{base}.{alias.name}" if base else alias.name)
                if target:
                    dependencies.add(target)
    dependencies.discard(path)
    return dependencies


def _collect_functions(path: str, tree: ast.Module) -> list[tuple[FunctionInfo, ast.FunctionDef | ast.AsyncFunctionDef]]:
    found: list[tuple[FunctionInfo, ast.FunctionDef | ast.AsyncFunctionDef]] = []

    def visit_body(body: list[ast.stmt], parent: tuple[str, ...] = (), owner: str | None = None) -> None:
        for node in body:
            if isinstance(node, ast.ClassDef):
                class_path = (*parent, node.name)
                for member in node.body:
                    if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        qualname = ".".join((*class_path, member.name))
                        found.append((FunctionInfo(path, qualname, member.lineno, node.name), member))
                        visit_body(member.body, (*class_path, member.name), None)
                    elif isinstance(member, ast.ClassDef):
                        visit_body([member], class_path, node.name)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qualname = ".".join((*parent, node.name))
                found.append((FunctionInfo(path, qualname, node.lineno, owner), node))
                visit_body(node.body, (*parent, node.name), None)

    visit_body(tree.body)
    return found


def _collect_classes(path: str, tree: ast.Module) -> list[ClassInfo]:
    class Collector(ast.NodeVisitor):
        def __init__(self) -> None:
            self.parents: list[str] = []
            self.found: list[ClassInfo] = []

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            class_path = (*self.parents, node.name)
            self.found.append(ClassInfo(path, ".".join(class_path), node.lineno))
            self.parents.append(node.name)
            self.generic_visit(node)
            self.parents.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self.parents.append(node.name)
            self.generic_visit(node)
            self.parents.pop()

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self.parents.append(node.name)
            self.generic_visit(node)
            self.parents.pop()

    collector = Collector()
    collector.visit(tree)
    return collector.found


def _import_bindings(
    path: str,
    tree: ast.Module,
    module_to_path: dict[str, str],
) -> tuple[dict[str, tuple[str, int]], dict[str, tuple[str, str]]]:
    modules: dict[str, tuple[str, int]] = {}
    symbols: dict[str, tuple[str, str]] = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".")[0]
                skipped = 0 if alias.asname else len(alias.name.split(".")) - 1
                modules[local] = (alias.name, skipped)
        elif isinstance(node, ast.ImportFrom):
            base = _resolve_relative_module(path, node)
            if base is None:
                continue
            for alias in node.names:
                local = alias.asname or alias.name
                submodule = f"{base}.{alias.name}" if base else alias.name
                if submodule in module_to_path:
                    modules[local] = (submodule, 0)
                elif base in module_to_path:
                    symbols[local] = (module_to_path[base], alias.name)
    return modules, symbols


class _CallCollector(ast.NodeVisitor):
    def __init__(self, root: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.root = root
        self.calls: list[ast.Call] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node is self.root:
            self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        if node is self.root:
            self.generic_visit(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        self.calls.append(node)
        self.generic_visit(node)


def _attribute_chain(node: ast.expr) -> list[str]:
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, ast.Attribute):
        return [*_attribute_chain(node.value), node.attr]
    return []


def _resolve_call(
    call: ast.Call,
    current: FunctionInfo,
    functions: dict[str, FunctionInfo],
    by_short_name: dict[str, list[FunctionInfo]],
    module_to_path: dict[str, str],
    module_bindings: dict[str, tuple[str, int]],
    symbol_bindings: dict[str, tuple[str, str]],
) -> FunctionInfo | None:
    called = call.func
    if isinstance(called, ast.Name):
        imported = symbol_bindings.get(called.id)
        if imported:
            return functions.get(f"{imported[0]}::{imported[1]}")
        same_file = [
            info for info in by_short_name.get(called.id, ())
            if info.file == current.file and info.owner is None
        ]
        return same_file[0] if len(same_file) == 1 else None

    chain = _attribute_chain(called)
    if not chain:
        return None
    method = chain[-1]
    if chain[0] == "self" and current.owner:
        local_method = functions.get(f"{current.file}::{current.owner}.{method}")
        if local_method:
            return local_method

    imported_symbol = symbol_bindings.get(chain[0])
    if imported_symbol and len(chain) > 1:
        imported_method = functions.get(f"{imported_symbol[0]}::{imported_symbol[1]}.{method}")
        if imported_method:
            return imported_method

    for prefix_length in range(len(chain), 0, -1):
        binding = module_bindings.get(".".join(chain[:prefix_length]))
        if binding is None:
            continue
        module_name, skipped = binding
        target_file = module_to_path.get(module_name)
        suffix = chain[prefix_length + skipped:]
        if target_file and suffix:
            imported_target = functions.get(f"{target_file}::{'.'.join(suffix)}")
            if imported_target:
                return imported_target

    matches = by_short_name.get(method, ())
    return matches[0] if len(matches) == 1 else None


def _router_prefixes(tree: ast.Module) -> dict[str, str]:
    prefixes: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if not isinstance(value, ast.Call):
            continue
        func_name = value.func.id if isinstance(value.func, ast.Name) else (
            value.func.attr if isinstance(value.func, ast.Attribute) else ""
        )
        if func_name != "APIRouter":
            continue
        target_nodes = node.targets if isinstance(node, ast.Assign) else [node.target]
        prefix = next(
            (
                keyword.value.value
                for keyword in value.keywords
                if keyword.arg == "prefix"
                and isinstance(keyword.value, ast.Constant)
                and isinstance(keyword.value.value, str)
            ),
            "",
        )
        for target in target_nodes:
            if isinstance(target, ast.Name):
                prefixes[target.id] = prefix.rstrip("/")
    return prefixes


def _api_routes(path: str, tree: ast.Module) -> list[dict[str, str]]:
    route_methods = {"get", "post", "put", "patch", "delete", "options", "head", "websocket"}
    prefixes = _router_prefixes(tree)
    routes: list[dict[str, str]] = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                continue
            method = decorator.func.attr.lower()
            if method not in route_methods:
                continue
            route_path = ""
            if decorator.args and isinstance(decorator.args[0], ast.Constant) and isinstance(decorator.args[0].value, str):
                route_path = decorator.args[0].value
            owner = decorator.func.value.id if isinstance(decorator.func.value, ast.Name) else ""
            prefix = prefixes.get(owner, "")
            routes.append({
                "file": path,
                "method": method.upper(),
                "path": f"{prefix}/{route_path.lstrip('/')}" if prefix else route_path,
                "handler": node.name,
            })
    return routes


def _is_test(path: str) -> bool:
    parts = PurePosixPath(path).parts
    name = PurePosixPath(path).name
    return "tests" in parts or name.startswith("test_") or name.endswith("_test.py")


def _component(path: str) -> str:
    parts = PurePosixPath(path).parts
    if len(parts) > 1 and parts[0] in {"src", "app", "backend"}:
        return parts[1]
    return parts[0] if len(parts) > 1 else "root"


def analyze_repository(files: dict[str, str], changed_files: list[str]) -> dict[str, object]:
    """Analyze a source snapshot and return stable file and function impact evidence."""
    normalized_files: dict[str, str] = {}
    for original_path, content in files.items():
        path = normalize_path(original_path)
        if path in normalized_files:
            raise InvalidAnalysisRequest(f"Duplicate normalized repository path: {path}")
        if not isinstance(content, str):
            raise InvalidAnalysisRequest(f"Source content must be text: {path}")
        normalized_files[path] = content

    normalized_changes = sorted({normalize_path(path) for path in changed_files})
    if not normalized_changes:
        raise InvalidAnalysisRequest("At least one changed file is required")
    missing = sorted(path for path in normalized_changes if path not in normalized_files)
    if missing:
        raise InvalidAnalysisRequest(f"Changed files are missing from the snapshot: {', '.join(missing)}")
    non_python = [path for path in normalized_changes if PurePosixPath(path).suffix != ".py"]
    if non_python:
        raise InvalidAnalysisRequest(f"Changed files must be Python source files: {', '.join(non_python)}")

    source_files = {
        path: text for path, text in normalized_files.items()
        if PurePosixPath(path).suffix == ".py"
    }
    module_to_path: dict[str, str] = {}
    for path in sorted(source_files):
        module = _module_for_path(path)
        if module:
            module_to_path.setdefault(module, path)

    trees: dict[str, ast.Module] = {}
    parse_errors: list[dict[str, object]] = []
    for path in sorted(source_files):
        try:
            trees[path] = ast.parse(source_files[path], filename=path)
        except SyntaxError as error:
            parse_errors.append({"file": path, "message": f"line {error.lineno}: {error.msg}"})

    dependencies: set[tuple[str, str]] = set()
    reverse_dependencies: dict[str, set[str]] = defaultdict(set)
    for path, tree in trees.items():
        for dependency in _imports(path, tree, module_to_path):
            dependencies.add((path, dependency))
            reverse_dependencies[dependency].add(path)

    function_infos: dict[str, FunctionInfo] = {}
    function_nodes: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    functions_by_file: dict[str, list[FunctionInfo]] = defaultdict(list)
    functions_by_short_name: dict[str, list[FunctionInfo]] = defaultdict(list)
    classes_by_file: dict[str, list[ClassInfo]] = defaultdict(list)
    for path, tree in trees.items():
        for info, node in _collect_functions(path, tree):
            function_infos[info.node_id] = info
            function_nodes[info.node_id] = node
            functions_by_file[path].append(info)
            functions_by_short_name[node.name].append(info)
        classes_by_file[path].extend(_collect_classes(path, tree))

    call_edges: set[tuple[str, str]] = set()
    callers: dict[str, set[str]] = defaultdict(set)
    callees: dict[str, set[str]] = defaultdict(set)
    for path, tree in trees.items():
        module_bindings, symbol_bindings = _import_bindings(path, tree, module_to_path)
        for info in functions_by_file.get(path, ()):
            visitor = _CallCollector(function_nodes[info.node_id])
            visitor.visit(function_nodes[info.node_id])
            for call in visitor.calls:
                target = _resolve_call(
                    call, info, function_infos, functions_by_short_name, module_to_path,
                    module_bindings, symbol_bindings,
                )
                if target and target.node_id != info.node_id:
                    edge = (info.node_id, target.node_id)
                    call_edges.add(edge)
                    callees[info.node_id].add(target.node_id)
                    callers[target.node_id].add(info.node_id)

    impacted_files = set(normalized_changes)
    impacted_functions = {
        info.node_id for path in normalized_changes for info in functions_by_file.get(path, ())
    }
    queue = deque(sorted(impacted_functions))
    while queue:
        current = queue.popleft()
        info = function_infos[current]
        impacted_files.add(info.file)
        related = callers.get(current, set()) | callees.get(current, set())
        for related_id in sorted(related):
            if related_id not in impacted_functions:
                impacted_functions.add(related_id)
                queue.append(related_id)

    pending_files = deque(sorted(impacted_files))
    while pending_files:
        dependency = pending_files.popleft()
        for importer in sorted(reverse_dependencies.get(dependency, ())):
            if importer not in impacted_files:
                impacted_files.add(importer)
                pending_files.append(importer)

    predicted_files = sorted(impacted_files)
    tests = [path for path in predicted_files if _is_test(path)]
    api_routes = sorted(
        (route for path, tree in trees.items() for route in _api_routes(path, tree)
         if path in impacted_files),
        key=lambda route: (route["file"], route["method"], route["path"], route["handler"]),
    )
    api_files = sorted({route["file"] for route in api_routes})
    if not api_files:
        api_files = [path for path in predicted_files if "/routes/" in f"/{path}/"]
    function_results = [
        asdict(function_infos[node_id]) | {"id": node_id}
        for node_id in sorted(impacted_functions)
    ]
    class_results = [
        asdict(info) | {"id": info.node_id}
        for path in sorted(impacted_files)
        for info in sorted(classes_by_file.get(path, ()))
    ]
    return {
        "changed_files": normalized_changes,
        "predicted_impact": {
            "files": predicted_files,
            "functions": function_results,
            "classes": class_results,
            "tests": tests,
            "api_files": api_files,
            "api_routes": api_routes,
            "components": sorted({_component(path) for path in predicted_files}),
        },
        "not_affected": sorted(set(source_files) - impacted_files),
        "dependency_edges": [
            {"source": source, "target": target, "kind": "imports"}
            for source, target in sorted(dependencies)
        ],
        "function_edges": [
            {"source": source, "target": target, "kind": "calls"}
            for source, target in sorted(call_edges)
        ],
        "parse_errors": parse_errors,
    }
