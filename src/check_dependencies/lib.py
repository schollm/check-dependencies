"""Library for check_dependencies."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from itertools import chain, takewhile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, TypeVar, cast

import toml

if TYPE_CHECKING:
    import ast
    from collections.abc import Iterable, Iterator


logger = logging.getLogger("check_dependencies.lib")
_PYPROJECT_TOML = Path("pyproject.toml")


class Dependency(Enum):
    """Possible dependency state."""

    NA = "!"  # Not Available
    EXTRA = "+"  # Extra dependency in config file
    OK = " "  # Correct import (declared in config file)


@dataclass()
class AppConfig:
    """Application config and helper functions."""

    include_dev: bool = False
    verbose: bool = False
    show_all: bool = False
    known_extra: Iterable[str] = frozenset()
    known_missing: Iterable[str] = frozenset()

    def __post_init__(self) -> None:
        """Dataclass post init method to ensure sets are frozen."""
        self.known_extra = frozenset(filter(None, self.known_extra or []))
        self.known_missing = frozenset(filter(None, self.known_missing or []))

    def mk_src_formatter(
        self,
    ) -> Callable[[Path | str, Dependency, str, ast.stmt | None], Iterator[str]]:
        """Formatter for missing or used dependencies."""
        cache: set[str] = set()

        def src_cause_formatter(
            src_pth: Path | str,
            cause: Dependency,
            module: str,
            stmt: ast.stmt | None,
        ) -> Iterator[str]:
            if self.verbose:
                location = f"{src_pth}:{getattr(stmt, 'lineno', -1)}"
                if cause == Dependency.NA or self.show_all:
                    yield f"{cause.value}{cause.name} {location} {module}"
            elif (pkg_ := pkg(module)) not in cache:
                cache.add(pkg_)
                if cause == Dependency.NA or self.show_all:
                    yield f"{cause.value} {pkg_}"

        return src_cause_formatter

    def unused_fmt(self, module: str) -> Iterator[str]:
        """Formatter for unused but declared dependencies."""
        info = Dependency.EXTRA.name if self.verbose else ""
        yield f"{Dependency.EXTRA.value}{info} {module}"


@dataclass(frozen=True)
class PyProjectToml:
    """Project specific options (dependencies, config) from a pyproject.toml file."""

    file: Path
    cfg: dict[str, Any]
    include_dev: bool = False

    @classmethod
    def from_pyproject(cls, file: Path, app_cfg: AppConfig) -> PyProjectToml:
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
        """Known to be used in application but not declared in requirements."""
        # Add project name
        pep631_name = pkg(_nested_item(self.cfg, "project.name", str) or "")
        poetry_name = pkg(_nested_item(self.cfg, "tool.poetry.name", str) or "")
        return frozenset(
            filter(
                lambda x: x,
                [
                    pep631_name,
                    poetry_name,
                    *_nested_item(
                        self.cfg,
                        "tool.check-dependencies.known-missing",
                        list,
                    ),
                ],
            ),
        )

    @property
    def known_extra(self) -> frozenset[str]:
        """Dependencies that are known to be unused in application."""
        return frozenset(
            _nested_item(self.cfg, "tool.check-dependencies.known-extra", list),
        )

    def _poetry_dependencies(self) -> frozenset[str]:
        """Get dependencies from a poetry-style pyproject.toml file."""
        deps = set(_nested_item(self.cfg, "tool.poetry.dependencies", dict))
        if self.include_dev:
            deps |= set(
                _nested_item(self.cfg, "tool.poetry.group.dev.dependencies", dict),
            )
            deps |= set(_nested_item(self.cfg, "tool.poetry.dev-dependencies", dict))

        return frozenset(x for x in deps) - {"python"}

    def _pep631_dependencies(self) -> frozenset[str]:
        """Get dependencies from a PEP 631-style pyproject.toml file."""

        def canonical(name: str) -> str:
            return "".join(takewhile(lambda x: x.isalnum() or x in "-_", name)).replace(
                "-",
                "_",
            )

        raw_deps = _nested_item(self.cfg, "project.dependencies", list)
        deps = {canonical(raw_dep) for raw_dep in raw_deps}
        for raw_extras in _nested_item(
            self.cfg,
            "project.optional-dependencies",
            dict,
        ).values():
            deps |= {canonical(raw_extra) for raw_extra in raw_extras}
        return frozenset(deps)


def pkg(module: str) -> str:
    """Get the installable module name from an import or package name statement."""
    return module.split(".")[0].replace("-", "_")


T = TypeVar("T")


def _nested_item(obj: dict[str, Any], keys: str, class_: type[T]) -> T:
    """Get items from a nested dictionary where the keys are dot-separated."""
    for a in keys.split("."):
        if a not in obj:
            return class_()
        obj = obj[a]
    if not isinstance(obj, class_):
        msg = f"Expected {class_} but got {type(obj)}"
        raise TypeError(msg)
    return cast(T, obj)


def _get_pyproject_path(path: Path) -> Path:
    for p in chain([path], path.resolve().parents):
        if (p / _PYPROJECT_TOML).exists():
            return p / _PYPROJECT_TOML
    msg = f"Could not find {_PYPROJECT_TOML} file within path hierarchy"
    raise FileNotFoundError(msg)
