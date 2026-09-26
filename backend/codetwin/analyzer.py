"""Deterministic repository impact analysis built on an evidence graph."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import asdict
from pathlib import PurePosixPath
from typing import Mapping

from codetwin.analysis_models import (
    APIEndpoint,
    AnalysisLimitation,
    Class,
    DependencyEdge,
    File,
    Function,
    Module,
    RepositoryGraph,
    Test,
)
from codetwin.repository_graph import InvalidAnalysisRequest, build_repository_graph, normalize_path


def _component(path: str) -> str:
    parts = PurePosixPath(path).parts
    if len(parts) > 1 and parts[0] in {"src", "app", "backend"}:
        return parts[1]
    return parts[0] if len(parts) > 1 else "root"


def _edge_result(edge: DependencyEdge) -> dict[str, object]:
    return asdict(edge)


def analyze_repository(files: Mapping[str, str], changed_files: list[str]) -> dict[str, object]:
    """Return deterministic predicted impact and the evidence behind its graph edges.

    ``build_repository_graph`` is the structured internal interface for later impact
    engine consumers. This compatibility report presents the graph's impacted slice
    in the shape used by CodeTwin's existing API.
    """
    normalized_changes = sorted({normalize_path(path) for path in changed_files})
    if not normalized_changes:
        raise InvalidAnalysisRequest("At least one changed file is required")
    non_python = [path for path in normalized_changes if PurePosixPath(path).suffix != ".py"]
    if non_python:
        raise InvalidAnalysisRequest(f"Changed files must be Python source files: {', '.join(non_python)}")

    graph = build_repository_graph(files)
    files_by_path = {item.path: item for item in graph.files}
    missing = sorted(path for path in normalized_changes if path not in files_by_path)
    if missing:
        raise InvalidAnalysisRequest(f"Changed files are missing from the snapshot: {', '.join(missing)}")

    python_files = {item.path for item in graph.files if item.language == "python"}
    functions = {item.id: item for item in graph.functions}
    classes = {item.id: item for item in graph.classes}
    tests_by_id = {item.id: item for item in graph.tests}
    symbol_to_file = {
        **{identifier: item.file_id for identifier, item in functions.items()},
        **{identifier: item.file_id for identifier, item in classes.items()},
        **{identifier: item.file_id for identifier, item in tests_by_id.items()},
        **{item.id: item.file_id for item in graph.modules},
    }
    symbols_by_file: dict[str, set[str]] = defaultdict(set)
    for identifier, file_path in symbol_to_file.items():
        symbols_by_file[file_path].add(identifier)

    symbol_neighbors: dict[str, set[str]] = defaultdict(set)
    importers: dict[str, set[str]] = defaultdict(set)
    for edge in graph.edges:
        if edge.kind in {"calls", "instantiates", "inherits"}:
            symbol_neighbors[edge.source].add(edge.target)
            symbol_neighbors[edge.target].add(edge.source)
        elif edge.kind == "imports":
            importers[edge.target].add(edge.source)

    impacted_files = set(normalized_changes)
    impacted_symbols = {
        identifier for identifier, file_path in symbol_to_file.items()
        if file_path in impacted_files
    }
    symbol_queue = deque(sorted(impacted_symbols))
    while symbol_queue:
        current = symbol_queue.popleft()
        for related in sorted(symbol_neighbors.get(current, ())):
            if related not in impacted_symbols:
                impacted_symbols.add(related)
                symbol_queue.append(related)
                related_file = symbol_to_file.get(related)
                if related_file:
                    impacted_files.add(related_file)

    fixture_function_ids = {
        edge.target for edge in graph.edges if edge.kind == "defines_fixture"
    }
    fixture_neighbors: dict[str, set[str]] = defaultdict(set)
    for edge in graph.edges:
        if edge.kind == "fixture_for":
            fixture_neighbors[edge.source].add(edge.target)

    pending_files = deque(sorted(impacted_files))
    processed_files: set[str] = set()
    while pending_files:
        dependency = pending_files.popleft()
        if dependency in processed_files:
            continue
        processed_files.add(dependency)

        for importer in sorted(importers.get(dependency, ())):
            if importer not in impacted_files:
                impacted_files.add(importer)
                pending_files.append(importer)

        fixture_queue = deque(sorted(
            symbols_by_file.get(dependency, set()) & fixture_function_ids
        ))
        visited_fixtures: set[str] = set()
        while fixture_queue:
            fixture_id = fixture_queue.popleft()
            if fixture_id in visited_fixtures:
                continue
            visited_fixtures.add(fixture_id)
            for consumer_id in sorted(fixture_neighbors.get(fixture_id, ())):
                if consumer_id in fixture_function_ids:
                    fixture_queue.append(consumer_id)
                consumer_file = symbol_to_file.get(consumer_id)
                if consumer_file and consumer_file not in impacted_files:
                    impacted_files.add(consumer_file)
                    pending_files.append(consumer_file)

    predicted_files = sorted(impacted_files)
    tests = [path for path in predicted_files if files_by_path[path].is_test_file]
    route_nodes = [
        endpoint for endpoint in graph.api_endpoints
        if endpoint.file_id in impacted_files and endpoint.path is not None
    ]
    route_nodes.sort(key=lambda item: (item.file_id, item.method, item.path or "", item.handler_name))
    api_routes = [
        {
            "file": endpoint.file_id,
            "method": endpoint.method,
            "path": endpoint.path,
            "handler": endpoint.handler_name,
        }
        for endpoint in route_nodes
    ]
    api_files = sorted({endpoint.file_id for endpoint in route_nodes})
    if not api_files:
        api_files = [path for path in predicted_files if "/routes/" in f"/{path}/"]

    function_results = [
        {
            "file": item.file_id,
            "qualname": item.qualname,
            "line": item.line,
            "owner": item.owner,
            "id": item.id,
        }
        for identifier, item in sorted(functions.items())
        if identifier in impacted_symbols
    ]
    class_results = [
        {
            "file": item.file_id,
            "qualname": item.qualname,
            "line": item.line,
            "id": item.id,
        }
        for item in graph.classes
        if item.file_id in impacted_files
    ]
    dependency_edges = [
        _edge_result(edge) for edge in graph.edges if edge.kind == "imports"
    ]
    function_edges = [
        _edge_result(edge)
        for edge in graph.edges
        if edge.kind == "calls" and edge.source in functions
    ]
    parse_errors = [
        {"file": item.path, "message": item.parse_error}
        for item in graph.files
        if item.parse_status == "syntax_error"
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
        "not_affected": sorted(python_files - impacted_files),
        "dependency_edges": dependency_edges,
        "function_edges": function_edges,
        "parse_errors": parse_errors,
        "analysis_limitations": [asdict(item) for item in graph.limitations],
    }


__all__ = [
    "APIEndpoint",
    "AnalysisLimitation",
    "Class",
    "DependencyEdge",
    "File",
    "Function",
    "InvalidAnalysisRequest",
    "Module",
    "RepositoryGraph",
    "Test",
    "analyze_repository",
    "build_repository_graph",
    "normalize_path",
]
