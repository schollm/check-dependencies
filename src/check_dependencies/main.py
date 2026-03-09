"""Main module for check_dependencies."""

from __future__ import annotations

import ast
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from check_dependencies.builtin_module import BUILTINS
from check_dependencies.lib import Dependency

if TYPE_CHECKING:
    from collections.abc import Collection, Generator, Iterator

    from check_dependencies.app_config import AppConfig, Packages

logger = logging.getLogger("check_dependencies")
ERR_MISSING_DEPENDENCY = 2
ERR_EXTRA_DEPENDENCY = 4
ERR_NO_PYPROJECT = 8


def yield_wrong_imports(
    file_names: Collection[str],
    app_cfg: AppConfig,
) -> Generator[str, None, int]:
    """Yield output lines of missing/unused imports.

    If cfg.show_all is True, all imports are shown.
    """
    used_deps: set[str] = set()
    src_fmt = app_cfg.mk_src_formatter()
    exit_status = 0

    expected_dependencies = frozenset().union(
        app_cfg.dependencies,  # dependencies from pyproject.toml
        app_cfg.known_extra,
        BUILTINS,  # builtins
    )
    provides = app_cfg.provides
    allowed_dependencies: frozenset[str] = frozenset().union(
        expected_dependencies,
        app_cfg.known_missing,
    )

    for src_pth in _project_files(file_names):
        for cause, module, stmt in _missing_imports_iter(
            src_pth,
            dependencies=allowed_dependencies,
            provides=provides,
        ):
            if cause not in (Dependency.OK, Dependency.FILE_ERROR):
                exit_status |= ERR_MISSING_DEPENDENCY
            if cause != Dependency.FILE_ERROR:
                used_deps |= provides.packages(module)
            yield from src_fmt(src_pth, cause, module, stmt)

    if superfluous_requirements := [
        msg
        for dep in sorted(
            set(app_cfg.dependencies).difference(used_deps, app_cfg.known_extra),
        )
        for msg in app_cfg.unused_fmt(dep)
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
    dependencies: Collection[str],
    provides: Packages,
) -> Iterator[tuple[Dependency, str, ast.stmt]]:
    """Find missing imports in a Python file.

    :param file: Pyton file to analyze
    :param dependencies: Declared dependencies from pyproject file
    :yields: Tuple of status, module name and optional import statement
    """
    try:
        parsed = ast.parse(file.read_bytes(), filename=file.as_posix())
    except (SyntaxError, OSError, PermissionError):
        logger.exception("Could not parse %s", file)
        yield Dependency.FILE_ERROR, file.as_posix(), ast.Raise(lineno=-1)
        return
    for module, stmt in _imports_iter(parsed.body):
        pkg_ = provides.packages(module)
        status = Dependency.OK if pkg_.intersection(dependencies) else Dependency.NA
        yield status, module, stmt


def _imports_iter(body: list[ast.stmt]) -> Iterator[tuple[str, ast.stmt]]:
    """Yield all import statements from a body of code."""
    try:
        iter(body)
    except TypeError:
        # not iterable, so return empty
        return

    for x in body:
        if isinstance(x, ast.Import):
            for alias in x.names:
                yield alias.name, x  # yield x, not alias to get lineno
        elif isinstance(x, ast.ImportFrom) and x.level == 0 and x.module:
            # level > 0 means relative import
            yield x.module, x
        elif hasattr(x, "body"):
            for f in x._fields:
                yield from _imports_iter(getattr(x, f))
