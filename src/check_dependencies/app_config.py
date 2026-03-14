"""Application configuration and helper functions for check-dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Callable,
    Collection,
    Iterable,
    Iterator,
    Sequence,
)

from check_dependencies.lib import Dependency, Package, Packages, main_module
from check_dependencies.pyproject_toml import PyProjectToml

if TYPE_CHECKING:
    import ast


@dataclass()
class AppConfig:
    """Application config and helper functions."""

    known_extra: Collection[Package]
    known_missing: Collection[str]
    provides: Packages
    dependencies: Collection[Package]
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
        provides_list: list[tuple[Package, str]] = []
        for package_name, _, module in (
            map1.partition("=") for maps in provides for map1 in maps.split(",")
        ):
            if package_name.strip() and module.strip():
                provides_list.append((Package(package_name), module.strip()))

        if not file_names:
            file_names = ["."]

        src_cfg = PyProjectToml.for_paths(file_names, include_dev=include_dev)

        return cls(
            include_dev=include_dev,
            verbose=verbose,
            show_all=show_all,
            known_extra=frozenset(
                pkg
                for pkg in (*Package.set(known_extra.split(",")), *src_cfg.known_extra)
                if pkg.canonical
            ),
            known_missing=frozenset(
                module.strip()
                for module in (*known_missing.split(","), *src_cfg.known_missing)
                if module.strip()
            ),
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
    ) -> Callable[[str, Dependency, str, ast.AST | None], Iterator[str]]:
        """Formatter for missing or used dependencies."""
        cache: set[str] = set()

        def src_cause_formatter(
            src_pth: str,
            cause: Dependency,
            module: str,
            stmt: ast.AST | None,
        ) -> Iterator[str]:
            if self.verbose:
                location = f"{Path(src_pth).as_posix()}:{getattr(stmt, 'lineno', -1)}"
                if cause in (Dependency.NA, Dependency.FILE_ERROR) or self.show_all:
                    yield f"{cause.value}{cause.name} {location} {module}"
            elif cause == Dependency.FILE_ERROR:
                yield f"{cause.value} {src_pth}"
            elif (pkg_ := main_module(module)) not in cache:
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
