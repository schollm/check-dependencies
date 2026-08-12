"""Main module for check_dependencies."""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from check_dependencies.app_config import ProjectConfig
from check_dependencies.lib import Module, Package
from check_dependencies.outputs import (
    ExtraPackage,
    FileError,
    InfoMessage,
    MissingModule,
    NoPyprojectError,
    OkDependency,
    Output,
    UnknownModule,
)
from check_dependencies.pyproject_toml import (
    NoPyProjectFileError,
    PyProjectToml,
    get_pyproject_toml,
)

if TYPE_CHECKING:
    from collections.abc import Collection, Generator, Iterable, Iterator
    from pathlib import Path

    from check_dependencies.app_config import AppConfig

logger = logging.getLogger("check_dependencies")


def yield_outputs(app_cfg: AppConfig) -> Generator[Output, None, None]:
    """Yield output objects of missing/unused imports.

    :param app_cfg: Application configuration used to determine which files to
        scan and how to resolve and report project dependencies.
    """
    # Map pyproject path → per-project accumulator.
    # A regular dict is used because the factory would need the AppConfig; we
    # initialize on first encounter instead of relying on defaultdict's zero-arg
    # factory.
    # One formatter per project — its internal dedup cache spans all files in
    # the same project.
    yield from InfoMessage.from_iter(_verbose_app_info(app_cfg), verbose=True)
    try:
        registry = _ProjectRegistry(app_cfg)
    except NoPyProjectFileError as exc:
        logger.error("Could not find pyproject.toml for %s", exc)  # noqa: TRY400
        yield NoPyprojectError(str(exc))
        return

    seen: set[Path] = set()
    for src_pth in (
        src_pth
        for root_pth in app_cfg.file_names
        for src_pth in (root_pth.rglob("*.py") if root_pth.is_dir() else [root_pth])
        if src_pth not in seen
    ):
        seen.add(src_pth)
        try:
            current = registry.get(src_pth)
        except NoPyProjectFileError as exc:  # pragma: no cover
            yield NoPyprojectError(str(exc))
            return

        yield from _source_imports_iter(src_pth, current)

    # After processing all files, check for superfluous requirements in each project.
    for entry in registry.entry.values():
        yield from InfoMessage.from_iter(
            _verbose_project_info(entry.project_cfg), verbose=False
        )
        for pkg in entry.get_superfluous_dependencies():
            yield ExtraPackage(entry.project_cfg, pkg)


@dataclass
class OptionalDependencyConfig:
    """Configuration for optional dependencies."""

    path: Path
    dependencies: set[Package]
    _used: bool = field(default=False, init=False)
    _imported: set[Package] = field(default_factory=set, init=False)

    def handles(self, path: Path) -> bool:
        """Check if this optional dependency handles the given path."""
        return path.is_relative_to(self.path)

    def register_imports(self, packages: Iterable[Package]) -> set[Package]:
        """Register imports for this optional dependency."""
        self._used = True
        seen = set(packages)
        self._imported.update(seen)
        return self.dependencies

    def mark_used(self) -> None:
        """Mark this optional dependency as used."""
        self._used = True

    def superfluous_dependencies(self) -> set[Package]:
        """Get the set of superfluous dependencies for this optional dependency."""
        if not self._used:
            return set()
        return self.dependencies - self._imported


@dataclass
class RegistryEntry:
    """Entry in the project registry."""

    project_cfg: ProjectConfig
    optionals: list[OptionalDependencyConfig]
    _seen: set[Package] = field(default_factory=set, init=False)

    @classmethod
    def from_project(cls, app_cfg: AppConfig, proj: PyProjectToml) -> RegistryEntry:
        """Get an instance from a project and app config."""
        return cls(
            project_cfg=ProjectConfig.from_config(app_cfg, proj),
            optionals=[
                OptionalDependencyConfig(proj.path.parent / path, set(od))
                for path, od in proj.optional_dependencies_cfg.items()
            ],
        )

    def _matched_optionals(self, path: Path) -> Iterable[OptionalDependencyConfig]:
        return (option for option in self.optionals if option.handles(path))

    def mark_used(self, path: Path) -> None:
        """Mark all associated dependency groups as used."""
        for option in self._matched_optionals(path):
            option.mark_used()

    def _add_imports(self, path: Path, packages: Collection[Package]) -> None:
        """Update the additional dependencies for this registry entry."""
        seen = set(packages)
        for option in self._matched_optionals(path):
            seen -= option.register_imports(packages)
        self._seen.update(seen)

    def get_superfluous_dependencies(self) -> list[Package]:
        """Get the set of superfluous dependencies for this registry entry."""
        # Expected dependencies are all [project.dependencies] + optional dependencies
        expected = set(self.project_cfg.defined_dependencies) | {
            dep
            for option in self.optionals
            for dep in option.superfluous_dependencies()
        }
        consumed = self._seen.union(self.project_cfg.known_extra)
        return sorted(expected - consumed)

    def _optional_dependencies(self, path: Path) -> list[Package]:
        cfg = self.project_cfg
        project_path = cfg.path.parent
        return [
            package
            for dep_path, packages in cfg.optional_dependencies.items()
            if path.is_relative_to(project_path / dep_path)
            for package in packages
        ]

    def _additional_dependencies(self, path: Path) -> set[Package]:
        """Get the set of additional dependencies for this source file."""
        return set(self._optional_dependencies(path))

    def is_known_module(self, file: Path, module: Module) -> bool:
        """Check if a module is a known module and update the used."""
        cfg = self.project_cfg
        pkg_ = cfg.packages.packages(module)
        self._add_imports(file, pkg_)
        return bool(
            any(parent in cfg.known_missing for parent in module.parents)
            or pkg_.intersection(cfg.allowed_dependencies)
            or pkg_.intersection(self._additional_dependencies(file))
        )


class _ProjectRegistry:
    """Registry of dependencies for a project, with formatters for output."""

    def __init__(self, app_cfg: AppConfig) -> None:
        """Initialize ProjectRegistry."""
        self.app_cfg = app_cfg
        self.include_dev = app_cfg.include_dev
        self.entry: dict[Path, RegistryEntry] = {}

        # Pre-populate registry to fail fast if pyproject.toml files are missing.
        for path in app_cfg.file_names:
            self.get(path)

    def get(self, path: Path) -> RegistryEntry:
        """Get the set of packages associated with a given path."""
        pyproject_pth = get_pyproject_toml(path if path.is_dir() else path.parent)
        if pyproject_pth not in self.entry:
            self.entry[pyproject_pth] = self._new_config(pyproject_pth)

        return self.entry[pyproject_pth]

    def _new_config(self, pyproject_pth: Path) -> RegistryEntry:
        """Get the config associated with a given path."""
        proj = PyProjectToml.for_path(pyproject_pth, include_dev=self.include_dev)
        return RegistryEntry.from_project(self.app_cfg, proj)


def _verbose_app_info(app_cfg: AppConfig) -> Iterable[str]:
    if not app_cfg.verbose:
        return
    yield f"OUTPUT_FORMAT={app_cfg.output_format.value}"
    yield f"INCLUDE_DEV={app_cfg.include_dev}"
    for extra in sorted(app_cfg.known_extra):
        yield f"EXTRA {extra}"
    for missing in sorted(app_cfg.known_missing):
        yield f"MISSING {missing.name}"


def _verbose_project_info(project_cfg: ProjectConfig) -> Iterable[str]:
    yield f"##### {project_cfg.path} ###"
    for package in sorted(project_cfg.packages.all_packages()):
        modules = ", ".join(
            m.name for m in sorted(project_cfg.packages.modules(package))
        )
        yield f"PROVIDES {package} -> [{modules}]"


def _source_imports_iter(file: Path, current: RegistryEntry) -> Iterator[Output]:
    """Find missing imports in a Python file.

    :param file: Python file to analyze
    :param current: Registry entry for the current project.
    :yields: Tuple of status, module and import statement
    """
    try:
        parsed = ast.parse(file.read_bytes(), filename=file.as_posix())
    except (SyntaxError, OSError, PermissionError, FileNotFoundError) as exc:
        logger.warning("Could not parse %s", file, exc_info=False)
        yield FileError(file, str(exc))
        return
    current.mark_used(file)
    for module, stmt in _imports_iter(parsed.body):
        if module.raw:
            yield UnknownModule(file, stmt, module)
            continue
        if current.is_known_module(file, module):
            yield OkDependency(file, stmt, module)
        else:
            yield MissingModule(file, stmt, module)


def _imports_iter(body: list[ast.stmt]) -> Iterator[tuple[Module, ast.AST]]:
    """Yield all import statements from a body of code.

    :param body: List of AST statements to analyze.
    """
    for node in (node for stmt in body for node in ast.walk(stmt)):
        yield from _imports(node)
        yield from _import_builtin(node)


def _imports(stmt: ast.AST) -> Iterable[tuple[Module, ast.AST]]:
    """Yield all module names from an import statement."""
    if isinstance(stmt, ast.Import):
        for alias in stmt.names:
            yield Module(alias.name), stmt
    elif isinstance(stmt, ast.ImportFrom) and stmt.level == 0 and stmt.module:
        # level > 0 means relative import

        yield from (
            (
                Module(
                    stmt.module if alias.name == "*" else f"{stmt.module}.{alias.name}"
                ),
                stmt,
            )
            for alias in stmt.names
        )


def _import_builtin(stmt: ast.AST) -> Iterable[tuple[Module, ast.AST]]:
    if not isinstance(stmt, ast.Call):
        return

    if (id_ := _fq_call_name(stmt)) in ("__import__", "__builtins__.__import__"):
        if stmt.args:
            # __import__ is called with at least one argument, which is the module name
            arg = stmt.args[0]
        elif kw_name_arg := [kw.value for kw in stmt.keywords if kw.arg == "name"]:
            # __import__ is called with keyword __import(name=...)
            arg = kw_name_arg[0]
        else:
            # __import__ is called without arguments, which is invalid, so we ignore it.
            return

        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            yield Module(arg.value), stmt
        else:
            yield Module(f"{id_}(...)", raw=True), stmt


def _fq_call_name(stmt: ast.Call) -> str | None:
    """Get the fully qualified name of a function call, if possible."""
    func = stmt.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return f"{func.value.id}.{func.attr}"
    return None
