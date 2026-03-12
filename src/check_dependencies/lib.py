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
    FILE_ERROR = "!!"  # Error in import statement (e.g. syntax error)


def pkg(module: str) -> str:
    """Extract the top-level package name from a module import.

    **Examples:**
    >>> pkg("numpy.linalg")
    "numpy"
    >>> pkg("sklearn")
    "sklearn"
    >>> pkg("PIL.Image")
    "pil"

    :param module: Full module path (e.g., "package.submodule.module")
    :returns: Normalized top-level package name
    """
    return module.split(".", 1)[0].strip()


def normalize_pkg(name: str) -> str:
    """Normalize a package name: lowercase and replace dots and hyphens with underscores.

    This makes package name comparison case-insensitive and treats hyphens and
    underscores as equivalent, consistent with PEP 503 / PyPI conventions.
    E.g. ``scikit-learn``, ``scikit_learn``, and ``SciKit-Learn`` all normalize
    to ``scikit_learn``.

    :param name: The package name to normalize.
    :returns: Normalized package name.
    """
    return name.lower().strip().replace("-", "_").replace(".", "_")
