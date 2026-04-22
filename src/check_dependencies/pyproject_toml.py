"""Parse project specific options (dependencies, config) from a pyproject.toml file."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from itertools import chain
from pathlib import Path
from typing import Any, Collection, Mapping, Sequence, TypeVar

from check_dependencies.lib import Module, Package, Packages

try:
    import tomllib  # ty:ignore[unresolved-import]
except ImportError:  # pragma: no cover
    import toml as tomllib

logger = logging.getLogger(__name__)
_PYPROJECT_TOML = Path("pyproject.toml")
_T = TypeVar("_T")

_INCLUDES_KEY = "tool.check-dependencies.includes"
_KNOWN_MISSING_KEY = "tool.check-dependencies.known-missing"
_KNOWN_EXTRA_KEY = "tool.check-dependencies.known-extra"
_PROVIDES_KEY = "tool.check-dependencies.provides"


@dataclass(frozen=True)
class ConfigToml:
    """Additional config for check-dependencies options. Useful for mono-repos."""

    cfg: dict[str, Any]
    includes_cfg: Sequence[ConfigToml]

    @classmethod
    def for_path(cls, path: Path, *, _seen: Collection[Path] = ()) -> ConfigToml:
        """Get a config from a path."""
        logger.debug("Parsing %s", path)
        cfg = tomllib.loads(path.read_text("utf-8"))
        return ConfigToml(
            cfg=cfg,
            includes_cfg=[
                cls.for_path(path=path.parent / p, _seen={*_seen, path})
                for p in _nested_item(cfg, _INCLUDES_KEY, list)
                if path.parent / p not in _seen
            ],
        )

    @property
    def known_missing(self) -> frozenset[Module]:
        """Known to be used in application but not declared in requirements."""
        return frozenset(
            chain(
                map(
                    Module,
                    _nested_item(self.cfg, _KNOWN_MISSING_KEY, list),
                ),
                chain.from_iterable(incl.known_missing for incl in self.includes_cfg),
            )
        )

    @property
    def known_extra(self) -> frozenset[Package]:
        """Dependencies that are known to be unused in application."""
        return frozenset(
            chain(
                map(
                    Package,
                    _nested_item(self.cfg, _KNOWN_EXTRA_KEY, list),
                ),
                chain.from_iterable(incl.known_extra for incl in self.includes_cfg),
            )
        )

    @property
    def provides(self) -> frozenset[tuple[Package, Module]]:
        """Mapping from import name to package name.

        E.g. ``[
            (Package("pyjwt"), Module("jwt")),
            (Package("pysh"), Module("shapefile"))
        ]``
        means that the package
        ``pyjwt`` is imported as ``jwt`` and ``pyshp`` as ``shapefile``.

        Package keys are canonicalized  (case-insensitive,
        hyphen/underscore equivalent), so e.g. ``PyJWT``, ``pyjwt``, and
        ``pyJwt`` resolve to the same package identity.
        """
        return frozenset(
            chain(
                (
                    (Package(package), Module(module))
                    for package, modules in _nested_item(
                        self.cfg, _PROVIDES_KEY, dict
                    ).items()
                    for module in ([modules] if isinstance(modules, str) else modules)
                ),
                chain.from_iterable(incl.provides for incl in self.includes_cfg),
            )
        )


@dataclass(frozen=True)
class PyProjectToml(ConfigToml):
    """Project specific options (dependencies, config) from a pyproject.toml file."""

    path: Path
    include_dev: bool = False

    @classmethod
    def for_path(
        cls, path: Path, *, include_dev: bool = False, _seen: Collection[Path] = ()
    ) -> PyProjectToml:
        """Create a PyProjectToml instance from a known pyproject.toml path.

        :param path: Absolute path to a pyproject.toml file.
        :param include_dev: Whether to include development dependencies.
        :returns: A PyProjectToml instance with the parsed configuration.
        """
        cfg = tomllib.loads(path.read_text("utf-8"))
        includes = [] if path in _seen else _nested_item(cfg, _INCLUDES_KEY, list)
        _seen = {*_seen, path}
        return cls(
            cfg=cfg,
            includes_cfg=[
                cls.for_path(path.parent / p, include_dev=include_dev, _seen=_seen)
                for p in includes
            ],
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
    def known_missing(self) -> frozenset[Module]:
        """Known to be used in application but not declared in requirements.

        This includes the project itself.
        """
        # Add project name
        packages = Packages([])
        pep631_name = Package(_nested_item(self.cfg, "project.name", str) or "")
        poetry_name = Package(_nested_item(self.cfg, "tool.poetry.name", str) or "")
        return frozenset(
            filter(
                lambda m: m.name,
                chain(
                    super().known_missing,
                    packages.modules(pep631_name),
                    packages.modules(poetry_name),
                ),
            ),
        )


@lru_cache(maxsize=None)
def get_pyproject_toml(path: Path) -> Path:
    """Return the pyproject.toml path for the given directory, with caching.

    Searches upward from *path* (which should be a directory, typically
    ``file.parent``) until a ``pyproject.toml`` is found.

    :param path: Directory to start searching from.
    :returns: Absolute path to the nearest ``pyproject.toml``.
    :raises FileNotFoundError: When no ``pyproject.toml`` is found in the hierarchy.

    This uses recursion and LRU caching to allow for efficient caching.
    """
    if (result := path / _PYPROJECT_TOML).exists():
        return result

    if path == path.parent:  # Exit recursion
        msg = f"Could not find {_PYPROJECT_TOML} file within path hierarchy"
        raise FileNotFoundError(msg)

    return get_pyproject_toml(path.parent)


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
