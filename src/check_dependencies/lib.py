"""Library for check_dependencies."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from functools import total_ordering
from itertools import groupby, takewhile
from operator import itemgetter
from typing import Iterable

logger = logging.getLogger("check_dependencies.lib")


class Dependency(Enum):
    """Possible dependency state."""

    NA = "!"  # Not Available
    EXTRA = "+"  # Extra dependency in config file
    OK = " "  # Correct import (declared in config file)
    FILE_ERROR = "!!"  # Error getting import statement (e.g. io error, syntax error)


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


@dataclass(frozen=True)
@total_ordering
class Package:
    """A single package with its original and canonical name for comparison.

    The original name is preserved for display purposes, while the canonical name is
    used for hashing and comparison, ensuring that different representations of the
    same package are treated as equal.

    Added advantage is that we now have a clear distinction between a module
    (presented as a string) and a package.
    """

    __slots__ = ["_original", "canonical"]
    _original: str
    canonical: str

    def __init__(self, package: str) -> None:
        """Initialize the Package dataclass."""
        object.__setattr__(self, "_original", package.strip())
        object.__setattr__(self, "canonical", _canonical(package))

    def __hash__(self) -> int:
        """Use only canonical name for hashing."""
        return hash(self.canonical)

    def __eq__(self, other: object) -> bool:
        """Compare with another package or a package name."""
        if isinstance(other, Package):
            return self.canonical == other.canonical
        if isinstance(other, str):
            return self.canonical == _canonical(other)
        return NotImplemented

    def __str__(self) -> str:
        """Get the Original name."""
        return self._original

    def __bool__(self) -> bool:
        """Check if there is a package (i.e. empty package name is Falsy)."""
        return bool(self.canonical)

    def __gt__(self, other: object) -> bool:
        """Compare with another package or a package name."""
        if isinstance(other, Package):
            return self.canonical > other.canonical
        if isinstance(other, str):
            return self.canonical > _canonical(other)
        return NotImplemented

    @classmethod
    def set(cls, package_names: Iterable[str]) -> set[Package]:
        """Get a set of packages from a package names."""
        return {cls(package_name) for package_name in package_names}


class Packages:
    """Translation layer to map between packages and modules."""

    _modules: dict[Package, set[str]]
    _packages: dict[str, set[Package]]

    def __init__(self, packages: list[tuple[Package, str]]) -> None:
        """Initialize the Packages dataclass.

        :param packages: List of (package, module) tuples, where package is the
            package name and module is the import name.
        """
        self._modules = {
            key: {module for _, module in val}
            for key, val in groupby(
                sorted(packages, key=itemgetter(0)), key=itemgetter(0)
            )
        }

        self._packages = {
            key: {pkg_ for pkg_, _ in val}
            for key, val in groupby(
                sorted(packages, key=itemgetter(1)), key=itemgetter(1)
            )
        }

    def modules(self, pkg_: str | Package) -> set[str]:
        """Get the modules (import name) for a given package name.

        :param pkg_: The package to look up.
        """
        if isinstance(pkg_, str):
            pkg_ = Package(pkg_)
        return self._modules.get(pkg_, {str(pkg_.canonical)})

    def packages(self, module_name: str) -> set[Package]:
        """Get the packages for a given module (import name).

        :param module_name: The module name (import name) to look up.
        """
        module_ = pkg(module_name)
        return self._packages.get(module_, {Package(module_)})


def _canonical(name: str) -> str:
    """Normalize a package name: lowercase and replace special chars with underscores.

    This makes package name comparison case-insensitive and treats hyphens and
    underscores as equivalent, consistent with PEP 503 / PyPI conventions.
    E.g. ``scikit-learn``, ``scikit_learn``, and ``SciKit-Learn`` all normalize
    to ``scikit_learn``.

    :param name: The package name to normalize.
    :returns: Normalized package name.
    """
    pkg_name_iter = takewhile(lambda x: x.isalnum() or x in "-_.", name.strip())
    package_name = "".join(pkg_name_iter)
    return package_name.lower().strip().replace("-", "_").replace(".", "_")
