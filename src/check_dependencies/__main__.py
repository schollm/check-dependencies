"""CLI entry point for check_dependencies."""

from __future__ import annotations

import argparse
import logging
import sys
from typing import TYPE_CHECKING, Any

from check_dependencies.app_config import AppConfig
from check_dependencies.main import yield_wrong_imports

if TYPE_CHECKING:
    from collections.abc import Sequence

def main() -> None:
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
    )

    parser.add_argument(
        "file_name",
        type=str,
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
        "--missing",
        type=str,
        action=_MultiSepAction,
        metavar="MODULE",
        default=[],
        help="Comma separated list of requirements known to be missing."
        " Assume they are part of the requirements.",
    )
    parser.add_argument(
        "--extra",
        type=str,
        action=_MultiSepAction,
        metavar="PACKAGE",
        default=[],
        help="Comma separated list of requirements known to not be imported."
        " Assume they are not part of the requirements. This can be plugins or similar"
        " that affect the package but are not imported explicitly.",
    )
    parser.add_argument(
        "--provides",
        type=str,
        action=_MultiSepAction,
        default=[],
        metavar="PACKAGE=IMPORT",
        help="Map a package name to its import name for packages whose import name"
        " differs from the package name. Can be specified multiple times."
        " E.g. --provides Pillow=PIL --provides PyJWT=jwt."
        " The package name is normalized (case-insensitive, hyphens and underscores"
        " are equivalent), so Pillow=PIL, pillow=PIL and PIL-ow=PIL are all the same.",
    )
    parser.add_argument(
        "--include",
        "-I",
        type=str,
        action="append",
        default=[],
        help="Additional config files to include."
        " Can be specified multiple times. E.g. --include check-dependencies.toml.",
    )
    args = parser.parse_args()

    cfg = AppConfig.from_cli_args(
        file_names=args.file_name,
        known_extra=args.extra,
        known_missing=args.missing,
        provides=args.provides,
        include_dev=args.include_dev,
        verbose=args.verbose,
        show_all=args.all,
        includes=args.include,
    )
    wrong_import_lines = yield_wrong_imports(args.file_name, cfg)
    try:
        while True:
            print(next(wrong_import_lines))  # noqa: T201
    except StopIteration as ex:  # Return value is the exit status
        sys.exit(ex.value)


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
    main()  # pragma: no cover
