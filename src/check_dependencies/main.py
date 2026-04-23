"""Main module for check_dependencies."""

from __future__ import annotations

import ast
import logging
from typing import TYPE_CHECKING, Iterable

from check_dependencies.app_config import ProjectConfig
from check_dependencies.lib import Dependency, Module, Package
from check_dependencies.pyproject_toml import (
    NoPyProjectFileError,
    PyProjectToml,
    get_pyproject_toml,
)

if TYPE_CHECKING:
    from collections.abc import Generator, Iterator
    from pathlib import Path

    from check_dependencies.app_config import AppConfig

logger = logging.getLogger("check_dependencies")
ERR_MISSING_DEPENDENCY = 2
ERR_EXTRA_DEPENDENCY = 4
ERR_NO_PYPROJECT = 8
ERR_FILE = 16


def yield_wrong_imports(app_cfg: AppConfig) -> Generator[str, None, int]:
    """Yield output lines of missing/unused imports.

    :param app_cfg: Application configuration used to determine which files to
        scan and how to resolve and report project dependencies.
    """
    # Map pyproject path → per-project accumulator.
    # A regular dict is used because the factory would need the AppConfig; we
    # initialise on first encounter instead of relying on defaultdict's zero-arg
    # factory.
    # One formatter per project — its internal dedup cache spans all files in
    # the same project.
    exit_status = 0
    registry = _ProjectRegistry(app_cfg)
    seen = set()
    for src_pth in (
        src_pth
        for root_pth in app_cfg.file_names
        for src_pth in (root_pth.rglob("*.py") if root_pth.is_dir() else [root_pth])
    ):
        if src_pth in seen:
            continue
        seen.add(src_pth)
        try:
            project_cfg, used_deps = registry.get(src_pth)
        except NoPyProjectFileError as exc:
            logger.error("Could not find pyproject.toml for %s", exc)  # noqa: TRY400
            return exit_status | ERR_NO_PYPROJECT

        for cause, module, stmt in _missing_imports_iter(src_pth, project_cfg):
            if cause not in (Dependency.OK, Dependency.FILE_ERROR, Dependency.UNKNOWN):
                exit_status |= ERR_MISSING_DEPENDENCY
            if not module.raw:
                used_deps |= project_cfg.packages.packages(module)
            yield from project_cfg.src_formatter(
                src_pth.as_posix(), cause, module, stmt
            )

    yield from _verbose_app_info(app_cfg)
    for pyproject_pth, (project_cfg, used_deps) in registry.registry.items():
        yield from _verbose_project_info(app_cfg, project_cfg)
        if superfluous_requirements := [
            msg
            for dep in sorted(
                set(project_cfg.defined_dependencies).difference(
                    used_deps, project_cfg.known_extra
                ),
            )
            for msg in app_cfg.unused_fmt(str(dep))
        ]:
            exit_status |= ERR_EXTRA_DEPENDENCY
            if app_cfg.verbose:
                yield ""
                yield "### Dependencies in config file not used in application:"
                yield f"# Config file: {pyproject_pth}"
            yield from superfluous_requirements

    return exit_status


class _ProjectRegistry:
    """Registry of dependencies for a project, with formatters for output."""

    def __init__(self, app_cfg: AppConfig) -> None:
        """Initialize ProjectRegistry."""
        self.app_cfg = app_cfg
        self.include_dev = app_cfg.include_dev
        self.registry = {}

    def get(self, path: Path) -> tuple[ProjectConfig, set[Package]]:
        """Get the set of packages associated with a given path."""
        pyproject_pth = get_pyproject_toml(path.parent)
        if pyproject_pth not in self.registry:
            self.registry[pyproject_pth] = (self._new_config(pyproject_pth), set())

        return self.registry[pyproject_pth]

    def _new_config(self, pyproject_pth: Path) -> ProjectConfig:
        """Get the config associated with a given path."""
        proj = PyProjectToml.for_path(pyproject_pth, include_dev=self.include_dev)
        return ProjectConfig.from_config(self.app_cfg, proj)


def _verbose_app_info(app_cfg: AppConfig) -> Iterable[str]:
    if not app_cfg.verbose:
        return
    yield f"# ALL={app_cfg.show_all}"
    yield f"# INCLUDE_DEV={app_cfg.include_dev}"
    for extra in sorted(app_cfg.known_extra):
        yield f"# EXTRA {extra}"
    for missing in sorted(app_cfg.known_missing):
        yield f"# MISSING {missing.name}"


def _verbose_project_info(
    app_cfg: AppConfig, project_cfg: ProjectConfig
) -> Iterable[str]:
    if not app_cfg.verbose:
        return
    yield f"# CONFIG: {project_cfg.path}"
    for package in sorted(project_cfg.packages.all_packages()):
        modules = ", ".join(
            m.name for m in sorted(project_cfg.packages.modules(package))
        )
        yield f"# PROVIDES {package} -> [{modules}]"


def _missing_imports_iter(
    file: Path, project_cfg: ProjectConfig
) -> Iterator[tuple[Dependency, Module, ast.AST]]:
    """Find missing imports in a Python file.

    :param file: Python file to analyze
    :param dependencies: Declared dependencies from pyproject file
    :yields: Tuple of status, module and import statement
    """
    try:
        parsed = ast.parse(file.read_bytes(), filename=file.as_posix())
    except (SyntaxError, OSError, PermissionError, FileNotFoundError):
        logger.warning("Could not parse %s", file, exc_info=False)
        yield (
            Dependency.FILE_ERROR,
            Module(file.as_posix(), raw=True),
            ast.Raise(lineno=-1),
        )
        return
    for module, stmt in _imports_iter(parsed.body):
        if module.raw:
            yield Dependency.UNKNOWN, module, stmt
        else:
            pkg_ = project_cfg.packages.packages(module)
            status = (
                Dependency.OK
                if module.main in project_cfg.known_missing
                or pkg_.intersection(project_cfg.allowed_dependencies)
                else Dependency.NA
            )
            yield status, module, stmt


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
        yield Module(stmt.module), stmt


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
