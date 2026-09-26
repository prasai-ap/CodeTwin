"""Typed nodes and evidence edges for deterministic repository analysis."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class File:
    id: str
    path: str
    language: str
    is_test_file: bool
    parse_status: str
    parse_error: str | None = None


@dataclass(frozen=True)
class Module:
    id: str
    name: str
    file_id: str
    is_package: bool


@dataclass(frozen=True)
class Function:
    id: str
    file_id: str
    name: str
    qualname: str
    line: int
    end_line: int
    owner: str | None
    owner_class_id: str | None
    is_async: bool


@dataclass(frozen=True)
class Class:
    id: str
    file_id: str
    name: str
    qualname: str
    line: int
    end_line: int
    bases: tuple[str, ...]


@dataclass(frozen=True)
class APIEndpoint:
    id: str
    file_id: str
    method: str
    path: str | None
    handler_id: str
    handler_name: str
    decorator: str
    line: int


@dataclass(frozen=True)
class Test:
    __test__ = False

    id: str
    file_id: str
    function_id: str
    name: str
    line: int
    discovery: str


@dataclass(frozen=True)
class DependencyEdge:
    source: str
    target: str
    kind: str
    reason: str
    evidence: str
    line: int | None = None


@dataclass(frozen=True)
class AnalysisLimitation:
    file_id: str
    kind: str
    detail: str
    line: int | None = None
    evidence: str | None = None


@dataclass(frozen=True)
class RepositoryGraph:
    files: tuple[File, ...]
    modules: tuple[Module, ...]
    functions: tuple[Function, ...]
    classes: tuple[Class, ...]
    api_endpoints: tuple[APIEndpoint, ...]
    tests: tuple[Test, ...]
    edges: tuple[DependencyEdge, ...]
    limitations: tuple[AnalysisLimitation, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation for internal consumers."""
        return asdict(self)
