"""Parse project specific options (dependencies, config) from a pyproject.toml file."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from itertools import chain, takewhile
from os.path import commonpath
from pathlib import Path
from typing import Any, Collection, Mapping, TypeVar

from check_dependencies.lib import normalize_pkg

try:
    import tomllib  # type: ignore[import-not-found,unused-ignore]
except ImportError:  # pragma: no cover
    import toml as tomllib  # type: ignore[no-redef,import-not-found,unused-ignore]

__all__ = ["PyProjectToml", "tomllib"]
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
            msg = f"Error finding common path for {paths}: {exc}"
            raise ValueError(msg) from exc
        path = _get_pyproject_path(pyproject_candidate)

        return cls(
            cfg=tomllib.loads(path.read_text("utf-8")),
            path=path,
            include_dev=include_dev,
        )

    @property
    def dependencies(self) -> frozenset[str]:
        """Get dependencies from pyproject.toml file."""
        deps = set()
        is_used = False
        for dep_class in (
            Pep621Dependencies,
            PoetryDependencies,
            UvLegacyDependencies,
            HatchDependencies,
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
        pep631_name = normalize_pkg(_nested_item(self.cfg, "project.name", str) or "")
        poetry_name = normalize_pkg(
            _nested_item(self.cfg, "tool.poetry.name", str) or ""
        )
        return frozenset(
            filter(
                None,
                (
                    pep631_name,
                    poetry_name,
                    *_nested_item(
                        self.cfg,
                        "tool.check-dependencies.known-missing",
                        list,
                    ),
                ),
            ),
        )

    @property
    def known_extra(self) -> frozenset[str]:
        """Dependencies that are known to be unused in application."""
        return frozenset(
            _nested_item(self.cfg, "tool.check-dependencies.known-extra", list),
        )

    @property
    def provides(self) -> list[tuple[str, str]]:
        """Mapping from import name to package name.

        E.g. ``{"jwt": "pyjwt", "shapefile": "pyshp"}`` means that the package
        ``pyjwt`` is imported as ``jwt`` and ``pyshp`` as ``shapefile``.

        Values are normalized via :func:`normalize_pkg` so that e.g. ``PyJWT``,
        ``pyjwt``, and ``py-jwt`` all resolve to the same key.
        """
        return [
            (normalize_pkg(package), module)
            for package, modules in _nested_item(
                self.cfg, "tool.check-dependencies.provides", dict
            ).items()
            for module in ([modules] if isinstance(modules, str) else modules)
        ]


def _get_pyproject_path(path: Path) -> Path:
    """Get the pyproject.toml file by searching up the directory hierarchy.

    :param path: The starting path to search from.
    """
    for p in chain([path], path.resolve().parents):
        if (p / _PYPROJECT_TOML).exists():
            return p / _PYPROJECT_TOML
    msg = f"Could not find {_PYPROJECT_TOML} file within path hierarchy"
    raise FileNotFoundError(msg)


def _nested_item(obj: Mapping[str, Any], key: str, /, class_: type[_T]) -> _T:
    """Get items from a nested dictionary where the keys are dot-separated.

    :param key: The dot-separated key to look up in the nested dictionary.
    :param class_: The expected type of the value.
    :returns: The value corresponding to the key if found
        otherwise the default instance of the expected type.
    :raises TypeError: If the value found is not of the expected type.
    """
    for a in key.split("."):
        if a not in obj:
            return class_()
        obj = obj[a]
    if not isinstance(obj, class_):
        msg = f"Expected {class_} but got {type(obj)}"
        raise TypeError(msg)
    return obj


@dataclass(frozen=True)
class BaseDependency:
    """Base class for different dependency providers."""

    cfg: Mapping[str, Any]

    def is_used(self) -> bool:
        """Check if the pyproject.toml file contains this style of dependencies."""
        raise NotImplementedError  # pragma: no cover

    def dependencies(self, *, include_dev: bool) -> set[str]:
        """Get all dependencies.

        :arg include_dev: Whether to include dev dependencies.
        """
        deps = self._dependencies()
        if include_dev:
            deps.update(self._dev_dependencies())
        return deps

    def _dev_dependencies(self) -> set[str]:
        """Get development dependencies."""
        raise NotImplementedError  # pragma: no cover

    def _dependencies(self) -> set[str]:
        """Get production dependencies, with extras, but no development dependencies."""
        raise NotImplementedError  # pragma: no cover


@dataclass(frozen=True)
class Pep621Dependencies(BaseDependency):
    cfg: dict[str, Any]

    def is_used(self) -> bool:
        """Check if the pyproject.toml file contains PEP 621-style dependencies."""
        return "dependencies" in self.cfg.get("project", {})

    def _dependencies(self) -> set[str]:
        """Get dependencies from a PEP 621-style pyproject.toml file."""
        deps = _canonicals(_nested_item(self.cfg, "project.dependencies", list))

        for raw_extras in _nested_item(
            self.cfg, "project.optional-dependencies", dict
        ).values():
            deps.update(_canonicals(raw_extras))
        return deps

    def _dev_dependencies(self) -> set[str]:
        """Get the dev dependencies from a PEP 621-style pyproject.toml file."""
        groups = _nested_item(self.cfg, "dependency-groups", dict)
        return _canonicals(set().union(*groups.values()))

class PoetryDependencies(BaseDependency):
    def is_used(self) -> bool:
        """Check if the pyproject.toml file contains Poetry style dependencies."""
        return bool(_nested_item(self.cfg, "tool.poetry", dict))

    def _dependencies(self) -> set[str]:
        return set(_nested_item(self.cfg, "tool.poetry.dependencies", dict)) - {
            "python"
        }

    def _dev_dependencies(self) -> set[str]:
        # Get tool.poetry.group.*.dependencies
        # e.g. groups is "dev": {"dependencies": {"pytest": "^6.2.5"}}
        deps = set(_nested_item(self.cfg, "tool.poetry.dev-dependencies", dict))
        groups: dict[str, dict[str, dict[str, str]]] = _nested_item(
            self.cfg, "tool.poetry.group", dict
        )
        for group in groups.values():
            deps |= set(
                group.get("dependencies", []),
            )
        return deps


class UvLegacyDependencies(BaseDependency):
    cfg: dict[str, Any]

    def is_used(self) -> bool:
        return bool(_nested_item(self.cfg, "tool.uv", dict))

    def _dependencies(self) -> set[str]:
        return Pep621Dependencies(self.cfg).dependencies(include_dev=False)

    def _dev_dependencies(self) -> set[str]:
        return _canonicals(_nested_item(self.cfg, "tool.uv.dev-dependencies", dict))


class HatchDependencies(BaseDependency):
    def is_used(self) -> bool:
        return bool(_nested_item(self.cfg, "tool.hatch", dict))

    def _dependencies(self) -> set[str]:
        return _canonicals(
            _nested_item(self.cfg, "tool.hatch.envs.default.dependencies", list)
        )

    def _dev_dependencies(self) -> set[str]:
        return set().union(
            *(
                _canonicals(env_cfg.get("dependencies", []))
                for name, env_cfg in _nested_item(
                    self.cfg, "tool.hatch.envs", dict
                ).items()
                if name != "default"
            )
        )


def _canonicals(names: Collection[str]) -> set[str]:
    """Canonicalize package names."""
    return set(map(_canonical, names))


def _canonical(name: str) -> str:
    return "".join(takewhile(lambda x: x.isalnum() or x in "-_", name.strip())).replace(
        "-", "_"
    )
