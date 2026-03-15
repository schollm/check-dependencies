"""Parse project specific options (dependencies, config) from a pyproject.toml file."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from itertools import chain
from os.path import commonpath
from pathlib import Path
from typing import Any, Collection, Mapping, TypeVar

from check_dependencies.lib import Module, Package

try:
    import tomllib  # type: ignore[unresolved-import]
except ImportError:  # pragma: no cover
    import toml as tomllib

logger = logging.getLogger(__name__)
_PYPROJECT_TOML = Path("pyproject.toml")
_T = TypeVar("_T")


@dataclass(frozen=True)
class PyProjectToml:
    """Project specific options (dependencies, config) from a pyproject.toml file."""

    cfg: dict[str, Any]
    path: Path
    include_dev: bool = False

    @classmethod
    def for_paths(
        cls, paths: Collection[str], *, include_dev: bool = False
    ) -> PyProjectToml:
        """Create a PyProjectToml instance from a pyproject.toml file.

        :param paths: List of file paths to analyze. The common parent directory
            will be searched for a pyproject.toml file.
        :param include_dev: Whether to include development dependencies
            from pyproject.toml.
        :returns: A PyProjectToml instance with the parsed configuration.
        """
        try:
            pyproject_candidate = Path(
                commonpath(Path(p).expanduser().resolve() for p in paths),
            )
        except ValueError as exc:
            # Can only be reached in Windows when two different drives are provided.
            msg = f"Error finding common path for {paths}: {exc}"
            raise ValueError(msg) from exc
        path = _get_pyproject_path(pyproject_candidate)

        return cls(
            cfg=tomllib.loads(path.read_text("utf-8")),
            path=path,
            include_dev=include_dev,
        )

    @property
    def dependencies(self) -> frozenset[Package]:
        """Get dependencies from pyproject.toml file."""
        deps: set[Package] = set()
        is_used = False
        for dep_class in (
            _Pep621Dependencies,
            _PoetryDependencies,
            _UvLegacyDependencies,
            _HatchDependencies,
        ):
            dep_cfg = dep_class(self.cfg)
            if dep_cfg.is_used():
                is_used = True
                deps |= dep_cfg.dependencies(include_dev=self.include_dev)
        if not is_used:
            msg = "No dependency management found"
            raise ValueError(msg)
        return frozenset(deps)

    @property
    def known_missing(self) -> frozenset[str]:
        """Known to be used in application but not declared in requirements.

        This includes the project itself.
        """
        # Add project name
        pep631_name = Package(_nested_item(self.cfg, "project.name", str) or "")
        poetry_name = Package(_nested_item(self.cfg, "tool.poetry.name", str) or "")
        return frozenset(
            filter(
                None,
                (
                    pep631_name.canonical,
                    poetry_name.canonical,
                    *_nested_item(
                        self.cfg,
                        "tool.check-dependencies.known-missing",
                        list,
                    ),
                ),
            ),
        )

    @property
    def known_extra(self) -> frozenset[Package]:
        """Dependencies that are known to be unused in application."""
        return frozenset(
            map(
                Package,
                _nested_item(self.cfg, "tool.check-dependencies.known-extra", list),
            )
        )

    @property
    def provides(self) -> list[tuple[Package, Module]]:
        """Mapping from import name to package name.

        E.g. ``{"jwt": "pyjwt", "shapefile": "pyshp"}`` means that the package
        ``pyjwt`` is imported as ``jwt`` and ``pyshp`` as ``shapefile``.

        Package keys are canonicalized via :class:`Package` (case-insensitive,
        hyphen/underscore equivalent), so e.g. ``PyJWT``, ``pyjwt``, and
        ``py-jwt`` resolve to the same package identity.
        """
        return [
            (Package(package), Module(module))
            for package, modules in _nested_item(
                self.cfg, "tool.check-dependencies.provides", dict
            ).items()
            for module in ([modules] if isinstance(modules, str) else modules)
        ]


@dataclass(frozen=True)
class _BaseDependency:
    """Base class for different dependency providers."""

    cfg: Mapping[str, Any]

    def is_used(self) -> bool:
        """Check if the pyproject.toml file contains this style of dependencies."""
        raise NotImplementedError  # pragma: no cover

    def dependencies(self, *, include_dev: bool) -> set[Package]:
        """Get all dependencies.

        :arg include_dev: Whether to include dev dependencies.
        """
        deps = self._dependencies()
        if include_dev:
            deps.update(self._dev_dependencies())
        return deps

    def _dev_dependencies(self) -> set[Package]:
        """Get development dependencies."""
        raise NotImplementedError  # pragma: no cover

    def _dependencies(self) -> set[Package]:
        """Get production dependencies, with extras, but no development dependencies."""
        raise NotImplementedError  # pragma: no cover


@dataclass(frozen=True)
class _Pep621Dependencies(_BaseDependency):
    """PEP-621 dependency provider."""

    def is_used(self) -> bool:
        """Check if the pyproject.toml file contains PEP 621-style dependencies."""
        return "dependencies" in self.cfg.get("project", {})

    def _dependencies(self) -> set[Package]:
        """Get dependencies from a PEP 621-style pyproject.toml file."""
        deps = Package.set(_nested_item(self.cfg, "project.dependencies", list))

        for raw_extras in _nested_item(
            self.cfg, "project.optional-dependencies", dict
        ).values():
            deps.update(Package.set(raw_extras))
        return deps

    def _dev_dependencies(self) -> set[Package]:
        """Get the dev dependencies from a PEP 621-style pyproject.toml file."""
        groups = _nested_item(self.cfg, "dependency-groups", dict)
        return set().union(*map(Package.set, groups.values()))


@dataclass(frozen=True)
class _PoetryDependencies(_BaseDependency):
    """Poetry Dependencies."""

    def is_used(self) -> bool:
        """Check if the pyproject.toml file contains Poetry style dependencies."""
        return bool(_nested_item(self.cfg, "tool.poetry", dict))

    def _dependencies(self) -> set[Package]:
        poetry_deps = dict(_nested_item(self.cfg, "tool.poetry.dependencies", dict))
        poetry_deps.pop("python", None)
        return Package.set(self._names_from_items(poetry_deps))

    def _dev_dependencies(self) -> set[Package]:
        # Get tool.poetry.group.*.dependencies
        # e.g. groups is "dev": {"dependencies": {"pytest": "^6.2.5"}}
        deps = Package.set(
            self._names_from_items(
                _nested_item(self.cfg, "tool.poetry.dev-dependencies", dict)
            )
        )
        groups: dict[str, dict[str, dict[str, str]]] = _nested_item(
            self.cfg, "tool.poetry.group", dict
        )
        for group in groups.values():
            deps |= Package.set(self._names_from_items(group.get("dependencies", {})))
        return deps

    @staticmethod
    def _names_from_items(items: dict[str, Any]) -> list[str]:
        """Get the package name from a Poetry dependency item."""
        return [f"{k} = {v!r}" for k, v in items.items()]


@dataclass(frozen=True)
class _UvLegacyDependencies(_BaseDependency):
    """uv (legacy) dependency manager."""

    def is_used(self) -> bool:
        """Check if uv is used."""
        return bool(_nested_item(self.cfg, "tool.uv", dict))

    def _dependencies(self) -> set[Package]:
        return _Pep621Dependencies(self.cfg).dependencies(include_dev=False)

    def _dev_dependencies(self) -> set[Package]:
        return Package.set(_nested_item(self.cfg, "tool.uv.dev-dependencies", dict))


@dataclass(frozen=True)
class _HatchDependencies(_BaseDependency):
    """Hatch Dependencies."""

    def is_used(self) -> bool:
        """Check if hatch is used in this project."""
        return bool(_nested_item(self.cfg, "tool.hatch", dict))

    def _dependencies(self) -> set[Package]:
        return Package.set(
            _nested_item(self.cfg, "tool.hatch.envs.default.dependencies", list)
        )

    def _dev_dependencies(self) -> set[Package]:
        return set().union(
            *(
                Package.set(env_cfg.get("dependencies", []))
                for name, env_cfg in _nested_item(
                    self.cfg, "tool.hatch.envs", dict
                ).items()
                if name != "default"
            )
        )


def _nested_item(obj: Mapping[str, Any], key: str, /, class_: type[_T]) -> _T:
    """Get items from a nested dictionary where the keys are dot-separated.

    :param key: The dot-separated key to look up in the nested dictionary.
    :param class_: The expected type of the value.
    :returns: The value corresponding to the key if found
        otherwise the default instance of the expected type.
    :raises TypeError: If the value found is not of the expected type or if any part of
        key is not a mapping.
    """
    for a in key.split("."):
        if a not in obj:
            return class_()
        obj = obj[a]
    if not isinstance(obj, class_):
        msg = f"Expected {class_} but got {type(obj)}"
        raise TypeError(msg)
    return obj


def _get_pyproject_path(path: Path) -> Path:
    """Get the pyproject.toml file by searching up the directory hierarchy.

    :param path: The starting path to search from.
    """
    for p in chain([path], path.resolve().parents):
        if (p / _PYPROJECT_TOML).exists():
            return p / _PYPROJECT_TOML
    msg = f"Could not find {_PYPROJECT_TOML} file within path hierarchy"
    raise FileNotFoundError(msg)
