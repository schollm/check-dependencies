"""Library for check_dependencies."""

from __future__ import annotations

import logging
from enum import Enum

logger = logging.getLogger("check_dependencies.lib")


class Dependency(Enum):
    """Possible dependency state."""

    NA = "!"  # Not Available
    EXTRA = "+"  # Extra dependency in config file
    OK = " "  # Correct import (declared in config file)


def pkg(module: str) -> str:
    """Get the installable module name from an import or package name statement."""
    return normalize_pkg(module.split(".", 1)[0])


def normalize_pkg(name: str) -> str:
    """Normalize a package name: lowercase and replace hyphens with underscores.

    This makes package name comparison case-insensitive and treats hyphens and
    underscores as equivalent, consistent with PEP 503 / PyPI conventions.
    E.g. ``scikit-learn``, ``scikit_learn``, and ``SciKit-Learn`` all normalize
    to ``scikit_learn``.
    """
    return name.lower().replace("-", "_")
