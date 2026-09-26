"""Build an evidence-based Python repository graph with the standard AST."""

from __future__ import annotations

import ast
import posixpath
import re
from collections import defaultdict
from pathlib import PurePosixPath
from typing import Iterable, Mapping

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


class InvalidAnalysisRequest(ValueError):
    """Raised when a proposed repository snapshot cannot be analyzed safely."""


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
    if keep < 1:
        return None
    prefix = package[:keep]
    if node.module:
        prefix.extend(node.module.split("."))
    return ".".join(prefix)


def _is_test_file(path: str) -> bool:
    parts = PurePosixPath(path).parts
    name = PurePosixPath(path).name
    return "tests" in parts or name.startswith("test_") or name.endswith("_test.py")


def _source_line(source: str, line: int) -> str:
    lines = source.splitlines()
    return lines[line - 1].strip() if 0 < line <= len(lines) else ""


def _language_for_path(path: str) -> str:
    suffix = PurePosixPath(path).suffix.lower()
    if suffix == ".py":
        return "python"
    if suffix == ".md":
        return "markdown"
    if suffix in {".txt", ".log"}:
        return "text"
    return suffix.lstrip(".") or "text"


def _id(path: str, qualname: str) -> str:
    return f"{path}::{qualname}"


def _collect_definitions(
    path: str,
    tree: ast.Module,
) -> tuple[
    list[tuple[Function, ast.FunctionDef | ast.AsyncFunctionDef]],
    list[tuple[Class, ast.ClassDef]],
]:
    class Collector(ast.NodeVisitor):
        def __init__(self) -> None:
            self.parents: list[str] = []
            self.owner_class_id: str | None = None
            self.functions: list[tuple[Function, ast.FunctionDef | ast.AsyncFunctionDef]] = []
            self.classes: list[tuple[Class, ast.ClassDef]] = []

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            qualname = ".".join((*self.parents, node.name))
            class_id = _id(path, qualname)
            self.classes.append((
                Class(
                    id=class_id,
                    file_id=path,
                    name=node.name,
                    qualname=qualname,
                    line=node.lineno,
                    end_line=getattr(node, "end_lineno", node.lineno),
                    bases=tuple(ast.unparse(base) for base in node.bases),
                ),
                node,
            ))
            previous_owner = self.owner_class_id
            self.owner_class_id = class_id
            self.parents.append(node.name)
            for statement in node.body:
                self.visit(statement)
            self.parents.pop()
            self.owner_class_id = previous_owner

        def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
            qualname = ".".join((*self.parents, node.name))
            owner_class_id = self.owner_class_id
            owner = owner_class_id.split("::", 1)[1].rsplit(".", 1)[-1] if owner_class_id else None
            self.functions.append((
                Function(
                    id=_id(path, qualname),
                    file_id=path,
                    name=node.name,
                    qualname=qualname,
                    line=node.lineno,
                    end_line=getattr(node, "end_lineno", node.lineno),
                    owner=owner,
                    owner_class_id=owner_class_id,
                    is_async=isinstance(node, ast.AsyncFunctionDef),
                ),
                node,
            ))
            previous_owner = self.owner_class_id
            self.owner_class_id = None
            self.parents.append(node.name)
            for statement in node.body:
                self.visit(statement)
            self.parents.pop()
            self.owner_class_id = previous_owner

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self._visit_function(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self._visit_function(node)

    collector = Collector()
    collector.visit(tree)
    return collector.functions, collector.classes


def _import_bindings(
    path: str,
    tree: ast.Module,
    module_to_path: Mapping[str, str],
) -> tuple[dict[str, tuple[str, int]], dict[str, tuple[str, str]]]:
    modules: dict[str, tuple[str, int]] = {}
    symbols: dict[str, tuple[str, str]] = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".")[0]
                skipped = 0 if alias.asname else len(alias.name.split(".")) - 1
                modules[local] = (alias.name, skipped)
                symbols.pop(local, None)
        elif isinstance(node, ast.ImportFrom):
            base = _resolve_relative_module(path, node)
            if base is None:
                continue
            for alias in node.names:
                local = alias.asname or alias.name
                submodule = f"{base}.{alias.name}" if base else alias.name
                modules.pop(local, None)
                symbols.pop(local, None)
                if submodule in module_to_path:
                    modules[local] = (submodule, 0)
                elif base in module_to_path:
                    symbols[local] = (module_to_path[base], alias.name)
        else:
            writes = _ModuleBindings()
            writes.visit(node)
            for name in writes.names:
                modules.pop(name, None)
                symbols.pop(name, None)
    return modules, symbols


def _attribute_chain(node: ast.expr) -> list[str]:
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, ast.Attribute):
        return [*_attribute_chain(node.value), node.attr]
    return []


class _CallCollector(ast.NodeVisitor):
    def __init__(self, root: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.root = root
        self.calls: list[ast.Call] = []

    def collect(self) -> list[ast.Call]:
        for statement in self.root.body:
            self.visit(statement)
        return self.calls

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node is self.root:
            for statement in node.body:
                self.visit(statement)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        if node is self.root:
            for statement in node.body:
                self.visit(statement)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self.visit(node.body)

    def visit_Call(self, node: ast.Call) -> None:
        self.calls.append(node)
        self.generic_visit(node)


class _ModuleCallCollector(ast.NodeVisitor):
    """Collect import-time calls without attributing function/class bodies to a module."""

    def __init__(self) -> None:
        self.calls: list[ast.Call] = []

    def collect(self, tree: ast.Module) -> list[ast.Call]:
        for statement in tree.body:
            self.visit(statement)
        return self.calls

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return

    def visit_Call(self, node: ast.Call) -> None:
        self.calls.append(node)
        self.generic_visit(node)


class _LocalBindings(ast.NodeVisitor):
    """Collect names bound in one function scope, without entering nested scopes."""

    def __init__(self, root: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.root = root
        self.names: set[str] = set()
        self.globals: set[str] = set()

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Store):
            self.names.add(node.id)

    def visit_Global(self, node: ast.Global) -> None:
        self.globals.update(node.names)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self.names.update(node.names)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name:
            self.names.add(node.name)
        self.generic_visit(node)

    def visit_MatchAs(self, node: ast.MatchAs) -> None:
        if node.name:
            self.names.add(node.name)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node is self.root:
            for statement in node.body:
                self.visit(statement)
        else:
            self.names.add(node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        if node is self.root:
            for statement in node.body:
                self.visit(statement)
        else:
            self.names.add(node.name)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.names.add(node.name)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.names.add(alias.asname or alias.name.split(".")[0])

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            self.names.add(alias.asname or alias.name)


class _ModuleBindings(ast.NodeVisitor):
    """Find names written by a module statement without entering definitions."""

    def __init__(self) -> None:
        self.names: set[str] = set()

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Store):
            self.names.add(node.id)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.names.add(node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.names.add(node.name)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.names.add(node.name)

    def visit_Import(self, node: ast.Import) -> None:
        self.names.update(alias.asname or alias.name.split(".")[0] for alias in node.names)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self.names.update(alias.asname or alias.name for alias in node.names if alias.name != "*")

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name:
            self.names.add(node.name)
        self.generic_visit(node)

    def visit_MatchAs(self, node: ast.MatchAs) -> None:
        if node.name:
            self.names.add(node.name)
        self.generic_visit(node)


def _function_shadows(node: ast.FunctionDef | ast.AsyncFunctionDef, name: str) -> bool:
    args = node.args
    parameters = {
        arg.arg
        for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs)
    }
    if args.vararg:
        parameters.add(args.vararg.arg)
    if args.kwarg:
        parameters.add(args.kwarg.arg)
    bindings = _LocalBindings(node)
    bindings.visit(node)
    return name in parameters or (name in bindings.names and name not in bindings.globals)


def _function_reassigns(node: ast.FunctionDef | ast.AsyncFunctionDef, name: str) -> bool:
    bindings = _LocalBindings(node)
    bindings.visit(node)
    return name in bindings.names and name not in bindings.globals


def _iter_nested_statements(body: Iterable[ast.stmt]) -> Iterable[ast.stmt]:
    """Yield statements in control-flow blocks but not nested function/class scopes."""
    for statement in body:
        yield statement
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        for field_name in ("body", "orelse", "finalbody"):
            nested = getattr(statement, field_name, None)
            if isinstance(nested, list):
                yield from _iter_nested_statements(nested)
        handlers = getattr(statement, "handlers", ())
        for handler in handlers:
            yield from _iter_nested_statements(handler.body)


def _class_reference(
    expression: ast.expr,
    path: str,
    classes: Mapping[str, Class],
    module_to_path: Mapping[str, str],
    module_bindings: Mapping[str, tuple[str, int]],
    symbol_bindings: Mapping[str, tuple[str, str]],
    classes_by_file_name: Mapping[tuple[str, str], list[Class]],
) -> tuple[str, str] | None:
    chain = _attribute_chain(expression)
    if not chain:
        return None

    if len(chain) == 1:
        imported = symbol_bindings.get(chain[0])
        if imported:
            target_id = _id(imported[0], imported[1])
            if target_id in classes:
                return target_id, f"import binding `{chain[0]}` resolves to class `{target_id}`"
        local = [
            info for info in classes_by_file_name.get((path, chain[0]), ())
            if "." not in info.qualname
        ]
        if len(local) == 1:
            return local[0].id, f"unqualified base or constructor name `{chain[0]}` resolves uniquely in this module"
        return None

    imported = symbol_bindings.get(chain[0])
    if imported:
        target_id = _id(imported[0], ".".join((imported[1], *chain[1:])))
        if target_id in classes:
            return target_id, f"qualified reference uses imported class binding `{chain[0]}`"

    for prefix_length in range(len(chain), 0, -1):
        binding = module_bindings.get(".".join(chain[:prefix_length]))
        if binding is None:
            continue
        module_name, skipped = binding
        target_file = module_to_path.get(module_name)
        suffix = chain[prefix_length + skipped:]
        if target_file and suffix:
            target_id = _id(target_file, ".".join(suffix))
            if target_id in classes:
                return target_id, f"qualified reference resolves through imported module `{module_name}`"
    return None


def _class_candidates_for_value(
    expression: ast.expr,
    path: str,
    classes: Mapping[str, Class],
    module_to_path: Mapping[str, str],
    module_bindings: Mapping[str, tuple[str, int]],
    symbol_bindings: Mapping[str, tuple[str, str]],
    classes_by_file_name: Mapping[tuple[str, str], list[Class]],
    known_names: Mapping[str, set[str]] | None = None,
) -> set[str]:
    if isinstance(expression, ast.Name):
        return set((known_names or {}).get(expression.id, ()))
    if isinstance(expression, ast.Call):
        resolved = _class_reference(
            expression.func, path, classes, module_to_path, module_bindings,
            symbol_bindings, classes_by_file_name,
        )
        return {resolved[0]} if resolved else set()
    if isinstance(expression, ast.BoolOp):
        candidates = [
            _class_candidates_for_value(
                value, path, classes, module_to_path, module_bindings,
                symbol_bindings, classes_by_file_name, known_names,
            )
            for value in expression.values
        ]
        if candidates and all(len(item) == 1 for item in candidates):
            shared = set.intersection(*candidates)
            return shared
    if isinstance(expression, ast.IfExp):
        left = _class_candidates_for_value(
            expression.body, path, classes, module_to_path, module_bindings,
            symbol_bindings, classes_by_file_name, known_names,
        )
        right = _class_candidates_for_value(
            expression.orelse, path, classes, module_to_path, module_bindings,
            symbol_bindings, classes_by_file_name, known_names,
        )
        if len(left) == len(right) == 1:
            return left & right
    return set()


def _infer_instance_fields(
    class_nodes: Mapping[str, ast.ClassDef],
    classes: Mapping[str, Class],
    classes_by_file_name: Mapping[tuple[str, str], list[Class]],
    trees: Mapping[str, ast.Module],
    module_to_path: Mapping[str, str],
) -> dict[str, dict[str, str]]:
    inferred: dict[str, dict[str, str]] = {}
    for class_id, class_node in class_nodes.items():
        init = next(
            (
                member for member in class_node.body
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)) and member.name == "__init__"
            ),
            None,
        )
        if init is None or not init.args.args:
            continue
        path = classes[class_id].file_id
        module_bindings, symbol_bindings = _import_bindings(path, trees[path], module_to_path)
        receiver = init.args.args[0].arg
        parameter_types: dict[str, set[str]] = {}
        arguments = (*init.args.posonlyargs, *init.args.args, *init.args.kwonlyargs)
        for argument in arguments:
            if argument.arg == receiver or argument.annotation is None:
                continue
            matches: set[str] = set()
            for name_node in ast.walk(argument.annotation):
                if isinstance(name_node, (ast.Name, ast.Attribute)):
                    resolved = _class_reference(
                        name_node, path, classes, module_to_path, module_bindings,
                        symbol_bindings, classes_by_file_name,
                    )
                    if resolved:
                        matches.add(resolved[0])
            if len(matches) == 1:
                parameter_types[argument.arg] = matches

        field_candidates: dict[str, set[str]] = defaultdict(set)
        uncertain_fields: set[str] = set()
        for statement in _iter_nested_statements(init.body):
            if isinstance(statement, ast.Assign):
                targets = statement.targets
                value = statement.value
                annotation = None
            elif isinstance(statement, ast.AnnAssign):
                targets = [statement.target]
                value = statement.value
                annotation = statement.annotation
            else:
                continue
            for target in targets:
                target_chain = _attribute_chain(target)
                if len(target_chain) != 2 or target_chain[0] != receiver:
                    continue
                name = target_chain[1]
                if value is None:
                    uncertain_fields.add(name)
                    continue
                candidates: set[str] = set()
                if annotation is not None:
                    for name_node in ast.walk(annotation):
                        if isinstance(name_node, (ast.Name, ast.Attribute)):
                            resolved = _class_reference(
                                name_node, path, classes, module_to_path, module_bindings,
                                symbol_bindings, classes_by_file_name,
                            )
                            if resolved:
                                candidates.add(resolved[0])
                value_candidates = _class_candidates_for_value(
                    value, path, classes, module_to_path, module_bindings,
                    symbol_bindings, classes_by_file_name, parameter_types,
                )
                if candidates and value_candidates and candidates != value_candidates:
                    uncertain_fields.add(name)
                    continue
                resolved_candidates = value_candidates or candidates
                if len(resolved_candidates) == 1:
                    field_candidates[name].update(resolved_candidates)
                else:
                    uncertain_fields.add(name)
        class_fields = {
            name: next(iter(candidates))
            for name, candidates in field_candidates.items()
            if len(candidates) == 1 and name not in uncertain_fields
        }
        if class_fields:
            inferred[class_id] = class_fields
    return inferred


def _infer_module_instances(
    path: str,
    tree: ast.Module,
    classes: Mapping[str, Class],
    module_to_path: Mapping[str, str],
    classes_by_file_name: Mapping[tuple[str, str], list[Class]],
) -> dict[str, str]:
    module_bindings, symbol_bindings = _import_bindings(path, tree, module_to_path)
    assignments: dict[str, set[str]] = defaultdict(set)
    counts: dict[str, int] = defaultdict(int)
    uncertain: set[str] = set()
    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            targets = statement.targets
            value = statement.value
            annotation = None
        elif isinstance(statement, ast.AnnAssign):
            targets = [statement.target]
            value = statement.value
            annotation = statement.annotation
        else:
            writes = _ModuleBindings()
            writes.visit(statement)
            uncertain.update(writes.names)
            continue
        candidates: set[str] = set()
        if annotation is not None:
            for name_node in ast.walk(annotation):
                if isinstance(name_node, (ast.Name, ast.Attribute)):
                    resolved = _class_reference(
                        name_node, path, classes, module_to_path, module_bindings,
                        symbol_bindings, classes_by_file_name,
                    )
                    if resolved:
                        candidates.add(resolved[0])
        value_candidates = _class_candidates_for_value(
            value, path, classes, module_to_path, module_bindings,
            symbol_bindings, classes_by_file_name,
        ) if value is not None else set()
        if candidates and value_candidates and candidates != value_candidates:
            candidates.clear()
        else:
            candidates.update(value_candidates)
        for target in targets:
            if isinstance(target, ast.Name):
                counts[target.id] += 1
                if len(candidates) == 1:
                    assignments[target.id].update(candidates)
                else:
                    uncertain.add(target.id)
    return {
        name: next(iter(candidates))
        for name, candidates in assignments.items()
        if len(candidates) == 1 and counts[name] == 1 and name not in uncertain
    }


def _resolve_call_target(
    call: ast.Call,
    current: Function,
    current_node: ast.FunctionDef | ast.AsyncFunctionDef | None,
    functions: Mapping[str, Function],
    classes: Mapping[str, Class],
    module_to_path: Mapping[str, str],
    module_bindings: Mapping[str, tuple[str, int]],
    symbol_bindings: Mapping[str, tuple[str, str]],
    instance_fields: Mapping[str, Mapping[str, str]],
    module_instances: Mapping[str, str],
) -> tuple[str, str, str] | None:
    called = call.func
    chain = _attribute_chain(called)

    def target_for_id(target_id: str, reason: str) -> tuple[str, str, str] | None:
        if target_id in functions:
            return target_id, "calls", reason
        if target_id in classes:
            return target_id, "instantiates", reason
        return None

    if isinstance(called, ast.Name):
        if current_node is not None and _function_shadows(current_node, called.id):
            return None
        imported = symbol_bindings.get(called.id)
        if imported:
            return target_for_id(
                _id(imported[0], imported[1]),
                f"name `{called.id}` resolves through a module-level import binding",
            )
        function_candidates = [
            item for item in functions.values()
            if item.file_id == current.file_id and item.qualname == called.id and item.owner_class_id is None
        ]
        class_candidates = [
            item for item in classes.values()
            if item.file_id == current.file_id and item.qualname == called.id
        ]
        candidates = [*function_candidates, *class_candidates]
        if len(candidates) == 1:
            candidate = candidates[0]
            return target_for_id(candidate.id, f"unqualified name `{called.id}` resolves to a unique module definition")
        return None

    if not chain:
        return None

    if current.owner_class_id and current_node and current_node.args.args:
        receiver = current_node.args.args[0].arg
        receiver_is_stable = not _function_reassigns(current_node, receiver)
        if receiver_is_stable and chain[0] == receiver and len(chain) == 2:
            target_id = _id(current.owner_class_id.split("::", 1)[0], f"{current.owner_class_id.split('::', 1)[1]}.{chain[1]}")
            if target_id in functions:
                return target_for_id(target_id, f"receiver `{receiver}` calls a method defined on its enclosing class")
        if receiver_is_stable and chain[0] == receiver and len(chain) == 3:
            field_class = instance_fields.get(current.owner_class_id, {}).get(chain[1])
            if field_class:
                target_id = _id(field_class.split("::", 1)[0], f"{field_class.split('::', 1)[1]}.{chain[2]}")
                if target_id in functions:
                    return target_for_id(
                        target_id,
                        f"receiver field `{receiver}.{chain[1]}` has a statically inferred class from its constructor assignment",
                    )

    if current_node is not None and _function_shadows(current_node, chain[0]):
        return None

    if len(chain) == 2 and chain[0] in module_instances:
        instance_class = module_instances[chain[0]]
        target_id = _id(instance_class.split("::", 1)[0], f"{instance_class.split('::', 1)[1]}.{chain[1]}")
        if target_id in functions:
            return target_for_id(
                target_id,
                f"module-level receiver `{chain[0]}` is assigned an instance of the target class in this file",
            )

    imported_symbol = symbol_bindings.get(chain[0])
    if imported_symbol:
        if len(chain) == 1:
            return target_for_id(
                _id(imported_symbol[0], imported_symbol[1]),
                f"name `{chain[0]}` resolves through a module-level import binding",
            )
        target_id = _id(imported_symbol[0], ".".join((imported_symbol[1], *chain[1:])))
        resolved = target_for_id(target_id, f"attribute call is defined on imported symbol `{chain[0]}`")
        if resolved:
            return resolved

    for prefix_length in range(len(chain), 0, -1):
        binding = module_bindings.get(".".join(chain[:prefix_length]))
        if binding is None:
            continue
        module_name, skipped = binding
        target_file = module_to_path.get(module_name)
        suffix = chain[prefix_length + skipped:]
        if target_file and suffix:
            target_id = _id(target_file, ".".join(suffix))
            resolved = target_for_id(
                target_id,
                f"attribute call resolves through imported module `{module_name}`",
            )
            if resolved:
                return resolved
    return None


def _import_edges(
    path: str,
    tree: ast.Module,
    module_candidates: Mapping[str, list[str]],
    limitations: list[AnalysisLimitation],
) -> list[DependencyEdge]:
    edges: list[DependencyEdge] = []

    def add(module_name: str | None, node: ast.AST, evidence: str) -> None:
        if not module_name:
            return
        candidates = module_candidates.get(module_name, [])
        if len(candidates) > 1:
            limitations.append(AnalysisLimitation(
                file_id=path,
                kind="ambiguous_module",
                detail=f"Import `{module_name}` matches multiple repository modules; no import edge was selected.",
                line=getattr(node, "lineno", None),
                evidence=evidence,
            ))
        elif len(candidates) == 1 and candidates[0] != path:
            target = candidates[0]
            edges.append(DependencyEdge(
                source=path,
                target=target,
                kind="imports",
                reason=f"Python import resolves module `{module_name}` to this repository file.",
                evidence=evidence,
                line=getattr(node, "lineno", None),
            ))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                add(alias.name, node, ast.unparse(node))
        elif isinstance(node, ast.ImportFrom):
            base = _resolve_relative_module(path, node)
            if base is None:
                limitations.append(AnalysisLimitation(
                    file_id=path,
                    kind="unresolved_relative_import",
                    detail="Relative import level extends beyond the statically known package path.",
                    line=node.lineno,
                    evidence=ast.unparse(node),
                ))
                continue
            add(base, node, ast.unparse(node))
            for alias in node.names:
                if alias.name == "*":
                    limitations.append(AnalysisLimitation(
                        file_id=path,
                        kind="star_import",
                        detail="Star imports do not identify the imported repository symbols statically.",
                        line=node.lineno,
                        evidence=ast.unparse(node),
                    ))
                    continue
                child_module = f"{base}.{alias.name}" if base else alias.name
                if child_module in module_candidates:
                    add(child_module, node, ast.unparse(node))
    return edges


def _fastapi_constructors(tree: ast.Module) -> tuple[set[str], set[str]]:
    """Return currently bound FastAPI constructors and module aliases."""
    constructor_names: set[str] = set()
    module_aliases: set[str] = set()
    recognized_modules = {"fastapi", "fastapi.routing", "fastapi.applications"}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".")[0]
                constructor_names.discard(local)
                if alias.name == "fastapi" or alias.name.startswith("fastapi."):
                    module_aliases.add(local)
                else:
                    module_aliases.discard(local)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                local = alias.asname or alias.name
                module_aliases.discard(local)
                if node.module in recognized_modules and alias.name in {"APIRouter", "FastAPI"}:
                    constructor_names.add(local)
                else:
                    constructor_names.discard(local)
        else:
            writes = _ModuleBindings()
            writes.visit(node)
            constructor_names.difference_update(writes.names)
            module_aliases.difference_update(writes.names)
    return constructor_names, module_aliases


def _is_fastapi_constructor(
    expression: ast.expr,
    constructor_names: set[str],
    module_aliases: set[str],
) -> bool:
    chain = _attribute_chain(expression)
    if len(chain) == 1:
        return chain[0] in constructor_names
    return bool(chain and chain[0] in module_aliases and chain[-1] in {"APIRouter", "FastAPI"})


def _router_prefixes(tree: ast.Module) -> dict[str, str | None]:
    prefixes: dict[str, str | None] = {}
    constructor_names, module_aliases = _fastapi_constructors(tree)
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        call = node.value
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        is_router = isinstance(call, ast.Call) and _is_fastapi_constructor(
            call.func, constructor_names, module_aliases
        )
        prefix_keyword = next((item for item in call.keywords if item.arg == "prefix"), None) if is_router else None
        if not is_router:
            prefix = None
        elif prefix_keyword is None:
            prefix = ""
        elif isinstance(prefix_keyword.value, ast.Constant) and isinstance(prefix_keyword.value.value, str):
            prefix = prefix_keyword.value.value.rstrip("/")
        else:
            prefix = None
        for target in targets:
            if isinstance(target, ast.Name):
                if is_router:
                    prefixes[target.id] = prefix
                else:
                    prefixes.pop(target.id, None)
    return prefixes


def _endpoint_nodes(
    path: str,
    tree: ast.Module,
    functions: Mapping[str, Function],
    limitations: list[AnalysisLimitation],
) -> list[APIEndpoint]:
    route_methods = {"get", "post", "put", "patch", "delete", "options", "head", "websocket"}
    prefixes = _router_prefixes(tree)
    endpoints: list[APIEndpoint] = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        handler_id = _id(path, node.name)
        if handler_id not in functions:
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                continue
            method = decorator.func.attr.lower()
            if method not in route_methods:
                continue
            owner = decorator.func.value.id if isinstance(decorator.func.value, ast.Name) else None
            if owner is None or owner not in prefixes:
                limitations.append(AnalysisLimitation(
                    file_id=path,
                    kind="unverified_api_route_decorator",
                    detail="A route-like decorator is not attached to a variable statically constructed from an imported FastAPI or APIRouter class.",
                    line=decorator.lineno,
                    evidence=ast.unparse(decorator),
                ))
                continue
            route_arg = decorator.args[0] if decorator.args else next(
                (item.value for item in decorator.keywords if item.arg in {"path", "route"}), None
            )
            route_path = (
                route_arg.value
                if isinstance(route_arg, ast.Constant) and isinstance(route_arg.value, str)
                else None
            )
            prefix = prefixes[owner]
            full_path: str | None = None
            if route_path is not None and prefix is not None:
                full_path = (
                    f"{prefix}/{route_path.lstrip('/')}"
                    if prefix and route_path
                    else prefix or route_path
                )
            else:
                detail = "Route path is not a string literal." if route_path is None else (
                    "Router prefix is not statically known, so the full endpoint path is uncertain."
                )
                limitations.append(AnalysisLimitation(
                    file_id=path,
                    kind="dynamic_api_route",
                    detail=detail,
                    line=decorator.lineno,
                    evidence=ast.unparse(decorator),
                ))
            decorator_text = ast.unparse(decorator)
            endpoint_id = f"endpoint::{path}::{method.upper()}::{node.name}::{decorator.lineno}"
            endpoints.append(APIEndpoint(
                id=endpoint_id,
                file_id=path,
                method=method.upper(),
                path=full_path,
                handler_id=handler_id,
                handler_name=node.name,
                decorator=decorator_text,
                line=decorator.lineno,
            ))
    return endpoints


def _limitation_key(item: AnalysisLimitation) -> tuple[object, ...]:
    return item.file_id, item.line or 0, item.kind, item.detail, item.evidence or ""


def build_repository_graph(files: Mapping[str, str]) -> RepositoryGraph:
    """Parse a repository snapshot into typed nodes and evidence-bearing edges.

    Only imports and calls with a statically resolvable repository binding become
    dependency edges. Unresolved internal-looking calls and unsupported syntax are
    returned in ``RepositoryGraph.limitations`` instead of being guessed.
    """
    normalized_files: dict[str, str] = {}
    for original_path, content in files.items():
        path = normalize_path(original_path)
        if path in normalized_files:
            raise InvalidAnalysisRequest(f"Duplicate normalized repository path: {path}")
        if not isinstance(content, str):
            raise InvalidAnalysisRequest(f"Source content must be text: {path}")
        normalized_files[path] = content

    limitations: list[AnalysisLimitation] = []
    module_candidates: dict[str, list[str]] = defaultdict(list)
    for path in sorted(normalized_files):
        module_name = _module_for_path(path)
        if module_name:
            module_candidates[module_name].append(path)
        elif PurePosixPath(path).suffix == ".py":
            limitations.append(AnalysisLimitation(
                file_id=path,
                kind="invalid_module_path",
                detail="Python file path does not map to a valid dotted module name.",
            ))
    module_to_path = {
        name: paths[0] for name, paths in module_candidates.items() if len(paths) == 1
    }
    for name, paths in module_candidates.items():
        if len(paths) > 1:
            for path in paths:
                limitations.append(AnalysisLimitation(
                    file_id=path,
                    kind="ambiguous_module",
                    detail=f"Module name `{name}` is provided by multiple files; imports will not be resolved to one.",
                ))

    trees: dict[str, ast.Module] = {}
    parse_errors: dict[str, str] = {}
    for path, source in sorted(normalized_files.items()):
        if PurePosixPath(path).suffix != ".py":
            continue
        try:
            trees[path] = ast.parse(source, filename=path)
        except SyntaxError as error:
            message = f"line {error.lineno}: {error.msg}"
            parse_errors[path] = message
            limitations.append(AnalysisLimitation(
                file_id=path,
                kind="syntax_error",
                detail=message,
                line=error.lineno,
                evidence=error.text.strip() if error.text else None,
            ))

    file_nodes = tuple(
        File(
            id=path,
            path=path,
            language=_language_for_path(path),
            is_test_file=_is_test_file(path),
            parse_status=("not_python" if PurePosixPath(path).suffix != ".py" else (
                "syntax_error" if path in parse_errors else "parsed"
            )),
            parse_error=parse_errors.get(path),
        )
        for path in sorted(normalized_files)
    )
    module_nodes = tuple(
        Module(
            id=f"module::{name}" if len(paths) == 1 else f"module::{name}::{path}",
            name=name,
            file_id=path,
            is_package=PurePosixPath(path).name == "__init__.py",
        )
        for name, paths in sorted(module_candidates.items())
        for path in sorted(paths)
    )
    module_id_by_file = {item.file_id: item.id for item in module_nodes}

    definitions: dict[str, tuple[Function, ast.FunctionDef | ast.AsyncFunctionDef]] = {}
    class_definitions: dict[str, tuple[Class, ast.ClassDef]] = {}
    for path, tree in sorted(trees.items()):
        functions, classes = _collect_definitions(path, tree)
        definitions.update({function.id: (function, node) for function, node in functions})
        class_definitions.update({item.id: (item, node) for item, node in classes})
    functions_by_id = {key: value[0] for key, value in definitions.items()}
    classes_by_id = {key: value[0] for key, value in class_definitions.items()}
    classes_by_file_name: dict[tuple[str, str], list[Class]] = defaultdict(list)
    class_nodes = {key: value[1] for key, value in class_definitions.items()}
    for item in classes_by_id.values():
        classes_by_file_name[(item.file_id, item.name)].append(item)

    edges: list[DependencyEdge] = []
    for path, tree in sorted(trees.items()):
        for edge in _import_edges(path, tree, module_candidates, limitations):
            edges.append(edge)

    for module in module_nodes:
        edges.append(DependencyEdge(
            source=module.file_id,
            target=module.id,
            kind="defines_module",
            reason="Python package and file path determine this dotted module name.",
            evidence=module.name,
        ))
    sources = normalized_files
    test_nodes: list[Test] = []
    for function_id, (function, node) in sorted(definitions.items()):
        evidence = _source_line(sources[function.file_id], function.line)
        edges.append(DependencyEdge(
            source=function.file_id,
            target=function.id,
            kind="defines_function",
            reason="AST contains this function definition in the source file.",
            evidence=evidence,
            line=function.line,
        ))
        if function.owner_class_id:
            edges.append(DependencyEdge(
                source=function.owner_class_id,
                target=function.id,
                kind="defines_method",
                reason="AST places this function directly in the class body.",
                evidence=evidence,
                line=function.line,
            ))
        if _is_test_file(function.file_id) and function.name.startswith("test_"):
            test = Test(
                id=f"test::{function.id}",
                file_id=function.file_id,
                function_id=function.id,
                name=function.name,
                line=function.line,
                discovery="pytest function naming convention",
            )
            test_nodes.append(test)
            edges.append(DependencyEdge(
                source=function.file_id,
                target=test.id,
                kind="contains_test",
                reason="The source file is a test file and this function name matches pytest discovery.",
                evidence=evidence,
                line=function.line,
            ))
            edges.append(DependencyEdge(
                source=function.id,
                target=test.id,
                kind="classified_as_test",
                reason="The function name starts with `test_` inside a test file.",
                evidence=evidence,
                line=function.line,
            ))

    for class_id, (class_node, node) in sorted(class_definitions.items()):
        edges.append(DependencyEdge(
            source=class_node.file_id,
            target=class_node.id,
            kind="defines_class",
            reason="AST contains this class definition in the source file.",
            evidence=_source_line(sources[class_node.file_id], class_node.line),
            line=class_node.line,
        ))

    instance_fields = _infer_instance_fields(
        class_nodes, classes_by_id, classes_by_file_name, trees, module_to_path
    )
    for path, tree in sorted(trees.items()):
        module_bindings, symbol_bindings = _import_bindings(path, tree, module_to_path)
        module_instances = _infer_module_instances(
            path, tree, classes_by_id, module_to_path, classes_by_file_name
        )
        for info_id, (function, function_node) in definitions.items():
            if function.file_id != path:
                continue
            for call in _CallCollector(function_node).collect():
                target = _resolve_call_target(
                    call,
                    function,
                    function_node,
                    functions_by_id,
                    classes_by_id,
                    module_to_path,
                    module_bindings,
                    symbol_bindings,
                    instance_fields,
                    module_instances,
                )
                expression = ast.unparse(call)
                if target:
                    target_id, kind, reason = target
                    edges.append(DependencyEdge(
                        source=info_id,
                        target=target_id,
                        kind=kind,
                        reason=reason,
                        evidence=expression,
                        line=call.lineno,
                    ))
                    if kind == "calls" and "receiver" in reason:
                        limitations.append(AnalysisLimitation(
                            file_id=path,
                            kind="dynamic_dispatch",
                            detail="The edge targets the statically inferred method, but subclass overrides, proxies, or runtime reassignment can change the implementation that executes.",
                            line=call.lineno,
                            evidence=expression,
                        ))
                    continue

                chain = _attribute_chain(call.func)
                called_name = chain[-1] if chain else None
                if not chain:
                    limitations.append(AnalysisLimitation(
                        file_id=path,
                        kind="dynamic_call",
                        detail="Call target is an expression rather than a statically resolvable name or attribute.",
                        line=call.lineno,
                        evidence=expression,
                    ))
                elif called_name and (
                    any(item.name == called_name for item in functions_by_id.values())
                    or any(item.name == called_name for item in classes_by_id.values())
                ) and (chain[0] in {"self", "cls"} or chain[0] in module_bindings or isinstance(call.func, ast.Name)):
                    limitations.append(AnalysisLimitation(
                        file_id=path,
                        kind="unresolved_internal_call",
                        detail=f"A repository definition named `{called_name}` may be the target, but static binding was insufficient; no call edge was invented.",
                        line=call.lineno,
                        evidence=expression,
                    ))

        module_id = module_id_by_file.get(path, path)
        for call in _ModuleCallCollector().collect(tree):
            module_function = Function(
                id=module_id,
                file_id=path,
                name="<module>",
                qualname="<module>",
                line=call.lineno,
                end_line=call.end_lineno or call.lineno,
                owner=None,
                owner_class_id=None,
                is_async=False,
            )
            target = _resolve_call_target(
                call,
                module_function,
                None,
                functions_by_id,
                classes_by_id,
                module_to_path,
                module_bindings,
                symbol_bindings,
                instance_fields,
                module_instances,
            )
            expression = ast.unparse(call)
            if target:
                target_id, kind, reason = target
                edges.append(DependencyEdge(
                    source=module_id,
                    target=target_id,
                    kind=kind,
                    reason=f"Module-level call: {reason}",
                    evidence=expression,
                    line=call.lineno,
                ))
            elif not _attribute_chain(call.func):
                limitations.append(AnalysisLimitation(
                    file_id=path,
                    kind="dynamic_call",
                    detail="Module-level call target is an expression rather than a statically resolvable name or attribute.",
                    line=call.lineno,
                    evidence=expression,
                ))

    for class_id, (class_node, node) in sorted(class_definitions.items()):
        path = class_node.file_id
        module_bindings, symbol_bindings = _import_bindings(path, trees[path], module_to_path)
        for base in node.bases:
            resolved = _class_reference(
                base, path, classes_by_id, module_to_path, module_bindings,
                symbol_bindings, classes_by_file_name,
            )
            if resolved:
                target_id, reason = resolved
                edges.append(DependencyEdge(
                    source=class_id,
                    target=target_id,
                    kind="inherits",
                    reason=reason,
                    evidence=f"class {class_node.name}({ast.unparse(base)})",
                    line=node.lineno,
                ))
            elif isinstance(base, (ast.Name, ast.Attribute)) and any(
                item.name == _attribute_chain(base)[-1] for item in classes_by_id.values()
            ):
                limitations.append(AnalysisLimitation(
                    file_id=path,
                    kind="unresolved_base_class",
                    detail=f"Base `{ast.unparse(base)}` resembles a repository class, but its binding could not be resolved.",
                    line=node.lineno,
                    evidence=ast.unparse(base),
                ))

    endpoints: list[APIEndpoint] = []
    for path, tree in sorted(trees.items()):
        endpoints.extend(_endpoint_nodes(path, tree, functions_by_id, limitations))
    for endpoint in endpoints:
        edges.append(DependencyEdge(
            source=endpoint.id,
            target=endpoint.handler_id,
            kind="handled_by",
            reason="The route decorator is attached to this endpoint handler definition.",
            evidence=endpoint.decorator,
            line=endpoint.line,
        ))

    return RepositoryGraph(
        files=file_nodes,
        modules=module_nodes,
        functions=tuple(sorted(functions_by_id.values(), key=lambda item: item.id)),
        classes=tuple(sorted(classes_by_id.values(), key=lambda item: item.id)),
        api_endpoints=tuple(sorted(endpoints, key=lambda item: item.id)),
        tests=tuple(sorted(test_nodes, key=lambda item: item.id)),
        edges=tuple(sorted(set(edges), key=lambda item: (
            item.source, item.target, item.kind, item.line or 0, item.reason, item.evidence
        ))),
        limitations=tuple(sorted(set(limitations), key=_limitation_key)),
    )
