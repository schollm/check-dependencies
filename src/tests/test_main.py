"""Test the main module"""

from __future__ import annotations

import ast
from pathlib import Path
from textwrap import dedent
from typing import Sequence
from unittest.mock import patch

import pytest

from check_dependencies.lib import AppConfig, Dependency
from check_dependencies.main import (
    _imports_iter,
    _missing_imports_iter,
    yield_wrong_imports,
)
from tests.conftest import DATA, POETRY, PYPROJECT_CFG, SRC


class TestYieldWrongImports:
    """Test collection for the yield wrong imports function"""

    def fn(  # pylint: disable=too-many-arguments
        self,
        overwrite_cfg: Path = POETRY,
        file_names: Sequence[str] = (SRC,),
        include_extra: bool = False,
        verbose: bool = False,
        show_all: bool = False,
        known_extra: Sequence[str] = (),
        known_missing: Sequence[str] = (),
    ) -> list[str]:
        """Helper function to call the yield wrong imports function"""
        with patch("check_dependencies.lib._PYPROJECT_TOML", overwrite_cfg):
            return list(
                yield_wrong_imports(
                    file_names,
                    AppConfig(
                        include_dev=include_extra,
                        verbose=verbose,
                        show_all=show_all,
                        known_extra=known_extra,
                        known_missing=known_missing,
                    ),
                )
            )

    def test(self, pyproject) -> None:
        """By default, we should only see the missing (and extra) imports"""
        assert self.fn(overwrite_cfg=pyproject) == [
            "! missing",
            "! missing_class",
            "! missing_def",
        ]

    def test_extra_requirements(self, pyproject_extra) -> None:
        """Ensure extra requirements are printed by default"""
        assert self.fn(overwrite_cfg=pyproject_extra) == [
            "! missing",
            "! missing_class",
            "! missing_def",
            "+ test_extra",
        ]

    def test_extra_requirements_as_cfg(self) -> None:
        """Do not flog unused requirements passed in as an extra"""
        assert not self.fn(overwrite_cfg=PYPROJECT_CFG)

    def test_ignore_requirements(self, pyproject_extra) -> None:
        """Ensure ignored requirements are not printed"""
        assert self.fn(overwrite_cfg=pyproject_extra, known_extra=["test_extra"]) == [
            "! missing",
            "! missing_class",
            "! missing_def",
        ]

    def test_ignore_requirements_still_check_in_src(self) -> None:
        """Ensure ignored requirements are not flagged even if they come up in src"""
        assert "  test_1" in self.fn(overwrite_cfg=POETRY, show_all=True)
        assert self.fn(overwrite_cfg=POETRY, known_missing=["test_1"]) == [
            "! missing",
            "! missing_class",
            "! missing_def",
        ]

    def test_show_all(self) -> None:
        """Show all imports, including correct ones"""
        assert self.fn(show_all=True) == [
            "! missing",
            "  test_1",
            "  test_main",
            "  check_dependencies",
            "! missing_class",
            "! missing_def",
        ]

    def test_include_extra(self) -> None:
        """Include development dependencies in the check"""
        assert self.fn(include_extra=True) == [
            "! missing",
            "! missing_class",
            "! missing_def",
            "+ test_dev_1",
            "+ test_dev_2",
        ]

    def test_include_extra_requirements(self) -> None:
        """Include extra requirements that are not part of the dependencies in the check"""
        res = self.fn(known_missing=["missing", "test_1"])
        assert res == ["! missing_class", "! missing_def"]

    def test_verbose(self) -> None:
        """Verbose output should include the file and line number of the import"""
        assert self.fn(verbose=True) == [
            f"!NA {SRC}:2 missing.bar",
            f"!NA {SRC}:3 missing.foo",
            f"!NA {SRC}:6 missing",
            f"!NA {SRC}:12 missing_class",
            f"!NA {SRC}:16 missing",
            f"!NA {SRC}:17 missing_def",
        ]

    def test_verbose_show_all(self) -> None:
        """This is the most verbose output possible"""
        assert self.fn(verbose=True, show_all=True) == [
            f"!NA {SRC}:2 missing.bar",
            f"!NA {SRC}:3 missing.foo",
            f" OK {SRC}:4 test_1",
            f" OK {SRC}:5 test_main",
            f"!NA {SRC}:6 missing",
            f" OK {SRC}:8 check_dependencies",
            f"!NA {SRC}:12 missing_class",
            f"!NA {SRC}:16 missing",
            f"!NA {SRC}:17 missing_def",
        ]

    @pytest.mark.parametrize("show_all", [True, False])
    @pytest.mark.parametrize("include_extra", [True, False])
    def test_directory_only_one_use(self, show_all, include_extra) -> None:
        """Even for multiple files, make sure we only print out one instance of
        a missing import"""
        res = self.fn(file_names=[DATA], show_all=show_all, include_extra=include_extra)
        assert len(res) == len(set(res))

    def test_directory_both_files(self) -> None:
        """Given a directory, we should check all files for missing imports"""
        res = self.fn(file_names=[DATA])
        assert set(res) > {"! missing", "! missing_src2"}

    def test_all_imports_all_files(self) -> None:
        """show_all=True should show all imports in all files"""
        res = self.fn(file_names=[DATA], show_all=True)
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
    ],
)
def test_imports_iter(stmt: str, expected: list[str]) -> None:
    """Test the imports iterator for statement junks"""
    parsed = ast.parse(dedent(stmt))
    assert [x[0] for x in _imports_iter(parsed.body)] == expected


def test_missing_imports_iter() -> None:
    """Test the missing imports iterator"""
    res = list(_missing_imports_iter(Path(SRC), {"test_0", "test_1", "extra"}))
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
    """Test the unused formatter"""
    cfg = AppConfig(verbose=verbose)
    assert list(cfg.unused_fmt("foo")) == [expected]
