"""Parse project specific options (dependencies, config) from a pyproject.toml file."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from itertools import chain, takewhile
from os.path import commonpath
from pathlib import Path
from typing import Any, Collection, TypeVar

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
        if "dependencies" in self.cfg.get("project", {}):
            return self._pep631_dependencies()
        if "poetry" in self.cfg.get("tool", {}):
            return self._poetry_dependencies()

        logger.warning("No dependencies found in %s", self.path)
        return frozenset()

    @property
    def known_missing(self) -> frozenset[str]:
        """Known to be used in application but not declared in requirements.

        This includes the project itself.
        """
        # Add project name
        pep631_name = normalize_pkg(self._nested_item("project.name", str) or "")
        poetry_name = normalize_pkg(self._nested_item("tool.poetry.name", str) or "")
        return frozenset(
            filter(
                None,
                (
                    pep631_name,
                    poetry_name,
                    *self._nested_item(
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
            self._nested_item("tool.check-dependencies.known-extra", list),
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
            for package, modules in self._nested_item(
                "tool.check-dependencies.provides", dict
            ).items()
            for module in ([modules] if isinstance(modules, str) else modules)
        ]

    def _poetry_dependencies(self) -> frozenset[str]:
        """Get dependencies from a poetry-style pyproject.toml file."""
        deps = set(self._nested_item("tool.poetry.dependencies", dict))
        if self.include_dev:
            deps |= set(
                self._nested_item("tool.poetry.group.dev.dependencies", dict),
            )
            deps |= set(self._nested_item("tool.poetry.dev-dependencies", dict))

        return frozenset(x for x in deps) - {"python"}

    def _pep631_dependencies(self) -> frozenset[str]:
        """Get dependencies from a PEP 631-style pyproject.toml file."""

        def canonical(name: str) -> str:
            return "".join(
                takewhile(lambda x: x.isalnum() or x in "-_", name.strip())
            ).replace("-", "_")

        deps = set(map(canonical, self._nested_item("project.dependencies", list)))
        for raw_extras in self._nested_item(
            "project.optional-dependencies", dict
        ).values():
            deps.update(map(canonical, raw_extras))
        if self.include_dev:
            deps.update(
                map(canonical, self._nested_item("tool.dev.dependencies", dict))
            )
        return frozenset(deps)

    def _nested_item(self, key: str, /, class_: type[_T]) -> _T:
        """Get items from a nested dictionary where the keys are dot-separated.

        :param key: The dot-separated key to look up in the nested dictionary.
        :param class_: The expected type of the value.
        :returns: The value corresponding to the key if found
            otherwise the default instance of the expected type.
        :raises TypeError: If the value found is not of the expected type.
        """
        obj = self.cfg
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
