"""Test the main module."""

from __future__ import annotations

import ast
import time
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from check_dependencies.__main__ import main as cli_main
from check_dependencies.app_config import AppConfig, Packages
from check_dependencies.lib import Dependency
from check_dependencies.main import (
    _imports_iter,
    _missing_imports_iter,
    yield_wrong_imports,
)
from tests.conftest import (
    DATA,
    POETRY,
    PYPROJECT_CFG,
    PYPROJECT_PROVIDES,
    PYPROJECT_UNICODE,
    SRC,
    SRC_MODULE,
    SRC_UNICODE,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


def test__main__(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the main module.

    This also tests if all dependencies are defined correctly.
    """
    main_module = Path(__file__).parents[1] / "check_dependencies"
    monkeypatch.setattr("sys.argv", ["check_dependencies", main_module.as_posix()])
    with pytest.raises(SystemExit) as excinfo:
        cli_main()
    assert excinfo.value.code == 0


@pytest.mark.parametrize(
    "argv_provides, expected_provides",
    [
        # single flag
        (["--provides", "Pillow=PIL"], [("pillow", {"PIL"})]),
        # multiple flags (primary new feature)
        (
            ["--provides", "Pillow=PIL", "--provides", "PyJWT=jwt"],
            [("pillow", {"PIL"}), ("pyjwt", {"jwt"})],
        ),
        # normalization: uppercase → lowercase
        (["--provides", "PyJWT=jwt"], [("pyjwt", {"jwt"})]),
        # multiple modules provided by the same package
        (["--provides", "foo=fox,foo=bar"], [("foo", {"fox", "bar"})]),
        # normalization: hyphen → underscore
        (["--provides", "scikit-learn=sklearn"], [("scikit_learn", {"sklearn"})]),
        # normalization: mixed case + hyphen
        (["--provides", "SciKit-Learn=sklearn"], [("scikit_learn", {"sklearn"})]),
        # backward-compat: comma-separated in a single flag
        (
            ["--provides", "Pillow=PIL,PyJWT=jwt"],
            [("pillow", {"PIL"}), ("pyjwt", {"jwt"})],
        ),
    ],
)
def test__main__provides_parsing(
    monkeypatch: pytest.MonkeyPatch,
    argv_provides: list[str],
    expected_provides: list[tuple[str, set[str]]],
) -> None:
    """Test that --provides flags are parsed, merged, and normalized correctly."""
    captured: dict[str, Packages] = {}

    def _mock_yield(_file_names: object, app_cfg: AppConfig) -> object:
        captured["provides"] = app_cfg.provides
        return iter([])

    monkeypatch.setattr("check_dependencies.__main__.yield_wrong_imports", _mock_yield)
    monkeypatch.setattr(
        "sys.argv", ["check_dependencies", *argv_provides, DATA.as_posix()]
    )
    with pytest.raises(SystemExit):
        cli_main()
    packages = captured["provides"]
    for expected_pkg, expected_import in expected_provides:
        assert packages.modules(expected_pkg) == expected_import


class TestYieldWrongImports:
    """Test collection for the yield wrong imports function."""

    def fn(  # pylint: disable=too-many-arguments
        self,
        overwrite_cfg: Path = POETRY,
        file_names: Sequence[str] = (SRC,),
        include_dev: bool = False,
        verbose: bool = False,
        show_all: bool = False,
        known_extra: Sequence[str] = (),
        known_missing: Sequence[str] = (),
        provides: Sequence[str] = (),
    ) -> list[str]:
        """Call the yield wrong imports function with patched pyproject.toml."""
        with patch("check_dependencies.pyproject_toml._PYPROJECT_TOML", overwrite_cfg):
            return list(
                yield_wrong_imports(
                    file_names,
                    AppConfig.from_cli_args(
                        file_names=file_names,
                        include_dev=include_dev,
                        verbose=verbose,
                        show_all=show_all,
                        known_extra=",".join(known_extra),
                        known_missing=",".join(known_missing),
                        provides=provides or [],
                    ),
                ),
            )

    def test(self, pyproject: Path) -> None:
        """By default, we should only see the missing (and extra) imports."""
        assert self.fn(overwrite_cfg=pyproject) == [
            "! missing",
            "! missing_class",
            "! missing_def",
        ]

    def test_dev(self) -> None:
        """Test default with dev."""
        assert self.fn(overwrite_cfg=PYPROJECT_CFG, include_dev=True) == [
            "+ test_devtest",
            "+ test_doctest",
        ]

    def test_extra_requirements(self, pyproject_extra: Path) -> None:
        """Ensure extra requirements are printed by default."""
        assert self.fn(overwrite_cfg=pyproject_extra) == [
            "! missing",
            "! missing_class",
            "! missing_def",
            "+ test_extra",
        ]

    def test_extra_requirements_verbose(self, pyproject_extra: Path) -> None:
        """Ensure extra requirements are printed by default."""
        assert set(self.fn(overwrite_cfg=pyproject_extra, verbose=True)) > {
            "",
            "### Dependencies in config file not used in application:",
        }

    def test_extra_requirements_as_cfg(self) -> None:
        """Do not flog unused requirements passed in as an extra."""
        assert not self.fn(overwrite_cfg=PYPROJECT_CFG)

    def test_provides_from_config(self) -> None:
        """Packages with a provides mapping should not appear as missing or extra.

        The pyproject_pep631_provides.toml declares 'test_alias_pkg' as a dependency
        with ``provides.test_1 = "test_alias_pkg"``.  Since src.py imports test_1,
        neither ``! test_1`` (missing) nor ``+ test_alias_pkg`` (extra) should appear.
        """
        result = self.fn(overwrite_cfg=PYPROJECT_PROVIDES)
        assert "! test_1" not in result
        assert "+ test_alias_pkg" not in result
        assert result == ["! missing", "! missing_class", "! missing_def"]

    def test_provides_from_app_cfg(self) -> None:
        """AppConfig.provides (CLI --provides) resolves false positives like config."""
        # POETRY has test_alias_pkg NOT declared, but we pass provides via AppConfig
        # to map test_1 -> test_main (test_main IS declared in POETRY).
        result = self.fn(overwrite_cfg=POETRY, provides="test_main=test_1")
        assert "! test_1" not in result
        assert "+ test_main" not in result

    def test_provides_app_cfg_overrides_file_cfg(self) -> None:
        """CLI --provides takes precedence over [tool.check-dependencies.provides]."""
        # Config maps test_1 -> test_alias_pkg.  CLI overrides to test_1 -> test_main.
        result = self.fn(
            overwrite_cfg=PYPROJECT_PROVIDES,
            provides="test_main=test_1",
        )
        assert "! test_1" not in result
        assert "+ test_main" not in result

    def test_ignore_requirements(self, pyproject_extra: Path) -> None:
        """Ensure ignored requirements are not printed."""
        assert self.fn(overwrite_cfg=pyproject_extra, known_extra=["test_extra"]) == [
            "! missing",
            "! missing_class",
            "! missing_def",
        ]

    def test_ignore_requirements_still_check_in_src(self) -> None:
        """Ensure ignored requirements are not flagged even if they come up in src."""
        assert "  test_1" in self.fn(overwrite_cfg=POETRY, show_all=True)
        assert self.fn(overwrite_cfg=POETRY, known_missing=["test_1"]) == [
            "! missing",
            "! missing_class",
            "! missing_def",
        ]

    def test_show_all(self) -> None:
        """Show all imports, including correct ones."""
        assert self.fn(show_all=True) == [
            "! missing",
            "  test_1",
            "  test_main",
            "  check_dependencies",
            "! missing_class",
            "! missing_def",
        ]

    def test_include_extra(self) -> None:
        """Include development dependencies in the check."""
        assert self.fn(include_dev=True) == [
            "! missing",
            "! missing_class",
            "! missing_def",
            "+ test_dev_1",
            "+ test_dev_2",
        ]

    def test_include_extra_requirements(self) -> None:
        """Test known_missing.

        Include requirements as known-missing - they should not appear in the output.
        """
        res = self.fn(known_missing=["missing", "test_1"])
        assert res == ["! missing_class", "! missing_def"]

    def test_verbose(self) -> None:
        """Verbose output should include the file and line number of the import."""
        assert self.fn(verbose=True) == [
            f"!NA {SRC}:1 missing.bar",
            f"!NA {SRC}:2 missing.foo",
            f"!NA {SRC}:5 missing",
            f"!NA {SRC}:11 missing_class",
            f"!NA {SRC}:15 missing",
            f"!NA {SRC}:16 missing_def",
        ]

    def test_verbose_show_all(self) -> None:
        """Test for the most verbose output."""
        assert self.fn(verbose=True, show_all=True) == [
            f"!NA {SRC}:1 missing.bar",
            f"!NA {SRC}:2 missing.foo",
            f" OK {SRC}:3 test_1",
            f" OK {SRC}:4 test_main",
            f"!NA {SRC}:5 missing",
            f" OK {SRC}:7 check_dependencies",
            f"!NA {SRC}:11 missing_class",
            f"!NA {SRC}:15 missing",
            f"!NA {SRC}:16 missing_def",
        ]

    @pytest.mark.parametrize("show_all", [True, False])
    @pytest.mark.parametrize("include_extra", [True, False])
    def test_directory_only_one_use(self, show_all: bool, include_extra: bool) -> None:
        """Print out only one instance of a missing import.

        Even for multiple files, make sure we only print out one instance of a
        missing import.
        """
        res = self.fn(
            file_names=[DATA.as_posix()], show_all=show_all, include_dev=include_extra
        )
        assert len(res) == len(set(res))

    def test_directory_both_files(self) -> None:
        """Given a directory, we should check all files for missing imports."""
        res = self.fn(file_names=[DATA.as_posix()])
        assert set(res) > {"! missing", "! missing_src2"}

    def test_all_imports_all_files(self) -> None:
        """show_all=True should show all imports in all files."""
        res = self.fn(file_names=[SRC_MODULE.as_posix()], show_all=True)
        assert set(res) == {
            "  check_dependencies",
            "  test_1",
            "  test_main",
            "! missing",
            "! missing_class",
            "! missing_def",
            "! missing_src2",
            "! tests_main",
        }

    def test_doublette_entries(self) -> None:
        """Test that doublette entries are not printed twice."""
        res = self.fn(file_names=[SRC_MODULE.as_posix()] * 2, show_all=True)
        assert sorted(res) == [
            "  check_dependencies",
            "  test_1",
            "  test_main",
            "! missing",
            "! missing_class",
            "! missing_def",
            "! missing_src2",
            "! tests_main",
        ]

    def test_no_fail_on_missing_pyproject(self) -> None:
        """Test that we do not fail if the pyproject.toml is missing."""
        res = AppConfig.from_cli_args(
            file_names=["nonexistent.py"],
            known_extra="",
            known_missing="",
            provides=[],
            include_dev=False,
            verbose=False,
            show_all=False,
        )
        assert res

    def test_unicode_imports(self) -> None:
        """Test for Unicode module names."""
        result = self.fn(overwrite_cfg=PYPROJECT_UNICODE, file_names=[SRC_UNICODE])

        # All Unicode module names should be flagged as missing
        assert result == []

    def test_unicode_imports_verbose(self) -> None:
        """Test verbose output with Unicode module names."""
        result = self.fn(file_names=[SRC_UNICODE], verbose=True)

        # Should show file path and line numbers for Unicode imports
        assert any("ö" in line and SRC_UNICODE in line for line in result)
        assert any("café" in line and SRC_UNICODE in line for line in result)

    def test_fail_msg_on_nonexisting_file(self) -> None:
        """Test non-existing files."""
        missing_file = (SRC_MODULE / "non-existing.pyy").as_posix()
        res = self.fn(file_names=[missing_file])
        assert res[0] == f"!! {missing_file}"


@pytest.mark.parametrize(
    "stmt, expected",
    [
        ("import foo", ["foo"]),
        ("import foo as bar", ["foo"]),
        ("from foo import bar", ["foo"]),
        ("from foo import bar as baz", ["foo"]),
        ("from foo import bar, baz", ["foo"]),
        ("from . import bar", []),
        ("from .internal import bar", []),
        ("import foo\nimport bar", ["foo", "bar"]),
        ("import foo.bar", ["foo.bar"]),
        ("class X:\n    import foo", ["foo"]),
        ("def x():\n    import foo", ["foo"]),
        ("try:\n    import foo\nexcept ImportError:\n    import bar", ["foo", "bar"]),
    ],
)
def test_imports_iter(stmt: str, expected: list[str]) -> None:
    """Test the imports iterator for statement junks."""
    parsed = ast.parse(dedent(stmt))
    assert [x[0] for x in _imports_iter(parsed.body)] == expected


def test_missing_import_iter_silent_on_invalid_python_code() -> None:
    """Test that missing imports iterator catches invalid Python code."""
    my_path = MagicMock()
    my_path.as_posix.return_value = "dummy.py"
    my_path.read_bytes.return_value = b"()foo"
    res = list(_missing_imports_iter(my_path, set(), Packages([])))
    assert len(res) == 1
    status, filename, _ = res[0]
    assert status == Dependency.FILE_ERROR
    assert filename == "dummy.py"


def test_missing_imports_iter_non_utf8_encoding(tmp_path: Path) -> None:
    """Test that _missing_imports_iter works with a non-UTF8-encoded file."""
    py_file = tmp_path / "latin1_module.py"
    # Write a latin-1 encoded file with an encoding cookie and an import
    content = "# -*- coding: latin-1 -*-\nimport os\nx = 'caf\xe9'\n"
    py_file.write_bytes(content.encode("latin-1"))
    result = list(_missing_imports_iter(py_file, set(), Packages([])))
    assert [m for _, m, _ in result] == ["os"]


def test_missing_imports_iter() -> None:
    """Test the missing import iterator."""
    res = list(
        _missing_imports_iter(Path(SRC), {"test_0", "test_1", "extra"}, Packages([]))
    )
    assert {c for c, _, _ in res} == {Dependency.NA, Dependency.OK}
    assert [m for _, m, _ in res] == [
        "missing.bar",
        "missing.foo",
        "test_1",
        "test_main",
        "missing",
        "check_dependencies",
        "missing_class",
        "missing",
        "missing_def",
    ]
    assert None not in {s for _, _, s in res}


@pytest.mark.parametrize(
    "verbose, expected",
    [
        (True, "+EXTRA foo"),
        (False, "+ foo"),
    ],
)
def test_mk_unused_formatter(verbose: bool, expected: str) -> None:
    """Test the unused formatter."""
    cfg = AppConfig.from_cli_args(file_names=[DATA.as_posix()], verbose=verbose)
    assert list(cfg.unused_fmt("foo")) == [expected]


@pytest.mark.parametrize(
    "stmt, expected",
    [
        # Unicode in module names (valid syntax, but won't work at runtime)
        ("import ö", ["ö"]),
        ("import café", ["café"]),
        ("from ä import something", ["ä"]),
        ("import 日本語", ["日本語"]),
        ("from Москва import test", ["Москва"]),
        # Unicode in variable names is valid, but shouldn't be confused with imports
        ("import os\nö = 1", ["os"]),
        # Mixed ASCII and Unicode
        ("import foo_ö", ["foo_ö"]),
    ],
)
def test_imports_iter_unicode(stmt: str, expected: list[str]) -> None:
    """Test that Unicode module names are handled correctly.

    While Python 3 allows Unicode identifiers (PEP 3131), module names
    must correspond to file names, which are typically ASCII. The tool
    should still parse these correctly, even though they won't work at runtime.
    """
    parsed = ast.parse(dedent(stmt))
    assert [x[0] for x in _imports_iter(parsed.body)] == expected


def test_missing_imports_iter_unicode_file(tmp_path: Path) -> None:
    """Test _missing_imports_iter with a file containing Unicode imports.

    This verifies that the tool can parse files with Unicode module names
    (even though such imports would fail at runtime).
    """
    py_file = tmp_path / "unicode_imports.py"
    content = """# -*- coding: utf-8 -*-
import ö
from café import something
import sys
"""
    py_file.write_text(content, encoding="utf-8")

    result = list(_missing_imports_iter(py_file, {"sys"}, Packages([])))

    # Extract module names
    modules = [m for _, m, _ in result]

    # Should have detected all three imports
    assert "ö" in modules
    assert "café" in modules
    assert "sys" in modules

    # sys should be OK, Unicode modules should be NA
    statuses = {m: status for status, m, _ in result}
    assert statuses["sys"] == Dependency.OK
    assert statuses["ö"] == Dependency.NA
    assert statuses["café"] == Dependency.NA


@pytest.mark.performance
def test_performance_large_project(tmp_path: Path) -> None:
    """Test the performance of yield_wrong_imports on a large project."""
    max_duration_per_file = 0.01  # in seconds
    n_files = 1000
    for i in range(n_files):
        (tmp_path / f"file_{i}.py").write_text("import sys\n")
    cfg = AppConfig(
        dependencies=[],
        known_extra=[],
        known_missing=[],
        provides=Packages([]),
    )
    start = time.time()
    _ = list(yield_wrong_imports([tmp_path.as_posix()], cfg))
    duration = time.time() - start

    assert duration < max_duration_per_file * n_files
