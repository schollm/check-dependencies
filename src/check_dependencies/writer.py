"""Write/Update config file based on an existing environment."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from check_dependencies.provides import mappings_for_env

EXIT_SUCCESS, EXIT_VALUE_ERROR, EXIT_FAILURE = 0, 1, 2
try:
    import tomlkit
except ImportError as _exc:  # pragma: no cover
    print(f"{_exc}: Require group [write] to be installed.")  # noqa: T201
    raise SystemExit(1) from _exc

if TYPE_CHECKING:
    from collections.abc import MutableMapping


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
    provides = mappings_for_env(python)
    is_stdout = config_file.as_posix() == "-"

    cfg = _get_existing_config(config_file, is_stdout=is_stdout)
    _ensure_key("tool.check-dependencies.provides", cfg)
    cfg["tool"]["check-dependencies"]["provides"].update(provides)  # type: ignore[not-subscriptable]
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


def _ensure_key(key: str, doc: MutableMapping) -> None:
    """Ensure a key exists in a TOML document.

    Updates the document in-place!
    :param key: The key to update in dot-separated format.
    :param doc: The document to update.
    """
    for key1 in key.split("."):
        if key1 not in doc:
            doc[key1] = {}
        doc = doc[key1]


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
