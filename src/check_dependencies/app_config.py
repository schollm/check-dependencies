"""Application configuration and helper functions for check-dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from logging import getLogger
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Collection,
    Iterable,
    Iterator,
    Sequence,
)

from check_dependencies.lib import Dependency, Module, Package, Packages
from check_dependencies.pyproject_toml import ConfigToml, PyProjectToml

if TYPE_CHECKING:
    import ast


logger = getLogger(__name__)


@dataclass()
class AppConfig:
    """Application config and helper functions."""

    known_extra: Collection[Package]
    known_missing: Collection[Module]
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
        file_names: Sequence[Path],
        known_extra: Sequence[str] = (),
        known_missing: Sequence[str] = (),
        provides: Iterable[str] = (),
        include_dev: bool = False,
        verbose: bool = False,
        show_all: bool = False,
        includes: Sequence[Path] = (),
    ) -> AppConfig:
        """Create an AppConfig instance from CLI arguments.

        :file_names: List of file paths to analyze.
        :known_extra: List of known extra dependencies.
        :known_missing: List of known missing dependencies.
        :provides: Iterable of strings in the format "package=module" to specify
            provided modules.
        :include_dev: Whether to include development dependencies from pyproject.toml.
        :verbose: Whether to include detailed information in the output.
        :show_all: Whether to show all dependencies, including those that are OK.
        """
        provides_list: list[tuple[Package, Module]] = []
        for package_name, _, module in (map1.partition("=") for map1 in provides):
            if package_name.strip() and module.strip():
                provides_list.append((Package(package_name), Module(module)))

        src_cfg = PyProjectToml.for_paths(
            file_names or [Path()], include_dev=include_dev
        )

        def with_includes(
            current_path: Path, paths: Iterable[Path], seen: set[Path]
        ) -> Iterable[ConfigToml]:
            for pth in paths:
                if (res_pth := (current_path / pth).resolve()) not in seen:
                    seen.add(res_pth)
                    cfg = ConfigToml.for_path(res_pth)
                    yield cfg
                    yield from with_includes(res_pth.parent, cfg.includes, seen)
                else:
                    logger.debug("Already parsed: %s", res_pth)

        seen: set[Path] = set()
        cfgs = [
            *with_includes(Path(), includes, seen),
            *with_includes(src_cfg.path.parent, src_cfg.includes, seen),
        ]

        def cfg_of(key: str) -> Iterable[Any]:
            yield from getattr(src_cfg, key)
            for cfg in cfgs:
                yield from getattr(cfg, key)

        return cls(
            include_dev=include_dev,
            verbose=verbose,
            show_all=show_all,
            known_extra=frozenset(
                pkg
                for pkg in (*map(Package, known_extra), *cfg_of("known_extra"))
                if pkg.canonical
            ),
            known_missing=frozenset(
                Module(module)
                for module in (*known_missing, *cfg_of("known_missing"))
                if module.strip()
            ),
            provides=Packages([*provides_list, *cfg_of("provides")]),
            dependencies=src_cfg.dependencies,
            pyproject_file=src_cfg.path,
        )

    def __post_init__(self) -> None:
        """Dataclass post init method to ensure sets are frozen."""
        self.known_extra = frozenset(filter(None, self.known_extra or ()))
        self.known_missing = frozenset(filter(None, self.known_missing or ()))

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
