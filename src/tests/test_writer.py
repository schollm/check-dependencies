"""Tests for writer.cli."""

from __future__ import annotations

import builtins
import sys
import textwrap
from typing import TYPE_CHECKING, Any

import pytest
import tomlkit

from check_dependencies import writer

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize("python_switch", ["-p", "--python"])
@pytest.mark.parametrize("cfg_switch", ["-c", "--config"])
def test__main__args__stdout(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
    python_switch: str,
    cfg_switch: str,
) -> None:
    """Test writer with write to stdout."""
    monkeypatch.setattr(
        sys,
        "argv",
        ["check-dependencies", python_switch, sys.executable, cfg_switch, "-"],
    )
    assert writer.main() == writer.EXIT_SUCCESS
    stdout = capsys.readouterr().out
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

    assert writer.main() == writer.EXIT_SUCCESS
    cfg = cfg_file.read_text("utf-8")
    assert "[tool.check-dependencies.provides]\n" in cfg
    assert "pytest = " in cfg
    assert (cfg_content or "") in cfg


def test__main__invalid_cfg(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
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
    assert writer.main() == writer.EXIT_VALUE_ERROR
    assert 'Invalid key "invalid cfg" at line 1' in capsys.readouterr().err


def test__main__cfg_file_is_non_readable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
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
    assert writer.main() == writer.EXIT_VALUE_ERROR
    assert "--config file must be a readable file" in capsys.readouterr().err


def test__main__() -> None:
    """Test writer without arguments."""
    with pytest.raises(SystemExit) as exc:
        writer.main()
    assert exc.value.code == writer.EXIT_FAILURE


def test__ensure_key() -> None:
    """Test _ensure_key."""
    doc = tomlkit.parse(
        textwrap.dedent("""\
        [tool.a]
        [fox]
        [tool.b]
    """)
    )

    writer._ensure_key(doc)
    assert tomlkit.dumps(doc) == textwrap.dedent("""\
        [tool.a]

        [tool.check-dependencies.provides]
        [fox]
        [tool.b]
    """)


def test__ensure_key2() -> None:
    """Test _ensure_key."""
    doc = tomlkit.parse(
        textwrap.dedent("""\
        [tool.check-dependencies.a]
        [fox]
        [tool.check-dependencies.b]
    """)
    )

    writer._ensure_key(doc)
    assert tomlkit.dumps(doc) == textwrap.dedent("""\
        [tool.check-dependencies.a]

        [tool.check-dependencies.provides]
        [fox]
        [tool.check-dependencies.b]
    """)


def test_no_writer_extra_installed(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    """Test that writer fails if tomlkit is not installed."""
    # Remove tomlkit and check_dependencies.writer from sys.modules
    monkeypatch.delitem(sys.modules, "tomlkit", raising=False)
    monkeypatch.delitem(sys.modules, "check_dependencies.writer", raising=False)

    original_import = builtins.__import__

    # Make only `import tomlkit` fail, while delegating all other imports.
    def fake_import(name: str, *args: Any, **kwargs: Any) -> object:  # noqa: ANN401
        if name == "tomlkit":
            raise ImportError(name)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(SystemExit) as exc:
        __import__("check_dependencies.writer")

    assert exc.value.code == 1
    output = capsys.readouterr()
    assert "Require group [write] to be installed." in output.err
    assert "tomlkit" in output.err
