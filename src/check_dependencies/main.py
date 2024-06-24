"""Main module for check_dependencies"""

from __future__ import annotations

import ast
import logging
from pathlib import Path
from typing import Generator, Iterator, Sequence

from check_dependencies.builtin_module import BUILTINS
from check_dependencies.lib import Config, Dependency, pkg

logger = logging.getLogger("check_dependencies")


def yield_wrong_imports(
    file_names: Sequence[str], cfg: Config
) -> Generator[str, None, int]:
    """Yield output lines of missing/unused imports (or all imports in case of cfg.show_all)"""
    declared_deps = cfg.get_declared_dependencies()
    used_deps: set[str] = set()
    missing_fmt = cfg.mk_src_formatter()
    exit_status = 0
    for file_name in _collect_files(file_names):
        for cause, module, stmt in _missing_imports_iter(
            Path(file_name),
            declared_deps | BUILTINS | set(cfg.extra_requirements),
            seen=used_deps,
        ):
            if cause != Dependency.OK:
                exit_status |= 2
            used_deps.add(pkg(module))
            if f := missing_fmt(file_name, cause, module, stmt):
                yield f

    if cfg.file:
        unused_fmt = cfg.mk_unused_formatter()
        errs = [
            err
            for dep in sorted(declared_deps - used_deps - set(cfg.ignore_requirements))
            if (err := unused_fmt(dep))
        ]
        if errs:
            exit_status |= 4
            if cfg.verbose:
                yield ""
                yield "### Dependencies in config file not used in application:"
                yield f"# Config file: {cfg.file}"
            yield from errs
    return exit_status


def _collect_files(file_names: Sequence[str]) -> Iterator[str]:
    """
    Collect all Python files in a list of files or directories.
    Ensure no file is visited more than once
    """
    seen = set()
    for p in map(Path, file_names):
        if (p_resolved := p.resolve()) in seen:
            continue
        seen.add(p_resolved)
        if p.is_dir():
            for p_sub in p.rglob("*.py"):
                if (p_sub_resolved := p_sub.resolve()) in seen:
                    continue
                seen.add(p_sub_resolved)
                yield p_sub.as_posix()
        else:
            yield p.as_posix()


def _missing_imports_iter(
    file: Path, dependencies: set[str], seen: set[str]
) -> Iterator[tuple[Dependency, str, ast.stmt]]:
    """
    Find missing imports in a Python file
    :param file: Pyton file to analyse
    :param dependencies: Declared dependencies
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
        seen.add(pkg_)
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
