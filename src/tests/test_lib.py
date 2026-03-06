"""Tests for the lib module."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from check_dependencies.app_config import AppConfig
from check_dependencies.lib import Dependency, normalize_pkg


class TestNormalizePkg:
    """Test suite for the normalize_pkg helper."""

    @pytest.mark.parametrize(
        "name, expected",
        [
            ("pyjwt", "pyjwt"),
            ("PyJWT", "pyjwt"),
            ("scikit-learn", "scikit_learn"),
            ("scikit_learn", "scikit_learn"),
            ("SciKit-Learn", "scikit_learn"),
            ("Pillow", "pillow"),
        ],
    )
    def test_normalize_pkg(self, name: str, expected: str) -> None:
        """normalize_pkg lowercases and replaces hyphens with underscores."""
        assert normalize_pkg(name) == expected


class TestMkSrcFormatter:
    """Test suite for the mk_src_formatter function."""

    @pytest.fixture
    def stmt(self) -> ast.stmt:
        """AST import statement fixture."""
        return ast.parse("import foo.bar").body[0]

    @pytest.mark.parametrize("verbose", [True, False])
    def test_no_show_all_on_status_ok(self, stmt: ast.stmt, verbose: bool) -> None:
        """If the import is expected, we do not show it."""
        cfg = AppConfig.from_cli_args(
            file_names=(), verbose=verbose, show_all=False, known_extra="foo"
        )
        fn = cfg.mk_src_formatter()
        assert not list(fn(Path("src.py"), Dependency.OK, "foo", stmt))

    @pytest.mark.parametrize(
        "verbose, show_all, cause, expected",
        [
            (True, False, "!", "!NA src.py:1 foo"),
            (True, True, "!", "!NA src.py:1 foo"),
            (True, True, " ", " OK src.py:1 foo"),
            (False, False, "!", "! foo"),
            (False, True, "!", "! foo"),
            (False, True, " ", "  foo"),
        ],
    )
    def test(  # pylint: disable=too-many-arguments
        self,
        stmt: ast.stmt,
        verbose: bool,
        show_all: bool,
        cause: str,
        expected: str,
    ) -> None:
        """MkSrcFormatter generic tests."""
        cfg = AppConfig.from_cli_args(file_names=(), verbose=verbose, show_all=show_all)
        fn = cfg.mk_src_formatter()
        assert next(fn(Path("src.py"), Dependency(cause), "foo", stmt)) == expected

    def test_cache(self, stmt: ast.stmt) -> None:
        """Test the cache mechanism for the formatter."""
        cfg = AppConfig.from_cli_args(file_names=(), verbose=False)
        fn = cfg.mk_src_formatter()
        assert list(fn("src.py", Dependency.NA, "foo", stmt))
        assert not list(fn("src.py", Dependency.NA, "foo", stmt))
