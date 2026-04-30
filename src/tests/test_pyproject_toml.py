"""Test suite for the PyProjectToml class and get_pyproject_path function."""

from __future__ import annotations

from pathlib import Path
from typing import TypeVar

import pytest

from check_dependencies import pyproject_toml
from check_dependencies.lib import Module, Package
from check_dependencies.pyproject_toml import (
    NoPyProjectFileError,
    PyProjectToml,
    _nested_item,
    get_pyproject_toml,
)
from tests.conftest import (
    HATCH,
    PEP631,
    POETRY,
    PYPROJECT_PROVIDES,
    UV_LEGACY,
)

try:
    import tomllib  # ty:ignore[unresolved-import]
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
            includes_cfg=[],
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
        cfg = PyProjectToml(
            cfg={"project": {"name": "test-project"}},
            path=Path(),
            include_dev=False,
            includes_cfg=[],
        )
        with pytest.raises(ValueError, match="No dependency management found"):
            _ = cfg.dependencies

    def test_provides_empty(self) -> None:
        """Test that provides returns an empty dict when not configured."""
        cfg = self.cfg(PEP631)
        assert cfg.provides == set()

    def test_provides(self) -> None:
        """Test that provides returns the correct mapping."""
        cfg = self.cfg(PYPROJECT_PROVIDES)
        assert cfg.provides == {(Package("test_alias_pkg"), Module("test_1"))}

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
            includes_cfg=[],
        )
        assert cfg.provides == {(Package(expected), Module("some_import"))}

    def test_includes(self, tmp_path: Path) -> None:
        """Test that includes are processed correctly."""
        a = tmp_path / "a.toml"
        b = tmp_path / "b.toml"
        a.write_text(
            "[tool.check-dependencies]\n"
            'known-missing = ["mod_a"]\n'
            'known-extra = ["extra_a"]\n'
            'includes = ["b.toml"]\n'
            'provides = {extra_a = "mod_a"}\n',
            "utf-8",
        )
        b.write_text(
            "[tool.check-dependencies]\n"
            'known-missing = ["mod_b"]\n'
            'known-extra = ["extra_b"]\n'
            'includes = ["c.toml"]\n'
            'provides = {extra_b = "mod_b"}\n',
            "utf-8",
        )
        (tmp_path / "c.toml").write_text(
            "[tool.check-dependencies]\n"
            'known-missing = ["mod_c"]\n'
            'known-extra = ["extra_c"]\n'
            "[tool.check-dependencies.provides]\n"
            'extra_c = "mod_c"\n'
            'extra_a = "mod_ac"\n',
            "utf-8",
        )
        result = PyProjectToml.for_path(a)
        assert set(result.known_missing) == {
            Module("mod_a"),
            Module("mod_b"),
            Module("mod_c"),
        }
        assert set(result.known_extra) == {
            Package("extra_a"),
            Package("extra_b"),
            Package("extra_c"),
        }
        assert set(result.provides) == {
            (Package("extra_a"), Module("mod_a")),
            (Package("extra_a"), Module("mod_ac")),
            (Package("extra_b"), Module("mod_b")),
            (Package("extra_c"), Module("mod_c")),
        }


class TestNestedItem:
    """Test suite for nested item."""

    _T = TypeVar("_T")

    @pytest.mark.parametrize(
        "key, type_, expected",
        [("a.b.c", int, 1), ("a.b.d", int, 2), ("a.b.x", int, 0)],
    )
    def test_nested_item(self, key: str, type_: type[_T], expected: _T) -> None:
        """Test nested item."""
        prj = PyProjectToml(
            cfg={"a": {"b": {"c": 1, "d": 2}}}, path=Path(), includes_cfg=[]
        )
        assert _nested_item(prj.cfg, key, type_) == expected

    def test_raise_wrong_type(self) -> None:
        """Raise wrong type."""
        prj = PyProjectToml(cfg={"a": 1}, path=Path(), includes_cfg=[])
        with pytest.raises(TypeError):
            _nested_item(prj.cfg, "a", str)


class TestPyProjectTomlCircularIncludes:
    """Test that circular includes in PyProjectToml are handled correctly."""

    def test_circular_include_no_duplicate(self, tmp_path: Path) -> None:
        """Circular includes (A→B→A) must not duplicate config values from A."""
        a = tmp_path / "a.toml"
        b = tmp_path / "b.toml"
        a.write_text(
            "[tool.check-dependencies]\n"
            'known-missing = ["mod_a"]\n'
            'includes = ["b.toml"]\n',
            "utf-8",
        )
        b.write_text(
            "[tool.check-dependencies]\n"
            'known-missing = ["mod_b"]\n'
            'includes = ["a.toml"]\n',
            "utf-8",
        )
        result = PyProjectToml.for_path(a)
        # mod_a should appear exactly once; mod_b exactly once
        known = list(result.known_missing)
        assert known.count(Module("mod_a")) == 1
        assert known.count(Module("mod_b")) == 1

    def test_self_referential_include(self, tmp_path: Path) -> None:
        """A self-referential include must not recurse infinitely or duplicate."""
        a = tmp_path / "a.toml"
        a.write_text(
            "[tool.check-dependencies]\n"
            'known-missing = ["mod_a"]\n'
            'includes = ["a.toml"]\n',
            "utf-8",
        )
        result = PyProjectToml.for_path(a)
        known = list(result.known_missing)
        assert known.count(Module("mod_a")) == 1


class TestGetPyProjectToml:
    """Test suite for the get_pyproject_toml function."""

    def test_find_pyproject(self, tmp_path: Path) -> None:
        """Test that get_pyproject_toml finds the pyproject.toml file."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.check-dependencies]\n", "utf-8")
        assert get_pyproject_toml(tmp_path) == pyproject

    def test_no_pyproject(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that get_pyproject_toml raises when no pyproject.toml exists."""
        subdir = tmp_path / "no_project"
        subdir.mkdir()
        monkeypatch.setattr(
            pyproject_toml,
            "_PYPROJECT_TOML",
            Path(subdir / "/non-existent-pyproject.toml"),
        )
        with pytest.raises(NoPyProjectFileError):
            get_pyproject_toml(subdir)
