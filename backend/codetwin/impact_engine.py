"""Deterministic impact prediction over a repository analysis graph."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from typing import Any

from codetwin.analysis_models import (
    APIEndpoint,
    Class,
    DependencyEdge,
    File,
    Function,
    Module,
    RepositoryGraph,
    Test,
)


PREDICTED_IMPACT = "PREDICTED IMPACT"


class InvalidImpactRequest(ValueError):
    """Raised when a proposed change does not identify a graph component."""


@dataclass(frozen=True)
class ProposedChange:
    """Structured identity for the component changed by a developer."""

    component_kind: str
    component_id: str
    description: str = ""


@dataclass(frozen=True)
class ImpactPathStep:
    source_id: str
    target_id: str
    relationship: str
    reason: str
    evidence: str
    line: int | None = None
    label: str = PREDICTED_IMPACT


@dataclass(frozen=True)
class DependencyPath:
    label: str
    source_id: str
    target_id: str
    node_ids: tuple[str, ...]
    steps: tuple[ImpactPathStep, ...]


@dataclass(frozen=True)
class ImpactedComponent:
    label: str
    component_kind: str
    component_id: str
    reasons: tuple[str, ...]
    dependency_path: DependencyPath


@dataclass(frozen=True)
class RiskIndicator:
    label: str
    code: str
    severity: str
    detail: str
    file_id: str | None = None
    evidence: str | None = None


@dataclass(frozen=True)
class ImpactPrediction:
    label: str
    proposed_change: ProposedChange
    affected_files: tuple[ImpactedComponent, ...]
    affected_modules: tuple[ImpactedComponent, ...]
    affected_functions: tuple[ImpactedComponent, ...]
    affected_classes: tuple[ImpactedComponent, ...]
    affected_apis: tuple[ImpactedComponent, ...]
    affected_tests: tuple[ImpactedComponent, ...]
    dependency_paths: tuple[DependencyPath, ...]
    risk_indicators: tuple[RiskIndicator, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible prediction with labels on every result."""
        return asdict(self)


@dataclass(frozen=True)
class _Node:
    kind: str
    component: File | Module | Function | Class | APIEndpoint | Test
    file_id: str


@dataclass(frozen=True)
class _Traversal:
    target_id: str
    edge: DependencyEdge
    relationship: str
    reason: str


@dataclass(frozen=True)
class _Route:
    node_ids: tuple[str, ...]
    steps: tuple[ImpactPathStep, ...]


_KIND_ORDER = {
    "file": 0,
    "module": 1,
    "function": 2,
    "class": 3,
    "api_endpoint": 4,
    "test": 5,
}


def _node_index(graph: RepositoryGraph) -> dict[str, _Node]:
    result: dict[str, _Node] = {}
    records: tuple[tuple[str, tuple[Any, ...]], ...] = (
        ("file", graph.files),
        ("module", graph.modules),
        ("function", graph.functions),
        ("class", graph.classes),
        ("api_endpoint", graph.api_endpoints),
        ("test", graph.tests),
    )
    for kind, components in records:
        for component in components:
            file_id = component.path if kind == "file" else component.file_id
            if component.id in result:
                raise InvalidImpactRequest(f"Graph contains duplicate component id: {component.id}")
            result[component.id] = _Node(kind, component, file_id)
    return result


def _adjacency(graph: RepositoryGraph) -> dict[str, tuple[_Traversal, ...]]:
    neighbors: dict[str, list[_Traversal]] = defaultdict(list)

    def add(
        source_id: str,
        target_id: str,
        edge: DependencyEdge,
        relationship: str,
        reason: str,
    ) -> None:
        neighbors[source_id].append(_Traversal(target_id, edge, relationship, reason))

    for edge in graph.edges:
        if edge.kind == "imports":
            add(
                edge.target,
                edge.source,
                edge,
                "imported_by",
                f"This source imports the changed dependency. {edge.reason}",
            )
        elif edge.kind == "calls":
            add(
                edge.target,
                edge.source,
                edge,
                "called_by",
                f"This component calls the changed function. {edge.reason}",
            )
            add(
                edge.source,
                edge.target,
                edge,
                "calls_dependency",
                f"This affected function calls the downstream component. {edge.reason}",
            )
        elif edge.kind in {"instantiates", "inherits"}:
            relationship = {
                "instantiates": "instantiated_by",
                "inherits": "subclass_of",
            }[edge.kind]
            add(
                edge.target,
                edge.source,
                edge,
                relationship,
                f"This component depends on the changed target through {edge.kind}. {edge.reason}",
            )
        elif edge.kind == "handled_by":
            add(
                edge.target,
                edge.source,
                edge,
                "exposed_by_api",
                f"This API endpoint is handled by the affected function. {edge.reason}",
            )
            add(
                edge.source,
                edge.target,
                edge,
                "handled_by",
                f"This API change is connected to its handler. {edge.reason}",
            )
        elif edge.kind == "fixture_for":
            add(
                edge.source,
                edge.target,
                edge,
                "fixture_for",
                edge.reason,
            )
        elif edge.kind in {
            "defines_module",
            "defines_function",
            "defines_class",
            "defines_fixture",
            "contains_test",
            "defines_method",
        }:
            add(
                edge.source,
                edge.target,
                edge,
                edge.kind,
                edge.reason,
            )
            add(
                edge.target,
                edge.source,
                edge,
                {
                    "defines_method": "member_of_class",
                    "contains_test": "test_in_file",
                }.get(edge.kind, "declared_in"),
                edge.reason,
            )
        elif edge.kind == "classified_as_test":
            add(edge.source, edge.target, edge, edge.kind, edge.reason)

    return {
        component_id: tuple(sorted(
            items,
            key=lambda item: (
                item.target_id,
                item.relationship,
                item.edge.kind,
                item.edge.line or 0,
                item.edge.evidence,
            ),
        ))
        for component_id, items in neighbors.items()
    }


def predict_impact(graph: RepositoryGraph, change: ProposedChange) -> ImpactPrediction:
    """Traverse statically evidenced relationships and return predicted impact.

    Dependencies are traversed from a changed dependency to its consumers. The
    returned paths preserve the original AST evidence and edge explanations.
    """
    nodes = _node_index(graph)
    changed = nodes.get(change.component_id)
    if changed is None:
        raise InvalidImpactRequest(f"Changed component is not present in the graph: {change.component_id}")
    if changed.kind != change.component_kind:
        raise InvalidImpactRequest(
            f"Component `{change.component_id}` has kind `{changed.kind}`, not `{change.component_kind}`"
        )

    root_route = _Route((change.component_id,), ())
    routes: dict[str, _Route] = {change.component_id: root_route}
    root_state = (change.component_id, None)
    state_routes: dict[tuple[str, str | None], _Route] = {root_state: root_route}
    queue = deque([root_state])
    if changed.kind != "file" and changed.file_id != change.component_id:
        association = ImpactPathStep(
            source_id=change.component_id,
            target_id=changed.file_id,
            relationship="declared_in",
            reason="The proposed change targets a component declared in this source file.",
            evidence=change.component_id,
            line=getattr(changed.component, "line", None),
        )
        file_route = _Route((change.component_id, changed.file_id), (association,))
        routes[changed.file_id] = file_route
        file_state = (changed.file_id, "upstream")
        state_routes[file_state] = file_route
        queue.append(file_state)

    adjacency = _adjacency(graph)
    terminal_nodes: set[str] = set()
    while queue:
        current_id, flow = queue.popleft()
        if current_id in terminal_nodes:
            continue
        for traversal in adjacency.get(current_id, ()):
            # A component-scoped change uses its containing file to find importers,
            # but does not imply that every sibling definition changed. A file-level
            # proposal does include the definitions contained in that file.
            if (
                current_id in nodes
                and nodes[current_id].kind == "file"
                and current_id != change.component_id
                and traversal.edge.kind in {
                    "defines_module",
                    "defines_function",
                    "defines_class",
                    "contains_test",
                }
            ):
                continue
            if (
                traversal.edge.kind == "defines_method"
                and traversal.relationship == "defines_method"
                and not (
                    (changed.kind == "class" and current_id == change.component_id)
                    or (
                        changed.kind == "file"
                        and current_id in nodes
                        and nodes[current_id].kind == "class"
                        and nodes[current_id].file_id == change.component_id
                    )
                )
            ):
                continue

            next_flow = flow
            if traversal.edge.kind == "calls":
                if flow is None:
                    next_flow = "upstream" if traversal.relationship == "called_by" else "downstream"
                elif flow == "upstream" and traversal.relationship != "called_by":
                    continue
                elif flow == "downstream" and traversal.relationship != "calls_dependency":
                    continue
            elif flow == "downstream" and traversal.relationship in {
                "imported_by", "instantiated_by", "subclass_of",
            }:
                # A downstream dependency's importers or class constructors are
                # not consumers of the proposed behavior change. Call edges from
                # the changed code provide the relevant downstream path.
                continue
            elif flow is None:
                if traversal.relationship in {
                    "imported_by", "instantiated_by", "subclass_of", "exposed_by_api",
                    "member_of_class", "declared_in", "test_in_file",
                }:
                    next_flow = "upstream"
                elif traversal.relationship in {
                    "defines_module", "defines_function", "defines_class", "defines_method",
                    "handled_by", "fixture_for", "classified_as_test",
                }:
                    next_flow = "downstream"

            next_state = (traversal.target_id, next_flow)
            if next_state in state_routes:
                continue
            previous = state_routes[(current_id, flow)]
            step = ImpactPathStep(
                source_id=current_id,
                target_id=traversal.target_id,
                relationship=traversal.relationship,
                reason=traversal.reason,
                evidence=traversal.edge.evidence,
                line=traversal.edge.line,
            )
            candidate = _Route(
                (*previous.node_ids, traversal.target_id),
                (*previous.steps, step),
            )
            state_routes[next_state] = candidate
            existing = routes.get(traversal.target_id)
            if existing is None or (len(candidate.steps), candidate.node_ids) < (
                len(existing.steps), existing.node_ids
            ):
                routes[traversal.target_id] = candidate
            if traversal.relationship == "member_of_class":
                # Keep the owning class visible in the prediction, but do not
                # fan out from it to every method caller that merely constructs
                # the same class. Method callers are reached through exact call
                # edges instead.
                terminal_nodes.add(traversal.target_id)
            elif traversal.relationship == "declared_in":
                # Include the source file as a result, but do not walk from an
                # affected implementation file into every module that imports it.
                terminal_nodes.add(traversal.target_id)
            queue.append(next_state)

    # A component is associated with its containing file by the typed model. Extend
    # its path so file-level results retain the dependency chain that reached it.
    for component_id in sorted(tuple(routes)):
        node = nodes.get(component_id)
        if node is None or node.kind == "file" or node.file_id not in nodes:
            continue
        step = ImpactPathStep(
            source_id=component_id,
            target_id=node.file_id,
            relationship="declared_in",
            reason="The affected component is declared in this source file.",
            evidence=component_id,
        )
        previous = routes[component_id]
        candidate = _Route((*previous.node_ids, node.file_id), (*previous.steps, step))
        existing = routes.get(node.file_id)
        if existing is None or (len(candidate.steps), candidate.node_ids) < (
            len(existing.steps), existing.node_ids
        ):
            routes[node.file_id] = candidate

    affected_file_paths = {
        component.file_id
        for component_id in routes
        if (component := nodes.get(component_id)) is not None
    }

    # Module nodes are useful impact results even when traversal reached their file
    # through an import edge rather than through a file-level proposal.
    modules_by_file: dict[str, list[Module]] = defaultdict(list)
    for module in graph.modules:
        modules_by_file[module.file_id].append(module)
    for file_path in sorted(affected_file_paths):
        file_route = routes.get(file_path)
        if file_route is None:
            continue
        for module in sorted(modules_by_file.get(file_path, ()), key=lambda item: item.id):
            if module.id not in routes:
                step = ImpactPathStep(
                    source_id=file_path,
                    target_id=module.id,
                    relationship="defines_module",
                    reason="This file provides the affected Python module.",
                    evidence=module.name,
                )
                routes[module.id] = _Route(
                    (*file_route.node_ids, module.id),
                    (*file_route.steps, step),
                )

    def path_for(component_id: str) -> DependencyPath:
        route = routes[component_id]
        return DependencyPath(
            label=PREDICTED_IMPACT,
            source_id=change.component_id,
            target_id=component_id,
            node_ids=route.node_ids,
            steps=route.steps,
        )

    def item_for(component_id: str, node: _Node) -> ImpactedComponent:
        route = path_for(component_id)
        reasons = tuple(
            f"{step.relationship}: {step.reason} Evidence: {step.evidence}"
            for step in route.steps
        )
        if not reasons:
            reasons = ("The proposed change directly targets this component.",)
        return ImpactedComponent(
            label=PREDICTED_IMPACT,
            component_kind=node.kind,
            component_id=component_id,
            reasons=reasons,
            dependency_path=route,
        )

    results_by_kind: dict[str, list[ImpactedComponent]] = defaultdict(list)
    dependency_paths: dict[str, DependencyPath] = {}
    for component_id in sorted(routes, key=lambda value: (
        _KIND_ORDER.get(nodes[value].kind, 99) if value in nodes else 99,
        value,
    )):
        node = nodes.get(component_id)
        if node is None:
            continue
        result = item_for(component_id, node)
        results_by_kind[node.kind].append(result)
        dependency_paths[component_id] = result.dependency_path

    file_results: list[ImpactedComponent] = []
    for path in sorted(affected_file_paths):
        node = nodes.get(path)
        if node is None or node.kind != "file":
            continue
        file_results.append(item_for(path, node))
        dependency_paths[path] = file_results[-1].dependency_path

    risks: list[RiskIndicator] = []
    affected_set = set(affected_file_paths)
    for limitation in graph.limitations:
        if limitation.file_id not in affected_set:
            continue
        severity = "high" if limitation.kind == "syntax_error" else "medium"
        risks.append(RiskIndicator(
            label=PREDICTED_IMPACT,
            code=limitation.kind,
            severity=severity,
            detail=limitation.detail,
            file_id=limitation.file_id,
            evidence=limitation.evidence,
        ))
    if not results_by_kind["test"]:
        risks.append(RiskIndicator(
            label=PREDICTED_IMPACT,
            code="no_affected_tests_found",
            severity="medium",
            detail="Static dependency traversal did not find a related test; this is not evidence that no regression exists.",
            file_id=changed.file_id,
        ))

    return ImpactPrediction(
        label=PREDICTED_IMPACT,
        proposed_change=change,
        affected_files=tuple(file_results),
        affected_modules=tuple(results_by_kind["module"]),
        affected_functions=tuple(results_by_kind["function"]),
        affected_classes=tuple(results_by_kind["class"]),
        affected_apis=tuple(results_by_kind["api_endpoint"]),
        affected_tests=tuple(results_by_kind["test"]),
        dependency_paths=tuple(dependency_paths[key] for key in sorted(dependency_paths)),
        risk_indicators=tuple(sorted(risks, key=lambda item: (
            item.file_id or "", item.code, item.evidence or "", item.detail
        ))),
    )


__all__ = [
    "PREDICTED_IMPACT",
    "DependencyPath",
    "ImpactPathStep",
    "ImpactPrediction",
    "ImpactedComponent",
    "InvalidImpactRequest",
    "ProposedChange",
    "RiskIndicator",
    "predict_impact",
]
