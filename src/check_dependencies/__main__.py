"""CLI entry point for check_dependencies."""

from __future__ import annotations

import argparse
import logging
import sys
import textwrap
from argparse import RawTextHelpFormatter
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import TYPE_CHECKING, Any

from check_dependencies.app_config import AppConfig
from check_dependencies.main import yield_outputs

if TYPE_CHECKING:
    from collections.abc import Sequence


_DIST_NAME = "check-dependencies"
_writer = sys.stdout.write


def _get_version() -> str:
    """Return the installed package version."""
    try:
        return version(_DIST_NAME)
    except PackageNotFoundError:
        return "unknown"


def main() -> int:
    """CLI entry point for check_dependencies."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(filename)s: "
        "%(levelname)-8s: "
        "%(funcName)s(): "
        "%(lineno)d:\t"
        "%(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Find undeclared and unused (or all) imports in Python files",
        add_help=True,
        formatter_class=RawTextHelpFormatter,
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
        "--all",
        action="store_true",
        default=False,
        help="Show all imports (including correct ones)",
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
        help="Comma separated list of requirements known to be missing."
        " Assume they are part of the requirements."
        "\n Can be specified multiple times."
        "\n Toml Key: [tool.check-dependencies] known-missing=[]",
    )
    parser.add_argument(
        "--extra",
        type=str,
        action=_MultiSepAction,
        metavar="PACKAGE,...",
        default=[],
        help="Comma separated list of requirements known to not be imported."
        "\nAssume they are not part of the requirements. This can be plugins or similar"
        "\nthat affect the package but are not imported explicitly."
        "\nCan be specified multiple times."
        "\nToml Key: [tool.check-dependencies] known-extra=[]",
    )
    parser.add_argument(
        "--provides",
        type=str,
        action=_MultiSepAction,
        default=[],
        metavar="PACKAGE=MODULE,...",
        help="Map a package name to its module (import) name for packages whose import"
        "\nname differs from the package name. Can be specified multiple times."
        "\nE.g. --provides Pillow=PIL --provides PyJWT=jwt."
        "\nThe package name is normalized (case-insensitive, hyphens and underscores"
        "\nare equivalent), so Pillow=PIL, pillow=PIL and PIL-ow=PIL are all the same."
        "\nToml Key: [tool.check-dependencies.provides]",
    )
    parser.add_argument(
        "--include",
        "-I",
        type=Path,
        action="append",
        default=[],
        help="Additional config files to include."
        "\nCan be specified multiple times. E.g. --include check-dependencies.toml."
        "\nToml Key: [tool.check-dependencies] includes=[]",
    )
    parser.add_argument(
        "--output-format",
        type=str,
        help=textwrap.dedent("""\
            The format to use for printing diagnostic messages

            Possible values:
            - full:     Print all imports, including correct ones (default if --all
                        is specified)
            - concise:  Print only problematic imports (missing or extra)
            - github:   Print only problematic imports in a format suitable for GitHub
                        Actions annotations
            """),
        default="concise",
    )

    args = parser.parse_args()

    app_cfg = AppConfig.from_cli_args(
        file_names=args.file_name,
        known_extra=args.extra,
        known_missing=args.missing,
        provides=args.provides,
        include_dev=args.include_dev,
        verbose=args.verbose,
        show_all=args.all,
        includes=args.include,
        provides_from_venv=args.provides_from_venv,
        output_format=args.output_format,
    )

    outputs = yield_outputs(app_cfg)
    formatter = app_cfg.mk_formatter()
    exit_code = 0
    for output in outputs:
        for line in formatter(output):
            _writer(line)
            _writer("\n")
        exit_code |= output.exit_code
    return exit_code


class _MultiSepAction(argparse.Action):
    def __init__(
        self,
        option_strings: list[str],
        dest: str,
        nargs: None | str = None,
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
        existing = getattr(namespace, self.dest, None) or []
        if not isinstance(values, str):
            msg = f"expected a string, got {type(values).__name__}"
            raise TypeError(msg)
        for value in values.split(","):
            existing.append(value)
        setattr(namespace, self.dest, existing)


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
