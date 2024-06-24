"""Tests for the lib module."""

from __future__ import annotations

import ast
from typing import Sequence

import pytest

from check_dependencies.lib import Config, Dependency
from tests.conftest import POETRY


class TestConfig:
    """Test suite for the Config class"""

    @pytest.mark.parametrize("show_all", [True, False])
    @pytest.mark.parametrize("include_dev", [True, False])
    @pytest.mark.parametrize("ignore_requirements", [(), ("test_1",)])
    @pytest.mark.parametrize("extra_requirements", [(), ("test_1",)])
    def test_missing_file(
        self,
        show_all: bool,
        include_dev: bool,
        ignore_requirements: Sequence[str],
        extra_requirements: Sequence[str],
    ) -> None:
        """Ensure we don't crash when the config file is missing"""
        with pytest.raises(FileNotFoundError, match="non-existent.toml"):
            Config(
                file="non-existent.toml",
                show_all=show_all,
                include_dev=include_dev,
                ignore_requirements=ignore_requirements,
                extra_requirements=extra_requirements,
            )

    @pytest.mark.parametrize(
        "included_dev, expect",
        [
            (False, "test_main test_1"),
            (True, "test_main test_1 test_dev_1 test_dev_2"),
        ],
    )
    def test_get_declared_dependencies(self, included_dev, expect) -> None:
        """Test the get_declared_dependencies function without included development dependencies"""
        cfg = Config(file=POETRY, include_dev=included_dev)
        assert set(cfg.get_declared_dependencies()) == set(expect.split())


class TestMkSrcFormatter:
    """Test suite for the mk_src_formatter function"""

    @pytest.fixture
    def stmt(self) -> ast.stmt:
        """AST import statement fixture"""
        return ast.parse("import foo").body[0]

    @pytest.mark.parametrize("cfg_file", ["", None])
    @pytest.mark.parametrize("show_all", [True, False])
    @pytest.mark.parametrize("cause", ["!", " "])
    @pytest.mark.parametrize(
        "verbose, expect", [(True, "src.py:1 foo"), (False, "foo")]
    )
    def test_no_cfg(  # pylint: disable=too-many-arguments
        self,
        cfg_file: str,
        stmt: ast.stmt,
        verbose: bool,
        show_all: bool,
        cause: str,
        expect: str,
    ) -> None:
        """Without config we cannot get a NA status"""
        cfg = Config(file=cfg_file, verbose=verbose, show_all=show_all)
        fn = cfg.mk_src_formatter()
        assert fn("src.py", Dependency(cause), "foo", stmt) == expect

    @pytest.mark.parametrize("verbose", [True, False])
    def test_no_show_all_on_status_ok(self, stmt: ast.stmt, verbose: bool) -> None:
        """If the import is expected, we do not show it"""
        cfg = Config(file=POETRY, verbose=verbose, show_all=False)
        fn = cfg.mk_src_formatter()
        assert fn("src.py", Dependency.OK, "foo", stmt) is None

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
        self, stmt: ast.stmt, verbose: bool, show_all: bool, cause: str, expected: str
    ) -> None:
        """MkSrcFormatter generic tests"""
        cfg = Config(file=POETRY, verbose=verbose, show_all=show_all)
        fn = cfg.mk_src_formatter()
        assert fn("src.py", Dependency(cause), "foo", stmt) == expected

    @pytest.mark.parametrize("cfg_file", [POETRY, None])
    def test_cache(self, cfg_file: str | None, stmt: ast.stmt) -> None:
        """Test the cache mechanism for the formatter"""
        cfg = Config(file=cfg_file, verbose=False)
        fn = cfg.mk_src_formatter()
        assert fn("src.py", Dependency.NA, "foo", stmt) is not None
        assert fn("src.py", Dependency.NA, "foo", stmt) is None
