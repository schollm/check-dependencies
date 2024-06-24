"""Tests for the builtin modules."""

from __future__ import annotations

from check_dependencies.builtin_module import BUILTINS


def test_is_set():
    """Are the builtin modules stored in a set?"""
    assert isinstance(BUILTINS, set)


def test_contains_future():
    """Test a single sample module."""
    assert "__future__" in BUILTINS


def test_no_empty_module():
    """Ensure no empty string is in the builtins set."""
    assert "" not in BUILTINS


def test_all_correct_names():
    """Ensure all builtin modules are valid identifiers."""
    for module in BUILTINS:
        assert module.isidentifier()
