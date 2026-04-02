"""CLI entry point for check_dependencies."""

import argparse
import logging
import sys

from check_dependencies.app_config import AppConfig
from check_dependencies.main import yield_wrong_imports


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
        "check_dependencies",
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
        help="Comma separated list of requirements known to be missing."
        " Assume they are part of the requirements.",
        default="",
    )
    parser.add_argument(
        "--extra",
        type=str,
        help="Comma separated list of requirements known to not be imported."
        " Assume they are not part of the requirements. This can be plugins or similar"
        " that affect the package but are not imported explicitly.",
        default="",
    )
    parser.add_argument(
        "--provides",
        type=str,
        action="append",
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


if __name__ == "__main__":
    main()  # pragma: no cover
