"""Application configuration and helper functions for check-dependencies."""

from __future__ import annotations

import argparse
import enum
import textwrap
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
from itertools import chain
from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from check_dependencies.builtin_module import BUILTINS
from check_dependencies.lib import Module, Package, Packages
from check_dependencies.provides import mappings_for_env
from check_dependencies.pyproject_toml import ConfigToml, PyProjectToml

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Iterable, Iterator, Sequence

    from check_dependencies.outputs import Output, SeenT

logger = getLogger(__name__)
_T = TypeVar("_T")
_DIST_NAME = "check-dependencies"


class OutputFormat(enum.Enum):
    """Output format for check-dependencies."""

    GITHUB = "github"
    FULL = "full"
    CONCISE = "concise"


@dataclass(frozen=True)
class AppConfig:
    """Application config and helper functions."""

    file_names: Sequence[Path]
    known_extra: Sequence[Package] = ()
    known_missing: Sequence[Module] = ()
    provides: Packages = field(default_factory=Packages)
    include_dev: bool = False
    verbose: bool = False
    output_format: OutputFormat = OutputFormat.CONCISE

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
        includes: Sequence[Path] = (),
        provides_from_venv: Path | None = None,
        output_format: OutputFormat = OutputFormat.CONCISE,
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
            output_format=output_format,
        )

    @classmethod
    def from_argv(cls, sysv: list[str] | None = None) -> AppConfig:
        """Construct an AppConfig from sys.argv or a provided list of arguments."""
        parser = argparse.ArgumentParser(
            description="Find undeclared and unused (or all) imports in Python files",
            add_help=True,
            formatter_class=argparse.RawTextHelpFormatter,
        )
        parser.add_argument(
            "--version",
            action="version",
            version=f"%(prog)s {_get_version()}",
        )
        parser.add_argument(
            "file_name",
            type=Path,
            nargs="+",
            help="Python Source file to analyse",
        )
        parser.add_argument(
            "--include-dev",
            action="store_true",
            default=False,
            help="Include dev dependencies",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            default=False,
            help="Show every import of a package",
        )
        parser.add_argument(
            "--provides-from-venv",
            metavar="PYTHON_EXECUTABLE",
            type=Path,
            help="Path to the virtual environment's Python executable\n"
            "(for example, .venv/bin/python) to include all packages\n"
            "installed in it as provides.",
        )
        parser.add_argument(
            "--missing",
            type=str,
            action=_MultiSepAction,
            metavar="MODULE,...",
            default=[],
            help=textwrap.dedent("""\
            Comma separated list of requirements known to be missing.

            Assume they are part of the requirements.
            Can be specified multiple times.
            Toml Key: [tool.check-dependencies] known-missing=[]
            """),
        )
        parser.add_argument(
            "--extra",
            type=str,
            action=_MultiSepAction,
            metavar="PACKAGE,...",
            default=[],
            help=textwrap.dedent("""\
            Comma separated list of requirements known to not be imported.

            Assume they are not part of the requirements. This can be plugins or
            similar that affect the package but are not imported explicitly.
            Can be specified multiple times.
            Toml Key: [tool.check-dependencies] known-extra=[]
            """),
        )
        parser.add_argument(
            "--provides",
            type=str,
            action=_MultiSepAction,
            default=[],
            metavar="PACKAGE=MODULE,...",
            help=textwrap.dedent("""\
            Map a package name to its module (import) name for packages whose import
            name differs from the package name. Can be specified multiple times.

            E.g. --provides Pillow=PIL --provides PyJWT=jwt.
            The package name is normalized (case-insensitive, hyphens and underscores
            are equivalent), so Pillow=PIL, pillow=PIL and PIL-ow=PIL are all the same.
            Toml Key: [tool.check-dependencies.provides]"""),
        )
        parser.add_argument(
            "--include",
            "-I",
            type=Path,
            action="append",
            default=[],
            help=textwrap.dedent("""\
            Additional config files to include.
            Can be specified multiple times. E.g. --include check-dependencies.toml.
            Toml Key: [tool.check-dependencies] includes=[]
            """),
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="(Deprecated) Show all imports (including correct ones). "
            "Use --output-format full.",
        )
        full, concise, github = (
            OutputFormat.FULL.value,
            OutputFormat.CONCISE.value,
            OutputFormat.GITHUB.value,
        )
        parser.add_argument(
            "--output-format",
            type=OutputFormat,
            help=textwrap.dedent(f"""\
            The format to use for printing diagnostic messages

            Possible values:
            - {full}:     Print all imports, including correct ones.
            - {concise}:  Print only problematic imports (missing or extra)
            - {github}:   Print only problematic imports in a format suitable
                for GitHub Actions annotations
            """),
            default=OutputFormat.CONCISE,
        )
        args = parser.parse_args(sysv)
        if args.all and args.output_format == OutputFormat.CONCISE:
            logger.warning("--all is deprecated, use --output-format full instead.")
            args.output_format = OutputFormat.FULL

        return AppConfig.from_cli_args(
            file_names=args.file_name,
            known_extra=args.extra,
            known_missing=args.missing,
            provides=args.provides,
            include_dev=args.include_dev,
            verbose=args.verbose,
            includes=args.include,
            provides_from_venv=args.provides_from_venv,
            output_format=args.output_format,
        )

    def mk_formatter(self) -> Callable[[Output], Iterator[str]]:
        """Format outputs."""
        if self.output_format == OutputFormat.GITHUB:

            def formatter(output: Output) -> Iterator[str]:
                yield from output.as_github()

            return formatter
        return self._mk_text_formatter()

    def _mk_text_formatter(self) -> Callable[[Output], Iterator[str]]:
        seen = set()

        def formatter(output: Output) -> Iterator[str]:
            yield from self.text_formatter(output, seen=seen)

        return formatter

    def text_formatter(self, output: Output, seen: SeenT) -> Iterator[str]:
        """Return a formatter function for the given output type."""
        yield from output.to_text(
            verbose=self.verbose,
            show_all=self.output_format == OutputFormat.FULL,
            seen=seen,
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


class _MultiSepAction(argparse.Action):
    """Custom argparse action to split comma-separated values into a list.

    This action allows the user to specify multiple values for an argument by
    separating them with commas. Each time the argument is encountered,
    the values are split and added to a list in the namespace.

    E.g. `--extra foo,bar --extra baz` will result in
    `namespace.extra == ['foo', 'bar', 'baz']`.
    """

    def __init__(
        self,
        option_strings: list[str],
        dest: str,
        nargs: str | None = None,
        type: type | None = None,  # noqa: A002
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        """Initialize MultiSepAction."""
        if nargs is not None:
            msg = "nargs not allowed"
            raise ValueError(msg)
        if type not in (str, None):
            msg = "type: Only support str"
            raise ValueError(msg)
        super().__init__(option_strings, dest, type=type, **kwargs)

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | Sequence | None,
        option_string: str | None = None,
    ) -> None:
        """Set provided argument on namespace."""
        del parser, option_string
        if not isinstance(values, str):
            msg = f"expected a string, got {type(values).__name__}"
            raise TypeError(msg)
        # namespace.(dest) is None on first call:
        existing: list[str] = getattr(namespace, self.dest, None) or []
        setattr(namespace, self.dest, [*existing, *values.split(",")])


def _get_version() -> str:
    """Return the installed package version."""
    try:
        return version(_DIST_NAME)
    except PackageNotFoundError:
        return "unknown"
