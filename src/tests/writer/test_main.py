"""Tests for writer.cli."""

from __future__ import annotations

import sys
from importlib import import_module
from typing import TYPE_CHECKING

import pytest

from check_dependencies.writer.cli import EXIT_FAILURE, EXIT_SUCCESS, EXIT_VALUE_ERROR

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize("python_switch", ["-p", "--python"])
@pytest.mark.parametrize("cfg_switch", ["-c", "--config"])
def test__main__args__stdout(
    monkeypatch: pytest.MonkeyPatch,
    capteesys: pytest.CaptureFixture,
    python_switch: str,
    cfg_switch: str,
) -> None:
    """Test writer with write to stdout."""
    monkeypatch.setattr(
        sys,
        "argv",
        ["check-dependencies", python_switch, sys.executable, cfg_switch, "-"],
    )
    with pytest.raises(SystemExit) as exc:
        import_module("check_dependencies.writer.__main__")
    assert exc.value.code == EXIT_SUCCESS
    stdout = capteesys.readouterr().out
    assert "[tool.check-dependencies.provides]\n" in stdout
    assert "pytest = " in stdout


@pytest.mark.parametrize(
    "cfg_content",
    [
        None,
        "",
        "[foo]",
        "[tool.check-dependencies.provides]\n",
        '[tool.check-dependencies.provides]\n"foo" = ["bar"]\n',
    ],
)
def test_main__args(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, cfg_content: str | None
) -> None:
    """Test writer with different pre-set config."""
    cfg_file = tmp_path / "check-dependencies.cfg"
    if cfg_content is not None:
        cfg_file.write_text(cfg_content)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "check-dependencies",
            "--python",
            sys.executable,
            "--config",
            cfg_file.as_posix(),
        ],
    )
    with pytest.raises(SystemExit) as exc:
        import_module("check_dependencies.writer.__main__")
    assert exc.value.code == EXIT_SUCCESS
    cfg = cfg_file.read_text("utf-8")
    assert "[tool.check-dependencies.provides]\n" in cfg
    assert "pytest = " in cfg
    assert (cfg_content or "") in cfg


def test__main__invalid_cfg(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capteesys: pytest.CaptureFixture,
) -> None:
    """Test with invalid cfg file."""
    cfg_file = tmp_path / "check-dependencies.cfg"
    cfg_file.write_text("[invalid cfg]")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "foo",
            "--python",
            sys.executable,
            "--config",
            cfg_file.as_posix(),
        ],
    )
    with pytest.raises(SystemExit) as exc:
        import_module("check_dependencies.writer.__main__")
    assert exc.value.code == 1
    assert 'Invalid key "invalid cfg" at line 1' in capteesys.readouterr().err


def test__main__cfg_file_is_non_readable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capteesys: pytest.CaptureFixture,
) -> None:
    """Test unreadable cfg file (because it's a directory)."""
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "foo",
            "--python",
            sys.executable,
            "--config",
            tmp_path.as_posix(),
        ],
    )
    with pytest.raises(SystemExit) as exc:
        import_module("check_dependencies.writer.__main__")
    assert exc.value.code == EXIT_VALUE_ERROR
    assert "--config file must be a readable file" in capteesys.readouterr().err


def test__main__() -> None:
    """Test writer without arguments."""
    with pytest.raises(SystemExit) as exc:
        import_module("check_dependencies.writer.__main__")
    assert exc.value.code == EXIT_FAILURE
