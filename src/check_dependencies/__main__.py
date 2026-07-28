"""CLI entry point for check_dependencies."""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

from check_dependencies.app_config import AppConfig
from check_dependencies.main import yield_outputs

if TYPE_CHECKING:
    from collections.abc import Iterable

_logger = logging.getLogger("check_dependencies.__main__")


def _writer(lines: Iterable[str]) -> None:
    for line in lines:
        sys.stdout.write(line)
        sys.stdout.write("\n")


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
    app_cfg = AppConfig.from_argv()
    formatter = app_cfg.mk_formatter()
    outputs = yield_outputs(app_cfg)
    exit_code = 0
    for output in outputs:
        _writer(formatter(output))
        exit_code |= output.exit_code
    return exit_code


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
