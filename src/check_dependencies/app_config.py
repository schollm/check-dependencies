"""Application configuration and helper functions for check-dependencies."""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import chain
from logging import getLogger
from typing import TYPE_CHECKING, TypeVar

from check_dependencies.builtin_module import BUILTINS
from check_dependencies.lib import Module, Package, Packages
from check_dependencies.provides import mappings_for_env
from check_dependencies.pyproject_toml import ConfigToml, PyProjectToml

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Iterable, Iterator, Sequence
    from pathlib import Path

    from check_dependencies.outputs import Output, SeenT

logger = getLogger(__name__)
_T = TypeVar("_T")


@dataclass(frozen=True)
class AppConfig:
    """Application config and helper functions."""

    file_names: Sequence[Path]
    known_extra: Sequence[Package] = ()
    known_missing: Sequence[Module] = ()
    provides: Packages = field(default_factory=Packages)
    include_dev: bool = False
    verbose: bool = False
    show_all: bool = False

    @classmethod
    def from_cli_args(  # noqa: PLR0913
        cls,
        *,
        file_names: Sequence[Path],
        known_extra: Sequence[str] = (),
        known_missing: Sequence[str] = (),
        provides: Iterable[str] = (),
        include_dev: bool = False,
        verbose: bool = False,
        show_all: bool = False,
        includes: Sequence[Path] = (),
        provides_from_venv: Path | None = None,
    ) -> AppConfig:
        """Construct an AppConfig from CLI arguments."""
        includes_cfg = [ConfigToml.for_path(incl) for incl in includes]

        def chained(
            iter_: Iterable[Iterable[_T]], additional: Iterable[_T] = ()
        ) -> list[_T]:
            return sorted({x for sub_iter in iter_ for x in sub_iter}.union(additional))

        return cls(
            file_names=file_names,
            known_extra=chained(
                (inc.known_extra for inc in includes_cfg),
                (
                    pkg
                    for name in known_extra
                    if (pkg := Package(name.strip())).canonical
                ),
            ),
            known_missing=chained(
                (inc.known_missing for inc in includes_cfg),
                (
                    module
                    for name in known_missing
                    if (module := Module(name.strip())).name
                ),
            ),
            provides=Packages(
                known_packages=(),
                packages=chained(
                    (inc.provides for inc in includes_cfg),
                    _get_provides(provides, provides_from_venv),
                ),
            ),
            include_dev=include_dev,
            verbose=verbose,
            show_all=show_all,
        )

    def mk_formatter(self) -> Callable[[Output], Iterator[str]]:
        """Format outputs."""
        seen = set()

        def formatter(output: Output) -> Iterator[str]:
            yield from self.text_formatter(output, seen=seen)

        return formatter

    def text_formatter(self, output: Output, seen: SeenT) -> Iterator[str]:
        """Return a formatter function for the given output type."""
        yield from output.to_text(
            verbose=self.verbose, show_all=self.show_all, seen=seen
        )


@dataclass(frozen=True)
class ProjectConfig:
    """Project dependencies and related config."""

    known_missing: Collection[Module]
    defined_dependencies: Collection[Package]
    allowed_dependencies: Collection[Package]
    known_extra: Collection[Package]
    packages: Packages
    path: Path

    @classmethod
    def from_config(cls, app_cfg: AppConfig, pyproject: PyProjectToml) -> ProjectConfig:
        """Initialize an empty ProjectDependencies instance."""
        return cls(
            known_missing=frozenset([*app_cfg.known_missing, *pyproject.known_missing]),
            defined_dependencies=frozenset(pyproject.dependencies),
            allowed_dependencies=frozenset(
                chain.from_iterable(
                    [
                        pyproject.dependencies,
                        app_cfg.known_extra,
                        pyproject.known_extra,
                        map(Package, BUILTINS),
                        (Package(m.name) for m in pyproject.known_missing),
                    ]
                )
            ),
            known_extra=frozenset({*app_cfg.known_extra, *pyproject.known_extra}),
            packages=app_cfg.provides
            | Packages(pyproject.dependencies, pyproject.provides),
            path=pyproject.path,
        )


def _get_provides(
    provides: Iterable[str], provides_from_venv: Path | None
) -> Iterable[tuple[Package, Module]]:
    """Parse the provides argument and collect provides from a virtual environment."""
    return [
        (Package(pkg.strip()), Module(mod.strip()))
        for pkg, sep, mods in chain(
            (map1.partition("=") for map1 in provides),
            (
                (str(pkg), "=", str(mod))
                for pkg, mod in mappings_for_env(provides_from_venv)
            ),
        )
        for mod in mods.split(",")
        if sep and pkg.strip() and mod.strip()
    ]
