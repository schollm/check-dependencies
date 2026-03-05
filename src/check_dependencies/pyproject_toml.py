"""Parse project specific options (dependencies, config) from a pyproject.toml file."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from itertools import chain, takewhile
from os.path import commonpath
from pathlib import Path
from typing import Any, Collection

from check_dependencies.lib import nested_item, normalize_pkg, pkg

try:
    import tomllib
except ImportError:  # pragma: no cover
    import toml as tomllib  # type: ignore[no-redef]

logger = logging.getLogger(__name__)


_PYPROJECT_TOML = Path("pyproject.toml")


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
        """Create a PyProjectToml instance from a pyproject.toml file."""
        pyproject_candidate = Path(
            commonpath(Path(p).expanduser().resolve() for p in paths),
        )
        path = get_pyproject_path(pyproject_candidate)

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

        logger.warning("No dependencies found in %s", _PYPROJECT_TOML)
        return frozenset()

    @property
    def known_missing(self) -> frozenset[str]:
        """Known to be used in application but not declared in requirements.

        This includes the project itself.
        """
        # Add project name
        pep631_name = pkg(nested_item(self.cfg, "project.name", str) or "")
        poetry_name = pkg(nested_item(self.cfg, "tool.poetry.name", str) or "")
        return frozenset(
            filter(
                None,
                (
                    pep631_name,
                    poetry_name,
                    *nested_item(
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
            nested_item(self.cfg, "tool.check-dependencies.known-extra", list),
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
            (normalize_pkg(k), v)
            for k, v_lst in nested_item(
                self.cfg, "tool.check-dependencies.provides", dict
            ).items()
            for v in ([v_lst] if isinstance(v_lst, str) else v_lst)
        ]

    def _poetry_dependencies(self) -> frozenset[str]:
        """Get dependencies from a poetry-style pyproject.toml file."""
        deps = set(nested_item(self.cfg, "tool.poetry.dependencies", dict))
        if self.include_dev:
            deps |= set(
                nested_item(self.cfg, "tool.poetry.group.dev.dependencies", dict),
            )
            deps |= set(nested_item(self.cfg, "tool.poetry.dev-dependencies", dict))

        return frozenset(x for x in deps) - {"python"}

    def _pep631_dependencies(self) -> frozenset[str]:
        """Get dependencies from a PEP 631-style pyproject.toml file."""

        def canonical(name: str) -> str:
            return "".join(takewhile(lambda x: x.isalnum() or x in "-_", name)).replace(
                "-",
                "_",
            )

        raw_deps = nested_item(self.cfg, "project.dependencies", list)
        deps = {canonical(raw_dep) for raw_dep in raw_deps}
        for raw_extras in nested_item(
            self.cfg,
            "project.optional-dependencies",
            dict,
        ).values():
            deps |= {canonical(raw_extra) for raw_extra in raw_extras}
        return frozenset(deps)


def get_pyproject_path(path: Path) -> Path:
    """Get the pyproject.toml file by searching up the directory hierarchy."""
    for p in chain([path], path.resolve().parents):
        if (p / _PYPROJECT_TOML).exists():
            return p / _PYPROJECT_TOML
    msg = f"Could not find {_PYPROJECT_TOML} file within path hierarchy"
    raise FileNotFoundError(msg)
