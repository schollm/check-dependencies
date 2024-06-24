from __future__ import annotations

import pytest

import ast
from pathlib import Path
from textwrap import dedent
from typing import Sequence

from conftest import DATA, POETRY, POETRY_EXTRA, SRC

from check_dependencies.lib import Config, Dependency
from check_dependencies.main import (
    _imports_iter,
    _missing_imports_iter,
    yield_wrong_imports,
)


class TestYieldWrongImports:
    def fn(
        self,
        file_name: Sequence[str] = (SRC,),
        cfg_file: str | None = POETRY,
        include_dev: bool = False,
        verbose: bool = False,
        show_all: bool = False,
        extra_requirement: Sequence[str] = (),
        ignore_requirements: Sequence[str] = (),
    ) -> list[str]:
        return list(
            yield_wrong_imports(
                file_name,
                Config(
                    file=cfg_file,
                    include_dev=include_dev,
                    verbose=verbose,
                    show_all=show_all,
                    extra_requirements=extra_requirement,
                    ignore_requirements=ignore_requirements,
                ),
            )
        )

    def test(self) -> None:
        assert self.fn() == ["! missing", "! missing_class", "! missing_def"]

    def test_no_cfg(self) -> None:
        assert self.fn(cfg_file=None) == [
            "missing",
            "test_1",
            "test_main",
            "dependency_check_test",
            "missing_class",
            "missing_def",
        ]

    def test_extra_requirements(self) -> None:
        assert self.fn(cfg_file=POETRY_EXTRA) == [
            "! missing",
            "! missing_class",
            "! missing_def",
            "+ test_extra",
        ]

    def test_extra_requirements_as_cfg(self) -> None:
        """Do not flog unused requirements passed in as an extra"""
        assert self.fn(extra_requirement=["test_extra"]) == [
            "! missing",
            "! missing_class",
            "! missing_def",
        ]

    def test_ignore_requirements(self) -> None:
        assert self.fn(cfg_file=POETRY_EXTRA, ignore_requirements=["test_extra"]) == [
            "! missing",
            "! missing_class",
            "! missing_def",
        ]

    def test_ignore_requirements_still_check_in_src(self) -> None:
        assert self.fn(cfg_file=POETRY, ignore_requirements=["test_1"]) == [
            "! missing",
            "! missing_class",
            "! missing_def",
        ]

    def test_show_all(self) -> None:
        assert self.fn(show_all=True) == [
            "! missing",
            "  test_1",
            "  test_main",
            "  dependency_check_test",
            "! missing_class",
            "! missing_def",
        ]

    def test_include_dev(self) -> None:
        assert self.fn(include_dev=True) == [
            "! missing",
            "! missing_class",
            "! missing_def",
            "+ test_dev_1",
            "+ test_dev_2",
        ]

    def test_include_extra_requirements(self) -> None:
        res = self.fn(extra_requirement=["missing", "test_1"])
        assert res == ["! missing_class", "! missing_def"]

    def test_verbose(self) -> None:
        assert self.fn(verbose=True) == [
            f"!NA {SRC}:2 missing.bar",
            f"!NA {SRC}:3 missing.foo",
            f"!NA {SRC}:6 missing",
            f"!NA {SRC}:10 missing_class",
            f"!NA {SRC}:14 missing",
            f"!NA {SRC}:15 missing_def",
        ]

    def test_verbose_show_all(self) -> None:
        assert self.fn(verbose=True, show_all=True) == [
            f"!NA {SRC}:2 missing.bar",
            f"!NA {SRC}:3 missing.foo",
            f" OK {SRC}:4 test_1",
            f" OK {SRC}:5 test_main",
            f"!NA {SRC}:6 missing",
            " OK data/src.py:7 dependency_check_test",
            f"!NA {SRC}:10 missing_class",
            f"!NA {SRC}:14 missing",
            f"!NA {SRC}:15 missing_def",
        ]

    @pytest.mark.parametrize("show_all", [True, False])
    @pytest.mark.parametrize("include_dev", [True, False])
    def test_directory_only_one_use(self, show_all, include_dev) -> None:
        res = self.fn(file_name=[DATA], show_all=show_all, include_dev=include_dev)
        assert len(res) == len(set(res))

    def test_directory_both_files(self) -> None:
        res = self.fn(file_name=[DATA])
        assert set(res) > {"! missing", "! missing_src2"}

    def test_all_imports_all_files(self) -> None:
        res = self.fn(file_name=[DATA], show_all=True)
        assert set(res) == {
            "  dependency_check_test",
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
    parsed = ast.parse(dedent(stmt))
    assert [x[0] for x in _imports_iter(parsed.body)] == expected


def test_missing_imports_iter() -> None:
    seen: set[str] = set()
    res = list(
        _missing_imports_iter(Path(SRC), {"test_0", "test_1", "extra"}, seen=seen)
    )
    assert {c for c, _, _ in res} == {Dependency.NA, Dependency.OK}
    assert [m for _, m, _ in res] == [
        "missing.bar",
        "missing.foo",
        "test_1",
        "test_main",
        "missing",
        "dependency_check_test",
        "missing_class",
        "missing",
        "missing_def",
    ]
    assert seen == {
        "dependency_check_test",
        "missing",
        "missing_class",
        "missing_def",
        "test_1",
        "test_main",
    }
    assert None not in {s for _, _, s in res}


@pytest.mark.parametrize(
    "verbose, expected",
    [
        (True, "+EXTRA foo"),
        (False, "+ foo"),
    ],
)
def test_mk_unused_formatter(verbose: bool, expected: str) -> None:
    cfg = Config(file=POETRY, verbose=verbose)
    assert cfg.mk_unused_formatter()("foo") == expected
