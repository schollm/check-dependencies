"""CLI entry point for check_dependencies."""

import argparse
import logging
import sys

from check_dependencies.lib import AppConfig
from check_dependencies.main import yield_wrong_imports

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
    "file_name", type=str, nargs="+", help="Python Source file to analyse"
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
    help="Comma seperated list of requirements known to be missing."
    " Assume they are part of the requirements",
    default="",
)
parser.add_argument(
    "--extra",
    type=str,
    help="Comma seperated list of requirements known to not be imported."
    " Assume they are not part of the requirements",
    default="",
)
args = parser.parse_args()

cfg = AppConfig(
    include_dev=args.include_dev,
    verbose=args.verbose,
    show_all=args.all,
    known_extra=set(args.extra.split(",")),
    known_missing=set(args.missing.split(",")),
)

wrong_import_lines = yield_wrong_imports(args.file_name, cfg)
try:
    while True:
        print(next(wrong_import_lines))
except StopIteration as ex:  # Return value is the exit status
    sys.exit(ex.value)
