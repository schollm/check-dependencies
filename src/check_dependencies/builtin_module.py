"""A list of all builtin modules."""

from __future__ import annotations

import sys

_EXTRA_MODULES = frozenset(
    {
        "_typeshed"  # Part of stdlib, but not available at runtime.
    }
)

BUILTINS = frozenset(sys.stdlib_module_names).union(_EXTRA_MODULES)  # pylint: disable=no-member
