"""Test suite for the PyProjectToml class and get_pyproject_path function."""

from __future__ import annotations

from pathlib import Path

import pytest

from check_dependencies.pyproject_toml import PyProjectToml
from tests.conftest import PEP631, POETRY, PYPROJECT_EMPTY, PYPROJECT_PROVIDES

try:
    import tomllib
except ImportError:
    import toml as tomllib  # type: ignore[no-redef]

from check_dependencies.pyproject_toml import get_pyproject_path


class TestPyProjectToml:
    """Test suite for the PyProjectToml class."""

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
            cfg=tomllib.loads(pyproject.read_text("utf-8")),
            include_dev=included_dev,
        )
        assert set(cfg.dependencies) == {"test_main", "test_1"}.union(add_expect or {})

    def test_unsupported_dependencies(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test unsupported dependencies in pyproject.toml."""
        cfg = PyProjectToml(
            cfg=tomllib.loads(PYPROJECT_EMPTY.read_text("utf-8")),
            include_dev=False,
        )
        assert set(cfg.dependencies) == set()
        assert "No dependencies found in" in caplog.text

    def test_provides_empty(self) -> None:
        """Test that provides returns an empty dict when not configured."""
        cfg = PyProjectToml(
            cfg=tomllib.loads(PEP631.read_text("utf-8")),
            include_dev=False,
        )
        assert cfg.provides == []

    def test_provides(self) -> None:
        """Test that provides returns the correct mapping."""
        cfg = PyProjectToml(
            cfg=tomllib.loads(PYPROJECT_PROVIDES.read_text("utf-8")),
            include_dev=False,
        )
        assert cfg.provides == [("test_alias_pkg", "test_1")]

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
            include_dev=False,
        )
        assert cfg.provides == [(expected, "some_import")]


class TestGetPyProjectPath:
    """Test suite for the get_pyproject_path function."""

    def test_find_pyproject(self, tmp_path: Path) -> None:
        """Test that get_pyproject_path finds the pyproject.toml file."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.check-dependencies]\n", "utf-8")
        assert get_pyproject_path(tmp_path) == pyproject

    def test_no_pyproject(self) -> None:
        """Test that get_pyproject_path raises without pyproject.toml."""
        with pytest.raises(FileNotFoundError):
            get_pyproject_path(Path("/"))
