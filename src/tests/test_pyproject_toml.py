"""Test suite for the PyProjectToml class and get_pyproject_path function."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TypeVar

import pytest

from check_dependencies.lib import Package
from check_dependencies.pyproject_toml import (
    PyProjectToml,
    _get_pyproject_path,
    _nested_item,
)
from tests.conftest import (
    HATCH,
    PEP631,
    POETRY,
    PYPROJECT_EMPTY,
    PYPROJECT_PROVIDES,
    UV_LEGACY,
)

try:
    import tomllib  # type: ignore[unresolved-import]
except ImportError:  # pragma: no cover
    import toml as tomllib


class TestPyProjectToml:
    """Test suite for the PyProjectToml class."""

    def cfg(self, path: Path, include_dev: bool = False) -> PyProjectToml:
        """Create a PyProjectToml instance."""
        return PyProjectToml(
            cfg=tomllib.loads(path.read_text("utf-8")),
            path=path,
            include_dev=include_dev,
        )

    @pytest.mark.parametrize(
        "pyproject, included_dev, add_expect",
        [
            (PEP631, True, []),
            (PEP631, False, []),
            (POETRY, False, []),
            (POETRY, True, ["test_dev_1", "test_dev_2"]),
            (HATCH, False, []),
            (HATCH, True, ["test_dev_1", "test_dev_2"]),
            (UV_LEGACY, False, []),
            (UV_LEGACY, True, ["test_dev_1", "test_dev_2"]),
        ],
    )
    def test_dependencies(
        self,
        pyproject: Path,
        included_dev: bool,
        add_expect: list[str],
    ) -> None:
        """Test get_declared_dependencies function without included development deps."""
        cfg = self.cfg(pyproject, include_dev=included_dev)
        assert set(cfg.dependencies) == {"test_main", "test_1"}.union(add_expect or {})

    def test_unsupported_dependencies(self) -> None:
        """Test unsupported dependencies in pyproject.toml."""
        cfg = self.cfg(PYPROJECT_EMPTY)
        with pytest.raises(ValueError, match="No dependency management found"):
            _ = cfg.dependencies

    def test_provides_empty(self) -> None:
        """Test that provides returns an empty dict when not configured."""
        cfg = self.cfg(PEP631)
        assert cfg.provides == []

    def test_provides(self) -> None:
        """Test that provides returns the correct mapping."""
        cfg = self.cfg(PYPROJECT_PROVIDES)
        assert cfg.provides == [(Package("test_alias_pkg"), "test_1")]

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
            cfg={"tool": {"check-dependencies": {"provides": {raw: "some_import"}}}},
            path=Path("dummy"),
            include_dev=False,
        )
        assert cfg.provides == [(Package(expected), "some_import")]

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test")
    def test_fails_on_different_paths(self) -> None:
        """Test that PyProjectToml raises when initialized with different paths."""
        with pytest.raises(
            ValueError, match=r"Error finding common path for.*C:.test.*D:.test"
        ):
            PyProjectToml.for_paths(["C:/test", "D:/test"])


class TestNestedItem:
    """Test suite for nested item."""

    _T = TypeVar("_T")

    @pytest.mark.parametrize(
        "key, type_, expected",
        [("a.b.c", int, 1), ("a.b.d", int, 2), ("a.b.x", int, 0)],
    )
    def test_nested_item(self, key: str, type_: type[_T], expected: _T) -> None:
        """Test nested item."""
        prj = PyProjectToml(cfg={"a": {"b": {"c": 1, "d": 2}}}, path=Path())
        assert _nested_item(prj.cfg, key, type_) == expected

    def test_raise_wrong_type(self) -> None:
        """Raise wrong type."""
        prj = PyProjectToml(cfg={"a": 1}, path=Path())
        with pytest.raises(TypeError):
            _nested_item(prj.cfg, "a", str)


class TestGetPyProjectPath:
    """Test suite for the get_pyproject_path function."""

    def test_find_pyproject(self, tmp_path: Path) -> None:
        """Test that get_pyproject_path finds the pyproject.toml file."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.check-dependencies]\n", "utf-8")
        assert _get_pyproject_path(tmp_path) == pyproject

    def test_no_pyproject(self) -> None:
        """Test that get_pyproject_path raises without pyproject.toml."""
        with pytest.raises(FileNotFoundError):
            _get_pyproject_path(Path("/"))
