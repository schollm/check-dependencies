"""Tests for the lib module."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from check_dependencies.lib import AppConfig, Dependency, PyProjectToml, _nested_item, normalize_pkg
from tests.conftest import DATA, PEP631, POETRY, PYPROJECT_EMPTY, PYPROJECT_PROVIDES

try:
    import tomllib
except ImportError:
    import toml as tomllib  # type: ignore[no-redef]


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
        cfg = PyProjectToml(
            DATA,
            cfg=tomllib.loads(pyproject.read_text("utf-8")),
            include_dev=included_dev,
        )
        assert set(cfg.dependencies) == {"test_main", "test_1"}.union(add_expect or {})

    def test_unsupported_dependencies(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test unsupported dependencies in pyproject.toml."""
        cfg = PyProjectToml(
            PYPROJECT_EMPTY,
            cfg=tomllib.loads(PYPROJECT_EMPTY.read_text("utf-8")),
            include_dev=False,
        )
        assert set(cfg.dependencies) == set()
        assert "No dependencies found in" in caplog.text

    def test_provides_empty(self) -> None:
        """Test that provides returns an empty dict when not configured."""
        cfg = PyProjectToml(
            DATA,
            cfg=tomllib.loads(PEP631.read_text("utf-8")),
            include_dev=False,
        )
        assert cfg.provides == {}

    def test_provides(self) -> None:
        """Test that provides returns the correct mapping."""
        cfg = PyProjectToml(
            DATA,
            cfg=tomllib.loads(PYPROJECT_PROVIDES.read_text("utf-8")),
            include_dev=False,
        )
        assert cfg.provides == {"test_1": "test_alias_pkg"}

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("pyjwt", "pyjwt"),
            ("PyJWT", "pyjwt"),
            ("scikit-learn", "scikit_learn"),
            ("scikit_learn", "scikit_learn"),
            ("SciKit-Learn", "scikit_learn"),
            ("Pillow", "pillow"),
        ],
    )
    def test_provides_normalizes_values(self, raw: str, expected: str) -> None:
        """PyProjectToml.provides normalizes package name values."""
        cfg = PyProjectToml(
            DATA,
            cfg={"tool": {"check-dependencies": {"provides": {"some_import": raw}}}},
            include_dev=False,
        )
        assert cfg.provides == {"some_import": expected}


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


class TestNestedItem:
    """Test suite for nested item."""

    @pytest.mark.parametrize(
        "key, type_, expected",
        [
            ("a.b.c", int, 1),
            ("a.b.d", int, 2),
        ],
    )
    def test_nested_item(self, key: str, type_: type, expected: object) -> None:
        """Test nested item."""
        assert _nested_item({"a": {"b": {"c": 1, "d": 2}}}, key, type_) == expected

    def test_raise_wrong_type(self) -> None:
        """Raise wrong type."""
        with pytest.raises(TypeError):
            _nested_item({"a": 1}, "a", str)
