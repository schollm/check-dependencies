"""Library for check_dependencies."""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, TypeVar

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


T = TypeVar("T")


def nested_item(obj: dict[str, Any], keys: str, class_: type[T]) -> T:
    """Get items from a nested dictionary where the keys are dot-separated."""
    for a in keys.split("."):
        if a not in obj:
            return class_()
        obj = obj[a]
    if not isinstance(obj, class_):
        msg = f"Expected {class_} but got {type(obj)}"
        raise TypeError(msg)
    return obj
