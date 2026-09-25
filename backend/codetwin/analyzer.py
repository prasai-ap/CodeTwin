"""Deterministic, import-based Python impact analysis."""

from __future__ import annotations

import ast
import posixpath
import re
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from pathlib import PurePosixPath


class InvalidAnalysisRequest(ValueError):
    """Raised when a requested change cannot be matched to a Python file."""


@dataclass(frozen=True, order=True)
class Dependency:
    """An importer depends on an imported repository file."""

    source: str
    target: str


@dataclass(frozen=True)
class ParseError:
    file: str
    message: str


def _normalize_path(path: str) -> str:
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
    parts = module.split(".") if module else []
    if PurePosixPath(path).name == "__init__.py":
        return parts
    return parts[:-1]


def _resolve_relative_module(path: str, node: ast.ImportFrom) -> str | None:
    package = _package_for_file(path)
    if node.level == 0:
        return node.module
    # level 1 stays in the current package; each additional dot climbs one level.
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
                # ``from package import module`` can refer to a sibling module.
                possible_module = f"{base}.{alias.name}" if base else alias.name
                target = module_to_path.get(possible_module)
                if target:
                    dependencies.add(target)
    dependencies.discard(path)
    return dependencies


def _is_api_file(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
                    if decorator.func.attr.lower() in {
                        "get", "post", "put", "patch", "delete", "options", "head", "websocket"
                    }:
                        return True
        if isinstance(node, ast.Call):
            called = node.func
            if isinstance(called, ast.Name):
                name = called.id
            elif isinstance(called, ast.Attribute):
                name = called.attr
            else:
                name = ""
            if name in {"FastAPI", "APIRouter"}:
                return True
    return False


def _file_kind(path: str, tree: ast.Module | None) -> str:
    parts = PurePosixPath(path).parts
    filename = PurePosixPath(path).name
    if "tests" in parts or filename.startswith("test_") or filename.endswith("_test.py"):
        return "test"
    if tree is not None and _is_api_file(tree):
        return "api"
    return "source"


def _component(path: str) -> str:
    parts = PurePosixPath(path).parts
    if len(parts) > 1 and parts[0] in {"src", "app", "backend"}:
        component = parts[1]
    else:
        component = parts[0] if len(parts) > 1 else "root"
    return component.removesuffix(".py")


def analyze_repository(files: dict[str, str], changed_files: list[str]) -> dict[str, object]:
    """Return a stable impact report for a mapping of repository paths to source text.

    Imports point from importer to dependency. Impact travels in the reverse direction,
    from a changed dependency to the files that import it, including transitive imports.
    """
    normalized_files: dict[str, str] = {}
    for original_path, content in files.items():
        path = _normalize_path(original_path)
        if path in normalized_files:
            raise InvalidAnalysisRequest(f"Duplicate normalized repository path: {path}")
        normalized_files[path] = content

    normalized_changes = sorted({_normalize_path(path) for path in changed_files})
    if not normalized_changes:
        raise InvalidAnalysisRequest("At least one changed file is required")
    missing = [path for path in normalized_changes if path not in normalized_files]
    if missing:
        missing_paths = ", ".join(missing)
        raise InvalidAnalysisRequest(f"Changed files are missing from the repository snapshot: {missing_paths}")
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
    parse_errors: list[ParseError] = []
    for path in sorted(source_files):
        try:
            trees[path] = ast.parse(source_files[path], filename=path)
        except SyntaxError as error:
            parse_errors.append(ParseError(path, f"line {error.lineno}: {error.msg}"))

    dependencies: set[Dependency] = set()
    reverse_dependencies: dict[str, set[str]] = defaultdict(set)
    for path, tree in trees.items():
        for target in _imports(path, tree, module_to_path):
            dependencies.add(Dependency(source=path, target=target))
            reverse_dependencies[target].add(path)

    impacted = set(normalized_changes)
    queue = deque(normalized_changes)
    while queue:
        changed = queue.popleft()
        for dependent in sorted(reverse_dependencies.get(changed, ())):
            if dependent not in impacted:
                impacted.add(dependent)
                queue.append(dependent)

    predicted = sorted(impacted)
    tests = [path for path in predicted if _file_kind(path, trees.get(path)) == "test"]
    apis = [path for path in predicted if _file_kind(path, trees.get(path)) == "api"]
    components = sorted({_component(path) for path in predicted})
    not_affected = sorted(set(source_files) - impacted)

    return {
        "changed_files": normalized_changes,
        "predicted_impact": {
            "files": predicted,
            "tests": tests,
            "api_files": apis,
            "components": components,
        },
        "not_affected": not_affected,
        "dependency_edges": [asdict(edge) for edge in sorted(dependencies)],
        "parse_errors": [asdict(error) for error in parse_errors],
    }
