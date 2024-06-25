"""
Library for check_dependencies
"""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass
from enum import Enum
from itertools import chain, takewhile
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

import toml

logger = logging.getLogger("check_dependencies.lib")
_PYPROJECT_TOML = Path("pyproject.toml")


class Dependency(Enum):
    """Possible depdendency state"""

    NA = "!"  # Not Available
    EXTRA = "+"  # Extra dependency in config file
    OK = " "  # Correct import (declared in config file)


@dataclass()
class AppConfig:
    """Application config and helper functions"""

    include_dev: bool = False
    verbose: bool = False
    show_all: bool = False
    known_extra: set[str] = frozenset()
    known_missing: set[str] = frozenset()

    def __post_init__(self) -> None:
        self.known_extra = frozenset(filter(None, self.known_extra or []))
        self.known_missing = frozenset(filter(None, self.known_missing or []))

    def mk_src_formatter(
        self,
    ) -> Callable[[str, Dependency, str, Optional[ast.stmt]], Optional[str]]:
        """Formatter for missing or used dependencies"""
        cache: set[str] = set()

        def src_cause_formatter(
            src_pth: Path, cause: Dependency, module: str, stmt: Optional[ast.stmt]
        ) -> Iterator[str]:
            if self.verbose:
                location = f"{src_pth}:{getattr(stmt, 'lineno', -1)}"
                if cause == Dependency.NA or self.show_all:
                    yield f"{cause.value}{cause.name} {location} {module}"
            else:
                if (pkg_ := pkg(module)) not in cache:
                    cache.add(pkg_)
                    if cause == Dependency.NA or self.show_all:
                        yield f"{cause.value} {pkg_}"

        return src_cause_formatter

    def unused_fmt(self, module: str) -> Iterator[str]:
        """Formatter for unused but declared dependencies"""
        info = Dependency.EXTRA.name if self.verbose else ""
        yield f"{Dependency.EXTRA.value}{info} {module}"


@dataclass(frozen=True)
class PyProjectToml:
    """Get project specific options (dependencies, config) from a pyproject.toml file."""

    file: Path
    cfg: dict[str, Any]
    include_dev: bool = False

    @classmethod
    def from_pyproject(cls, file: Path, app_cfg: AppConfig):
        """Create a PyProjectToml instance from a pyproject.toml file."""
        pyproject_file = _get_pyproject_path(file)
        return cls(
            file=pyproject_file,
            cfg=toml.load(pyproject_file),
            include_dev=app_cfg.include_dev,
        )

    @property
    def dependencies(self) -> frozenset[str]:
        """Get dependencies from pyproject.toml file."""
        if "dependencies" in self.cfg.get("project", {}):
            return self._pep631_dependencies()
        if "poetry" in self.cfg.get("tool", {}):
            return self._poetry_dependencies()

        logger.warning("No dependencies found in %s", _PYPROJECT_TOML)
        return frozenset()

    @property
    def known_missing(self) -> frozenset[str]:
        """
        Dependencies that are known to be used in application but not declared in
        requirements
        """
        # Add project name
        pep631_name = pkg(_nested_item(self.cfg, "project.name") or "")
        poetry_name = pkg(_nested_item(self.cfg, "tool.poetry.name") or "")
        return frozenset(
            filter(
                None,
                [
                    *(pep631_name, poetry_name),
                    *_nested_item(self.cfg, "tool.check-dependencies.known-missing"),
                ],
            )
        )

    @property
    def known_extra(self) -> frozenset[str]:
        """dependencies that are known to be unused in application"""
        return frozenset(_nested_item(self.cfg, "tool.check-dependencies.known-extra"))

    def _poetry_dependencies(self) -> frozenset[str]:
        """Get dependencies from a poetry-style pyproject.toml file"""
        deps = set(_nested_item(self.cfg, "tool.poetry.dependencies"))
        if self.include_dev:
            deps |= set(_nested_item(self.cfg, "tool.poetry.group.dev.dependencies"))
            deps |= set(_nested_item(self.cfg, "tool.poetry.dev-dependencies"))

        return frozenset(x for x in deps) - {"python"}

    def _pep631_dependencies(self) -> frozenset[str]:
        """Get dependencies from a PEP 631-style pyproject.toml file"""

        def canonical(name: str) -> str:
            return "".join(takewhile(lambda x: x.isalnum() or x in "-_", name)).replace(
                "-", "_"
            )

        raw_deps = _nested_item(self.cfg, "project.dependencies")
        deps = {canonical(raw_dep) for raw_dep in raw_deps}
        for _, raw_extras in _nested_item(
            self.cfg, "project.optional-dependencies"
        ).items():
            deps |= {canonical(raw_extra) for raw_extra in raw_extras}
        return frozenset(deps)


def pkg(module: str) -> str:
    """Get the installable module name from an import or package name statement"""
    return module.split(".")[0].replace("-", "_")


def _nested_item(obj: dict[str, Any], keys: str) -> Any:
    """Get items from a nested dictionary where the keys are dot-separated"""
    for a in keys.split("."):
        obj = obj.get(a, {})
    return obj


def _get_pyproject_path(path: Path):
    for p in chain([path], path.resolve().parents):
        if (p / _PYPROJECT_TOML).exists():
            return p / _PYPROJECT_TOML
    raise FileNotFoundError(
        f"Could not find {_PYPROJECT_TOML} file within path hierarchy"
    )
