"""Main module for check_dependencies"""

from __future__ import annotations

import ast
import logging
from os.path import commonpath
from pathlib import Path
from typing import Generator, Iterator, Sequence

from check_dependencies.builtin_module import BUILTINS
from check_dependencies.lib import AppConfig, Dependency, PyProjectToml, pkg

logger = logging.getLogger("check_dependencies")
ERR_MISSING_DEPENDENCY = 2
ERR_EXTRA_DEPENDENCY = 4
ERR_NO_PYPROJECT = 8


def yield_wrong_imports(
    file_names: Sequence[str], app_cfg: AppConfig
) -> Generator[str, None, int]:
    """Yield output lines of missing/unused imports (or all imports in case of cfg.show_all)"""
    used_deps: set[str] = set()
    src_fmt = app_cfg.mk_src_formatter()
    try:
        pyproject_candidate = Path(
            commonpath(Path(p).expanduser().resolve() for p in file_names)
        )
    except ValueError as exc:
        logger.fatal("Could not find pyproject.toml in common path: %s", exc)
        return ERR_NO_PYPROJECT

    src_cfg = PyProjectToml.from_pyproject(pyproject_candidate, app_cfg=app_cfg)
    exit_status = 0

    expected_dependencies = frozenset().union(
        src_cfg.dependencies,  # dependencies from pyproject.toml
        BUILTINS,  # builtins
    )
    allowed_dependencies = frozenset().union(
        expected_dependencies, app_cfg.known_missing, src_cfg.known_missing
    )

    for src_pth in _collect_files(file_names):
        for cause, module, stmt in _missing_imports_iter(
            src_pth, dependencies=allowed_dependencies
        ):
            if cause != Dependency.OK:
                exit_status |= ERR_MISSING_DEPENDENCY
            used_deps.add(pkg(module))
            yield from src_fmt(src_pth, cause, module, stmt)

    if superfluous_requirements := [
        msg
        for dep in sorted(
            src_cfg.dependencies.difference(
                used_deps, app_cfg.known_extra, src_cfg.known_extra
            )
        )
        for msg in app_cfg.unused_fmt(dep)
    ]:
        exit_status |= ERR_EXTRA_DEPENDENCY
        if app_cfg.verbose:
            yield ""
            yield "### Dependencies in config file not used in application:"
            yield f"# Config file: {src_cfg.file}"
        yield from superfluous_requirements
    return exit_status


def _collect_files(file_names: Sequence[str]) -> Iterator[Path]:
    """
    Collect all Python files in a list of files or directories.
    Ensure no file is visited more than once
    """
    visited = set()
    for p in map(Path, file_names):
        for p_sub in p.rglob("*.py") if p.is_dir() else [p]:
            if (p_sub_resolved := p_sub.resolve()) in visited:
                continue
            visited.add(p_sub_resolved)
            yield p_sub


def _missing_imports_iter(
    file: Path, dependencies: set[str]
) -> Iterator[tuple[Dependency, str, ast.stmt]]:
    """
    Find missing imports in a Python file
    :param file: Pyton file to analyse
    :param dependencies: Declared dependencies from pyproject file
    :param seen: Cache of seen packages - this is changed during the iteration
    :yields: Tuple of status, module name and optional import statement
    """
    try:
        parsed = ast.parse(file.read_text(), filename=str(file))
    except SyntaxError as exc:
        logger.error("Could not parse %s: %s", file, exc)
        return
    for module, stmt in _imports_iter(parsed.body):
        pkg_ = pkg(module)
        status = Dependency.OK if pkg_ in dependencies else Dependency.NA
        yield status, module, stmt


def _imports_iter(body: list[ast.stmt]) -> Iterator[tuple[str, ast.stmt]]:
    """Yield all import statements from a body of code"""
    for x in body:
        if isinstance(x, ast.Import):
            for alias in x.names:
                yield alias.name, x  # yield x, not alias to get lineno
        elif isinstance(x, ast.ImportFrom) and x.level == 0:
            # level > 0 means relative import
            yield x.module or "", x
        elif hasattr(x, "body"):
            yield from _imports_iter(x.body)
