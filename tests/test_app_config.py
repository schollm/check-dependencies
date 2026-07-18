"""Tests for app_config module."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import TYPE_CHECKING

from check_dependencies.app_config import AppConfig, OutputFormat, ProjectConfig
from check_dependencies.lib import Module, Package
from check_dependencies.pyproject_toml import PyProjectToml

if TYPE_CHECKING:
    from collections.abc import Sequence


def app_cfg(
    known_extra: Sequence[str] = (),
    known_missing: Sequence[str] = (),
    provides: Sequence[str] = (),
    includes: Sequence[Path] = (),
) -> AppConfig:
    """Return a default AppConfig for testing."""
    return AppConfig.from_cli_args(
        file_names=[Path("src")],
        known_extra=known_extra,
        known_missing=known_missing,
        provides=provides,
        include_dev=False,
        verbose=False,
        output_format=OutputFormat.CONCISE,
        includes=includes,
    )


def test_empty_known_extra_cli() -> None:
    """Test empty known extra from CLI."""
    assert app_cfg(known_extra=["xx", ""]).known_extra == [Package("xx")]


def test_empty_known_missing_cli() -> None:
    """Test empty known missing from CLI."""
    assert app_cfg(known_missing=["yy", ""]).known_missing == [Module("yy")]


def test_empty_provides_cli() -> None:
    """Test empty provides from CLI."""
    assert app_cfg(
        provides=["xx=xx_", "", "yy=yy1_,yy2_,", "zz="]
    ).provides._orig_packages == (
        (Package("xx"), Module("xx_")),
        (Package("yy"), Module("yy1_")),
        (Package("yy"), Module("yy2_")),
    )


def test_project_cfg(tmp_path: Path) -> None:
    """Test ProjectConfig dataclass."""
    (pyproject_path := tmp_path / "pyproject.toml").write_text(
        textwrap.dedent("""\
            [project]
            dependencies=["dep1=*"]
            [tool.check-dependencies]
            known-missing = ["missing"]
            known-extra = ["extra"]
            dependencies = ["dep1", "dep2"]
            provides = {dep1 = "mod1", dep2 = "mod2"}
            """),
        "utf-8",
    )
    pyproject_cfg = PyProjectToml.for_path(pyproject_path)
    cfg = ProjectConfig.from_config(app_cfg(provides=["app1=mod1"]), pyproject_cfg)
    assert cfg.known_missing == {Module("missing")}
    assert cfg.known_extra == {Package("extra")}
    assert set(cfg.allowed_dependencies) >= {Package("dep1"), Package("extra")}
    assert cfg.packages._orig_packages == (
        (Package("app1"), Module("mod1")),
        (Package("dep1"), Module("dep1")),
        (Package("dep1"), Module("mod1")),
        (Package("dep2"), Module("mod2")),
    )
