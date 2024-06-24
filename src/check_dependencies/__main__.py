"""CLI entry point for check_dependencies."""

import argparse
import logging
import sys

from check_dependencies.lib import Config
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
    "--config-file",
    type=str,
    required=False,
    default="",
    help="Location of pyproject.toml file, can be file or a directory"
    " containing pyproject.toml file",
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
    "--extra",
    type=str,
    help="Comma seperated list of extra requirements."
    " Assume they are part of the requirements",
    default="",
)
parser.add_argument(
    "--ignore",
    type=str,
    help="Comma seperated list of requirements to ignore."
    " Assume they are not part of the requirements",
    default="",
)
args = parser.parse_args()

cfg = Config(
    file=args.config_file,
    include_dev=args.include_dev,
    verbose=args.verbose,
    show_all=args.all,
    extra_requirements=args.extra.split(","),
    ignore_requirements=args.ignore.split(","),
)

wrong_import_lines = yield_wrong_imports(args.file_name, cfg)
try:
    while True:
        print(next(wrong_import_lines))
except StopIteration as ex:  # Return value is the exit status
    sys.exit(ex.value)
