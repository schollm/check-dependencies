"""
Library for check_dependencies
"""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, List, Optional, Sequence, cast

import toml

logger = logging.getLogger("check_dependencies.lib")


class Dependency(Enum):
    """Possible depdendency state"""

    NA = "!"  # Not Available
    EXTRA = "+"  # Extra dependency in config file
    OK = " "  # Correct import (declared in config file)


@dataclass()
class Config:
    """Application config and helper functions"""

    file: Optional[str] = None
    include_dev: bool = False
    verbose: bool = False
    show_all: bool = False
    extra_requirements: Sequence[str] = ()
    ignore_requirements: Sequence[str] = ()

    def __post_init__(self) -> None:
        self.extra_requirements = list(filter(None, self.extra_requirements or []))
        self.ignore_requirements = list(filter(None, self.ignore_requirements or []))
        if self.file and Path(self.file).is_dir():
            self.file = (Path(self.file) / "pyproject.toml").as_posix()
        if self.file:
            try:
                cfg = toml.load(Path(self.file))
            except FileNotFoundError:
                logger.fatal("Could not find config file: %s. Set to None", self.file)
                raise

            extra_cfg = _nested_item(cfg, "tool.check_dependencies.extra-requirements")
            self.extra_requirements += cast(List[str], list(extra_cfg or []))

            ignore_cfg = _nested_item(
                cfg, "tool.check_dependencies.ignore-requirements"
            )
            self.ignore_requirements += cast(List[str], list(ignore_cfg))
        else:
            logger.info("Config file unset, showing all imports")
            self.show_all = True
            self.include_dev = False
            self.include_dev = False
            self.ignore_requirements = ()
            self.extra_requirements = ()

    def get_declared_dependencies(self) -> set[str]:
        """
        Get dependencies from pyproject.toml file.
        ! Currently only poetry style dependencies are supported
        """
        if not self.file:
            return set()
        if (cfg_pth := Path(self.file)).is_dir():
            cfg_pth /= "pyproject.toml"
        try:
            cfg = toml.load(cfg_pth)
        except FileNotFoundError:
            return set()

        deps = set(_nested_item(cfg, "tool.poetry.dependencies"))
        if self_name := _nested_item(cfg, "tool.poetry.name"):
            cast(List[str], self.extra_requirements).append(_canonical_pkg(self_name))
        if self.include_dev:
            deps |= set(_nested_item(cfg, "tool.poetry.group.dev.dependencies"))
            deps |= set(_nested_item(cfg, "tool.poetry.dev-dependencies"))
        return {_canonical_pkg(x) for x in deps} - {"python"}

    def mk_src_formatter(
        self,
    ) -> Callable[[str, Dependency, str, Optional[ast.stmt]], Optional[str]]:
        """Formatter for missing or used dependencies"""
        cache: set[str] = set()

        def src_cause_formatter(
            file: str, cause: Dependency, module: str, stmt: Optional[ast.stmt]
        ) -> Optional[str]:
            if not self.file:
                if self.verbose:
                    location = f"{file}:{getattr(stmt, 'lineno', -1)}"
                    return f"{location} {module}"
                if (pkg_ := pkg(module)) not in cache:
                    cache.add(pkg_)
                    return pkg_
            if self.verbose:
                location = f"{file}:{getattr(stmt, 'lineno', -1)}"
                cause_str = f"{cause.value}{cause.name}" if self.file else ""
                if self.show_all or not self.file or cause == Dependency.NA:
                    return f"{cause_str} {location} {module}"
            else:
                if (pkg_ := pkg(module)) not in cache:
                    cache.add(pkg_)
                    cause_str = cause.value if self.file else " "
                    if self.show_all or not self.file or cause == Dependency.NA:
                        return f"{cause_str} {pkg_}"
            return None

        return src_cause_formatter

    def mk_unused_formatter(self) -> Callable[[str], Optional[str]]:
        """Formatter for unused but declared dependencies"""

        def unused_formatter(module: str) -> Optional[str]:
            if not self.file:
                return None
            if self.verbose:
                return f"{Dependency.EXTRA.value}{Dependency.EXTRA.name} {module}"
            return f"{Dependency.EXTRA.value} {module}"

        return unused_formatter


def pkg(module: str) -> str:
    """Get the installable module name from an import statement"""
    return module.split(".")[0]


def _nested_item(obj: dict[str, Any], keys: str) -> Any:
    """Get items from a nested dictionary where the keys are dot-separated"""
    for a in keys.split("."):
        obj = obj.get(a, {})
    return obj


def _canonical_pkg(name: str) -> str:
    return name.replace("-", "_")
