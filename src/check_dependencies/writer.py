"""Write/Update config file based on an existing environment."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from check_dependencies.provides import collect_mappings, mappings_for_env

try:
    # tomlkit is used for writing because it preserves formatting and comments,
    #  but it is not a strict requirement for check_dependencies main function.
    import tomlkit
except ImportError as _exc:
    # Emit a warning and exit with a non-zero status code if tomlkit is not installed,
    # since it's required for the writer functionality.
    sys.stderr.write(f"{_exc}: Require group [write] to be installed.\n")
    raise SystemExit(1) from _exc

if TYPE_CHECKING:
    from collections.abc import MutableMapping

EXIT_SUCCESS, EXIT_VALUE_ERROR, EXIT_FAILURE = 0, 1, 2


def main() -> int:
    """Provide the main entry point for writer."""
    args = _get_arg_parser().parse_args()
    try:
        _update_config(Path(args.config), Path(args.python))
    except ValueError as exc:
        print(exc, file=sys.stderr)  # noqa: T201
        return EXIT_VALUE_ERROR

    except Exception as exc:  # noqa:BLE001  # pragma: no cover
        print(exc, file=sys.stderr)  # noqa: T201
        return EXIT_FAILURE
    return EXIT_SUCCESS


def _get_arg_parser() -> argparse.ArgumentParser:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--python",
        "-p",
        help="Python executable to check.",
        required=True,
    )
    parser.add_argument(
        "--config", "-c", help="Location of toml config file.", type=Path, required=True
    )
    return parser


def _update_config(config_file: Path, python: Path) -> None:
    provides = collect_mappings(mappings_for_env(python))
    is_stdout = config_file.as_posix() == "-"

    cfg = _get_existing_config(config_file, is_stdout=is_stdout)

    _ensure_key(cfg)
    cfg["tool"]["check-dependencies"]["provides"].update(provides)
    dumps = tomlkit.dumps(cfg)
    if is_stdout:
        print(dumps)  # noqa: T201
    else:
        config_file.write_text(dumps, encoding="utf-8")


def _get_existing_config(config_file: Path, *, is_stdout: bool) -> tomlkit.TOMLDocument:
    if is_stdout or not config_file.exists():
        return tomlkit.TOMLDocument()

    try:
        content = config_file.read_text("utf-8")
    except (OSError, PermissionError) as exc:
        msg = f"{exc}: --config file must be a readable file"
        raise ValueError(msg) from exc

    return tomlkit.parse(content)


def _ensure_key(cfg: MutableMapping) -> None:
    """Ensure ``tool.check-dependencies.provides`` exists in a TOML document.

    Updates the document in-place.
    :param cfg: The document to update.
    """
    if "tool" not in cfg:
        cfg["tool"] = {}
    if "check-dependencies" not in cfg["tool"]:
        cfg["tool"]["check-dependencies"] = {}
    if "provides" not in cfg["tool"]["check-dependencies"]:
        cfg["tool"]["check-dependencies"]["provides"] = {}


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
