"""Application configuration and helper functions for check-dependencies."""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import chain
from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING, Collection, TypeVar

from check_dependencies.builtin_module import BUILTINS
from check_dependencies.lib import Dependency, Module, Package, Packages
from check_dependencies.provides import mappings_for_env
from check_dependencies.pyproject_toml import ConfigToml, PyProjectToml

if TYPE_CHECKING:
    import ast
    from collections.abc import Callable, Iterable, Iterator, Sequence


logger = getLogger(__name__)


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
    includes: Sequence[Path] = ()

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

        _T = TypeVar("_T")

        def chained(iter_: Iterable[Iterable[_T]]) -> set[_T]:
            return set(chain.from_iterable(iter_))

        known_extra_incl = chained(inc.known_extra for inc in includes_cfg)
        known_missing_incl = chained(inc.known_missing for inc in includes_cfg)
        provides_incl = chained(inc.provides for inc in includes_cfg)
        return cls(
            file_names=file_names,
            known_extra=sorted(known_extra_incl.union(map(Package, known_extra))),
            known_missing=sorted(known_missing_incl.union(map(Module, known_missing))),
            provides=Packages(
                provides_incl.union(_get_provides(provides, provides_from_venv))
            ),
            include_dev=include_dev,
            verbose=verbose,
            show_all=show_all,
            includes=includes,
        )

    def mk_src_formatter(
        self,
    ) -> Callable[[str, Dependency, Module, ast.AST | None], Iterator[str]]:
        """Formatter for missing or used dependencies."""
        cache: set[Module] = set()

        def src_cause_formatter(
            src_pth: str,
            cause: Dependency,
            module: Module,
            stmt: ast.AST | None,
        ) -> Iterator[str]:
            if self.verbose:
                if (
                    cause in (Dependency.NA, Dependency.FILE_ERROR, Dependency.UNKNOWN)
                    or self.show_all
                ):
                    location = (
                        f"{Path(src_pth).as_posix()}:{getattr(stmt, 'lineno', -1)}"
                    )
                    yield f"{cause.value}{cause.name} {location} {module.name}"
            elif cause == Dependency.FILE_ERROR:
                yield f"{cause.value} {src_pth}"
            elif module.raw:
                if cause in (Dependency.NA, Dependency.UNKNOWN) or self.show_all:
                    yield f"{cause.value} {module.name}"
            elif (pkg_ := module.main) not in cache:
                cache.add(pkg_)
                if cause == Dependency.NA or self.show_all:
                    yield f"{cause.value} {pkg_.name}"

        return src_cause_formatter

    def unused_fmt(self, module: str) -> Iterator[str]:
        """Formatter for unused but declared dependencies.

        :param module: The module name of the dependency.
        """
        name = Dependency.EXTRA.name if self.verbose else ""
        yield f"{Dependency.EXTRA.value}{name} {module}"


@dataclass
class ProjectConfig:
    """Project dependencies and related config."""

    known_missing: Collection[Module]
    defined_dependencies: Collection[Package]
    allowed_dependencies: Collection[Package]
    known_extra: Collection[Package]
    packages: Packages
    src_formatter: Callable[[str, Dependency, Module, ast.AST | None], Iterator[str]]
    path: Path

    @classmethod
    def from_config(cls, app_cfg: AppConfig, pyproject: PyProjectToml) -> ProjectConfig:
        """Initialize an empty ProjectDependencies instance."""
        packages = app_cfg.provides | Packages(pyproject.provides)

        allowed_dependencies = chain.from_iterable(
            [
                pyproject.dependencies,
                app_cfg.known_extra,
                pyproject.known_extra,
                map(Package, BUILTINS),
                [Package(m.name) for m in pyproject.known_missing],
            ]
        )

        known_missing = frozenset([*app_cfg.known_missing, *pyproject.known_missing])

        return cls(
            known_missing=known_missing,
            defined_dependencies=frozenset(pyproject.dependencies),
            allowed_dependencies=frozenset(allowed_dependencies),
            known_extra=frozenset({*app_cfg.known_extra, *pyproject.known_extra}),
            packages=packages,
            src_formatter=app_cfg.mk_src_formatter(),
            path=pyproject.path,
        )


def _get_provides(
    provides: Iterable[str], provides_from_venv: Path | None
) -> Iterable[tuple[Package, Module]]:
    """Parse the provides argument and collect provides from a virtual environment."""
    return [
        (Package(pkg.strip()), Module(mod.strip()))
        for pkg, sep, mod in chain(
            (map1.partition("=") for map1 in provides),
            ((str(pkg), "=", str(mod)) for pkg, mod in mappings_for_env(provides_from_venv)),
        )
        if sep and pkg.strip() and mod.strip()
    ]
