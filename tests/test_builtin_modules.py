"""Tests for the builtin modules."""

from __future__ import annotations

import sys
from importlib import import_module

import pytest

from check_dependencies import builtin_module


def test_is_frozenset():
    """Are the builtin modules stored in a frozenset?"""
    assert isinstance(builtin_module.BUILTINS, frozenset)


def test_contains_future():
    """Test a single sample module."""
    assert "__future__" in builtin_module.BUILTINS


@pytest.mark.parametrize(
    "module",
    ["memray", "pip", "pkg_resources", "setuptools", "wheel", "_virtualenv"],
)
@pytest.mark.parametrize("version", [(3, 9), (3, 10)])
def test_does_not_contain_extra_module(
    module: str, version: tuple[int, int], monkeypatch: pytest.MonkeyPatch
):
    if version >= (3, 10) and sys.version_info < (3, 10):
        pytest.skip("Python version is too low for this test")
    """Test that a module that is not builtin is not in the set."""
    monkeypatch.setattr("sys.version_info", version)
    monkeypatch.delitem(sys.modules, "check_dependencies.builtin_module", raising=False)
    bmod = import_module("check_dependencies.builtin_module")
    assert module not in bmod.BUILTINS


def test_no_empty_module():
    """Ensure no empty string is in the builtins set."""
    assert "" not in builtin_module.BUILTINS


def test_all_correct_names():
    """Ensure all builtin modules are valid identifiers."""
    for module in builtin_module.BUILTINS:
        assert module.isidentifier()
