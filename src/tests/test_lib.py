"""Tests for the lib module."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
import toml

from check_dependencies.lib import AppConfig, Dependency, PyProjectToml
from tests.conftest import DATA, PEP631, POETRY


class TestPyProjectToml:
    """Test suite for the PyProjectToml class."""

    def test_missing_file(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Ensure we don't crash when the config file is missing."""
        monkeypatch.setattr(
            "check_dependencies.lib._PYPROJECT_TOML",
            "pyproject.check-dependencies-non-existent.toml",
        )
        with pytest.raises(
            FileNotFoundError,
            match="pyproject.check-dependencies-non-existent.toml",
        ):
            _ = PyProjectToml.from_pyproject(DATA, AppConfig()).dependencies

    @pytest.mark.parametrize(
        "pyproject, included_dev, add_expect",
        [
            (PEP631, True, []),
            (PEP631, False, []),
            (POETRY, False, []),
            (POETRY, True, ["test_dev_1", "test_dev_2"]),
        ],
    )
    def test_dependencies(
        self,
        pyproject: Path,
        included_dev: bool,
        add_expect: list[str],
    ) -> None:
        """Test get_declared_dependencies function without included development deps."""
        cfg = PyProjectToml(DATA, cfg=toml.load(pyproject), include_dev=included_dev)
        assert set(cfg.dependencies) == {"test_main", "test_1"}.union(add_expect or {})


class TestMkSrcFormatter:
    """Test suite for the mk_src_formatter function."""

    @pytest.fixture
    def stmt(self) -> ast.stmt:
        """AST import statement fixture."""
        return ast.parse("import foo.bar").body[0]

    @pytest.mark.parametrize("verbose", [True, False])
    def test_no_show_all_on_status_ok(self, stmt: ast.stmt, verbose: bool) -> None:
        """If the import is expected, we do not show it."""
        cfg = AppConfig(verbose=verbose, show_all=False)
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
        cfg = AppConfig(verbose=verbose, show_all=show_all)
        fn = cfg.mk_src_formatter()
        assert next(fn(Path("src.py"), Dependency(cause), "foo", stmt)) == expected

    def test_cache(self, stmt: ast.stmt) -> None:
        """Test the cache mechanism for the formatter."""
        cfg = AppConfig(verbose=False)
        fn = cfg.mk_src_formatter()
        assert list(fn("src.py", Dependency.NA, "foo", stmt))
        assert not list(fn("src.py", Dependency.NA, "foo", stmt))
