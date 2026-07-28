"""Tests for app_config module."""

from __future__ import annotations

import argparse
import logging
import textwrap
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from check_dependencies.app_config import (
    AppConfig,
    OutputFormat,
    ProjectConfig,
    _get_version,
    _MultiSepAction,
)
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


def test_app_cfg_from_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test AppConfig.from_argv() with monkeypatching."""
    monkeypatch.setattr("sys.argv", ["check-dependencies", "src"])
    cfg = AppConfig.from_argv()
    assert cfg.file_names == [Path("src")]


def test_app_cfg_from_argv_deprecated_all(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Test AppConfig.from_argv() with monkeypatching."""
    monkeypatch.setattr("sys.argv", ["check-dependencies", "src", "--all"])
    with caplog.at_level(logging.WARNING):
        cfg = AppConfig.from_argv()
    assert cfg.file_names == [Path("src")]
    assert cfg.output_format == OutputFormat.FULL
    assert "--all is deprecated, use --output-format full instead." in caplog.text


class TestMultiSepAction:
    """Test _MultiSepAction."""

    @pytest.mark.parametrize(
        "args, expected",
        [
            (["--foo=a,b"], ["a", "b"]),
            (["--foo", "a,b"], ["a", "b"]),
            (["--foo=a", "--foo=b"], ["a", "b"]),
            (["--foo", "a,b", "--foo", "c"], ["a", "b", "c"]),
            (["-f", "a", "--foo", "b,c", "-f=d"], ["a", "b", "c", "d"]),
        ],
    )
    def test(self, args: list[str], expected: list[str]) -> None:
        """MultiSepAction with different lists."""
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--foo",
            "-f",
            type=str,
            action=_MultiSepAction,
        )
        res = parser.parse_args(args)
        assert res.foo == expected

    def test_invalid_type(self) -> None:
        """MultiSepAction with invalid type."""
        parser = argparse.ArgumentParser()
        with pytest.raises(ValueError, match="type: Only support str"):
            parser.add_argument("--foo", type=int, action=_MultiSepAction)

    def test_invalid_type_arg(self) -> None:
        """MultiSepAction with invalid type."""
        parser = argparse.ArgumentParser()
        parser.add_argument("--foo", action=_MultiSepAction)
        action = _MultiSepAction([], "foo", None, str)

        with pytest.raises(TypeError, match="expected a string, got"):
            action(parser, argparse.Namespace(), [])

    @pytest.mark.parametrize("nargs", ["*", "?", "+"])
    def test_invalid_nargs(self, nargs: str) -> None:
        """MultiSepAction with invalid nargs."""
        parser = argparse.ArgumentParser()
        with pytest.raises(ValueError, match="nargs not allowed"):
            parser.add_argument("--foo", nargs=nargs, action=_MultiSepAction)


def test_get_version_without_package_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """Return `unknown` when package metadata is unavailable."""

    def _raise_package_not_found(_dist_name: str) -> str:
        raise PackageNotFoundError(_dist_name)

    monkeypatch.setattr(
        "check_dependencies.app_config.version", _raise_package_not_found
    )

    assert _get_version() == "unknown"
