"""Main module for check_dependencies."""

from __future__ import annotations

import ast
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

from check_dependencies.builtin_module import BUILTINS
from check_dependencies.lib import Dependency, Module, Package, Packages

if TYPE_CHECKING:
    from collections.abc import Collection, Generator, Iterator

    from check_dependencies.app_config import AppConfig

logger = logging.getLogger("check_dependencies")
ERR_MISSING_DEPENDENCY = 2
ERR_EXTRA_DEPENDENCY = 4
ERR_NO_PYPROJECT = 8
ERR_FILE = 16


def yield_wrong_imports(
    file_names: Collection[str],
    app_cfg: AppConfig,
) -> Generator[str, None, int]:
    """Yield output lines of missing/unused imports.

    :param file_names: List of file paths to analyze.
    :param app_cfg: Application configuration containing dependencies and settings.
        If app_cfg.show_all is True, all imports are shown.
    """
    used_deps: set[Package] = set()
    src_fmt = app_cfg.mk_src_formatter()

    allowed_dependencies = {
        *app_cfg.dependencies,  # dependencies from pyproject.toml
        *app_cfg.known_extra,
        *Package.set(BUILTINS),
        *Package.set(app_cfg.known_missing),
    }
    provides = app_cfg.provides

    exit_status = 0

    for src_pth in _project_files(file_names):
        for cause, module, stmt in _missing_imports_iter(
            src_pth, dependencies=allowed_dependencies, provides=provides
        ):
            if cause not in (Dependency.OK, Dependency.FILE_ERROR):
                exit_status |= ERR_MISSING_DEPENDENCY
            if not module.raw:
                used_deps |= provides.packages(module.name)
            yield from src_fmt(src_pth.as_posix(), cause, module, stmt)

    if superfluous_requirements := [
        msg
        for dep in sorted(
            set(app_cfg.dependencies).difference(used_deps, app_cfg.known_extra),
        )
        for msg in app_cfg.unused_fmt(str(dep))
    ]:
        exit_status |= ERR_EXTRA_DEPENDENCY
        if app_cfg.verbose:
            yield ""
            yield "### Dependencies in config file not used in application:"
            yield f"# Config file: {app_cfg.pyproject_file}"
        yield from superfluous_requirements
    return exit_status


def _project_files(file_names: Collection[str]) -> Iterator[Path]:
    """Collect all Python files in a list of files or directories.

    Ensure no file is visited more than once.

    :param file_names: List of file paths or directories to analyze.
    """
    visited = set()
    for p in map(Path, file_names):
        for p_sub in p.rglob("*.py") if p.is_dir() else [p]:
            # resolve to avoid duplicates from symlinks or different relative paths.
            # Symlink can be pointed outside the project directory.
            if (p_sub_resolved := p_sub.resolve()) not in visited:
                visited.add(p_sub_resolved)
                yield p_sub


def _missing_imports_iter(
    file: Path,
    dependencies: Collection[Package],
    provides: Packages,
) -> Iterator[tuple[Dependency, Module, ast.AST]]:
    """Find missing imports in a Python file.

    :param file: Pyton file to analyze
    :param dependencies: Declared dependencies from pyproject file
    :yields: Tuple of status, module name and optional import statement
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
    for module, stmt in _imports_iter(parsed.body, file):
        if module.raw:
            yield Dependency.NA, module, stmt
        else:
            pkg_ = provides.packages(module.name)
            status = Dependency.OK if pkg_.intersection(dependencies) else Dependency.NA
            yield status, module, stmt


def _imports_iter(
    body: list[ast.stmt], file: Path | str = "-"
) -> Iterator[tuple[Module, ast.AST]]:
    """Yield all import statements from a body of code.

    :param body: List of AST statements to analyze.
    """
    for node in (node for stmt in body for node in ast.walk(stmt)):
        yield from _imports(node)
        yield from _import_builtin(node, file=file)


def _imports(stmt: ast.AST) -> Iterable[tuple[Module, ast.AST]]:
    """Yield all module names from an import statement."""
    if isinstance(stmt, ast.Import):
        for alias in stmt.names:
            yield Module(alias.name), stmt
    elif isinstance(stmt, ast.ImportFrom) and stmt.level == 0 and stmt.module:
        # level > 0 means relative import
        yield Module(stmt.module), stmt


def _import_builtin(
    stmt: ast.AST, file: Path | str
) -> Iterable[tuple[Module, ast.AST]]:
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
            yield (
                Module(
                    f"{Path(file).as_posix()}:{stmt.lineno}:{stmt.col_offset} {id_}(...)",
                    raw=True,
                ),
                stmt,
            )


def _fq_call_name(stmt: ast.Call) -> str | None:
    """Get the fully qualified name of a function call, if possible."""
    func = stmt.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return f"{func.value.id}.{func.attr}"
    return None
