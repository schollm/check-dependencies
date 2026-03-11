"""Application configuration and helper functions for check-dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import groupby
from operator import itemgetter
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Collection, Iterable, Iterator, Sequence

from check_dependencies.lib import Dependency, normalize_pkg, pkg
from check_dependencies.pyproject_toml import PyProjectToml

if TYPE_CHECKING:
    import ast


@dataclass()
class AppConfig:
    """Application config and helper functions."""

    known_extra: Collection[str]
    known_missing: Collection[str]
    provides: Packages
    dependencies: Collection[str]
    pyproject_file: Path | None = None
    include_dev: bool = False
    verbose: bool = False
    show_all: bool = False

    @classmethod
    def from_cli_args(  # noqa: PLR0913 (factory method)
        cls,
        *,
        file_names: Sequence[str],
        known_extra: str = "",
        known_missing: str = "",
        provides: Iterable[str] = (),
        include_dev: bool = False,
        verbose: bool = False,
        show_all: bool = False,
    ) -> AppConfig:
        """Create an AppConfig instance from CLI arguments.

        :file_names: List of file paths to analyze.
        :known_extra: Comma-separated list of known extra dependencies.
        :known_missing: Comma-separated list of known missing dependencies.
        :provides: Iterable of strings in the format "package=module" to specify
            provided modules.
        :include_dev: Whether to include development dependencies from pyproject.toml.
        :verbose: Whether to include detailed information in the output.
        :show_all: Whether to show all dependencies, including those that are OK.
        """
        provides_list: list[tuple[str, str]] = []
        for package, _, module in (
            map1.partition("=") for maps in provides for map1 in maps.split(",")
        ):
            if package.strip() and module.strip():
                provides_list.append((package.strip(), module.strip()))

        for file in file_names:
            if not Path(file).exists():
                raise FileNotFoundError(file)

        if not file_names:
            file_names = ["."]

        src_cfg = PyProjectToml.for_paths(file_names, include_dev=include_dev)

        def combine(*collections: Collection[str]) -> frozenset[str]:
            """Combine multiple collections, filtering empty strings.

            :params: Collections of strings to combine.
            """
            return frozenset(
                item.strip()
                for collection in collections
                for item in collection
                if item and item.strip()
            )

        return cls(
            include_dev=include_dev,
            verbose=verbose,
            show_all=show_all,
            known_extra=combine(known_extra.split(","), src_cfg.known_extra),
            known_missing=combine(known_missing.split(","), src_cfg.known_missing),
            provides=Packages([*provides_list, *src_cfg.provides]),
            dependencies=src_cfg.dependencies,
            pyproject_file=src_cfg.path,
        )

    def __post_init__(self) -> None:
        """Dataclass post init method to ensure sets are frozen."""
        self.known_extra = frozenset(filter(None, self.known_extra or ()))
        self.known_missing = frozenset(filter(None, self.known_missing or ()))

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
                location = f"{Path(src_pth).as_posix()}:{getattr(stmt, 'lineno', -1)}"
                if cause == Dependency.NA or self.show_all:
                    yield f"{cause.value}{cause.name} {location} {module}"
            elif (pkg_ := pkg(module)) not in cache:
                cache.add(pkg_)
                if cause == Dependency.NA or self.show_all:
                    yield f"{cause.value} {pkg_}"

        return src_cause_formatter

    def unused_fmt(self, module: str) -> Iterator[str]:
        """Formatter for unused but declared dependencies.

        :param module: The module name of the dependency.
        """
        name = Dependency.EXTRA.name if self.verbose else ""
        yield f"{Dependency.EXTRA.value}{name} {module}"


class Packages:
    """Translation layer to map between packages to modules."""

    _modules: dict[str, set[str]]
    _packages: dict[str, set[str]]

    def __init__(self, packages: list[tuple[str, str]]) -> None:
        """Initialize the Packages dataclass.

        :param packages: List of (package, module) tuples, where package is the
            package name and module is the import name.
        """
        packages = [(normalize_pkg(pkg_), module) for pkg_, module in packages]

        self._modules = {
            key: {module for _, module in val}
            for key, val in groupby(
                sorted(packages, key=itemgetter(0)), key=itemgetter(0)
            )
        }

        self._packages = {
            key: {pkg_ for pkg_, _ in val}
            for key, val in groupby(
                sorted(packages, key=itemgetter(1)), key=itemgetter(1)
            )
        }

    def modules(self, pkg_name: str) -> set[str]:
        """Get the modules (import name) for a given package name.

        :param pkg_name: The package name to look up.
        """
        pkg_ = normalize_pkg(pkg_name)
        return self._modules.get(pkg_, {pkg_})

    def packages(self, module_name: str) -> set[str]:
        """Get the packages for a given module (import name).

        :param module_name: The module name (import name) to look up.
        """
        module_ = pkg(module_name)
        return self._packages.get(module_, {normalize_pkg(module_)})
