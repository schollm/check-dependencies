"""Library for check_dependencies."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from functools import total_ordering
from itertools import groupby, takewhile
from operator import itemgetter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable

logger = logging.getLogger("check_dependencies.lib")


class Dependency(Enum):
    """Possible dependency state."""

    NA = "!"  # Not Available
    EXTRA = "+"  # Extra dependency in config file
    OK = " "  # Correct import (declared in config file)
    UNKNOWN = "?"  # Unknown import (e.g. dynamic import)
    FILE_ERROR = "!!"  # Error getting import statement (e.g. io error, syntax error)


@dataclass(frozen=True)
@total_ordering
class Module:
    """Describe an imported Module."""

    name: str
    raw: bool = False

    def __post_init__(self) -> None:
        """Initialize the Module."""
        object.__setattr__(self, "name", self.name.strip())

    def __hash__(self) -> int:
        """Hash based on the module name."""
        return hash((self.name, self.raw))

    def __eq__(self, other: object) -> bool:
        """Compare with another module."""
        if not isinstance(other, Module):
            return NotImplemented
        return (self.name, self.raw) == (other.name, other.raw)

    def __gt__(self, other: object) -> bool:
        """Compare with another module."""
        if isinstance(other, Module):
            if self.raw != other.raw:
                return self.raw > other.raw
            return self.name > other.name
        return NotImplemented

    def __repr__(self) -> str:
        """Get the string representation of the Module."""
        if self.raw:
            return f"Module({self.name!r}, raw={self.raw!r})"
        return f"Module({self.name!r})"

    @property
    def parents(self) -> list[Module]:
        """Get the parent modules of the current module.

        **Examples:**
        >>> Module("numpy.linalg").parents
        [Module("numpy.linalg"), Module("numpy")]
        >>> Module("sklearn").parents
        [Module("sklearn")]
        >>> Module("PIL.Image").parents
        [Module("PIL.Image"), Module("PIL")]

        :returns: A list of parent modules.
        """
        if self.raw:
            return [self]
        parts = self.name.split(".")
        return [Module(".".join(parts[:i])) for i in range(len(parts), 0, -1)]


@dataclass(frozen=True)
@total_ordering
class Package:
    """A single package with its original and canonical name for comparison.

    The original name is preserved for display purposes, while the canonical name is
    used for hashing and comparison, ensuring that different representations of the
    same package are treated as equal.
    """

    __slots__ = ("_original", "canonical")
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

    def __repr__(self) -> str:
        """Get the string representation of the Package."""
        return f"Package({self._original!r})"

    @classmethod
    def set(cls, package_names: Iterable[str]) -> __builtins__.set[Package]:
        """Get a set of packages from a package names."""
        return {cls(package_name) for package_name in package_names}


class Packages:
    """Translation layer to map between packages and modules."""

    _modules: dict[Package, set[Module]]
    _packages: dict[Module, set[Package]]
    _orig_packages: tuple[tuple[Package, Module], ...]

    def __init__(
        self,
        known_packages: Collection[Package] = (),
        packages: Collection[tuple[Package, Module]] = (),
    ) -> None:
        """Initialize the Packages dataclass.

        :param known_packages: Declared dependencies that implicitly provide a module
            of the same canonical name.
        :param packages: Explicit (package, module) tuples, where package is the
            distribution name and module is the import name.
        """
        combined = {
            *packages,
            *((pkg, Module(pkg.canonical)) for pkg in known_packages),
        }
        self._orig_packages = tuple(sorted(combined))
        self._modules = {
            key: {module for _, module in val}
            for key, val in groupby(
                sorted(self._orig_packages, key=itemgetter(0)), key=itemgetter(0)
            )
        }

        self._packages = {
            key: {pkg_ for pkg_, _ in val}
            for key, val in groupby(
                sorted(self._orig_packages, key=itemgetter(1)), key=itemgetter(1)
            )
        }

    def __or__(self, other: Packages) -> Packages:
        """Combine two Packages instances."""
        combined_packages = sorted(set(self._orig_packages) | set(other._orig_packages))
        return Packages((), combined_packages)

    def all_packages(self) -> Iterable[Package]:
        """Get all packages in the mapping."""
        return self._modules.keys()

    def modules(self, pkg_: Package) -> set[Module]:
        """Get the modules (import name) for a given package name.

        :param pkg_: The package to look up.
        """
        return self._modules.get(pkg_, {Module(pkg_.canonical)})

    def packages(self, module: Module) -> set[Package]:
        """Get the packages for a given module (import name).

        :param module: The module (import name) to look up.
        """
        parent = module
        for parent in module.parents:
            if parent in self._packages:
                return self._packages[parent]
        return {Package(parent.name)}


def _canonical(name: str) -> str:
    """Normalize a package name: lowercase and replace hyphens with underscores.

    This makes package name comparison case-insensitive and treats hyphens and
    underscores as equivalent, consistent with PEP 503 / PyPI conventions.
    E.g. ``scikit-learn``, ``scikit_learn``, and ``SciKit-Learn`` all normalize
    to ``scikit_learn``.

    However, it does, contrary to PEP 503, keep dots in the name, so that subpackages
    are preserved. This is important for namespace packages, where a package may
    define submodules that are imported with dotted names (e.g., ``company.module``).

    :param name: The package name to normalize.
    :returns: Normalized package name.
    """
    pkg_name_iter = takewhile(lambda x: x.isalnum() or x in "-_.", name.strip())
    package_name = "".join(pkg_name_iter)
    return package_name.lower().strip().replace("-", "_")
