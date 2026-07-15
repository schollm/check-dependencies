"""Tests for outputs module."""

import ast
from pathlib import Path
from typing import NamedTuple

import pytest

from check_dependencies import outputs
from check_dependencies.app_config import ProjectConfig
from check_dependencies.lib import Module, Package, Packages

PATH = Path("foo.py")
MODULE = Module("my_module")
PACKAGE = Package("MyPackage")
STMT = ast.Pass(lineno=1, col_offset=4, end_lineno=1, end_col_offset=8)
PRJ_CFG = ProjectConfig(
    known_missing=(),
    defined_dependencies=(),
    allowed_dependencies=(),
    known_extra=(),
    packages=Packages(),
    path=Path("foo/pyproject.toml"),
)

OUT_OK = outputs.OkDependency(PATH, STMT, MODULE)
OUT_NO_PYPROJECT = outputs.NoPyprojectError("/foo/pyproject.toml")
OUT_EXTRA = outputs.ExtraPackage(PRJ_CFG, PACKAGE)
OUT_FILE_ERROR = outputs.FileError(PATH, "Parsing failure")
OUT_INFO = outputs.InfoMessage("message", verbose=False)
OUT_INFO_VERBOSE = outputs.InfoMessage("message", verbose=True)
OUT_MISSING = outputs.MissingModule(PATH, STMT, MODULE)
OUT_UNKNOWN = outputs.UnknownModule(PATH, STMT, MODULE)


class TextResult(NamedTuple):
    """All possible results of an output."""

    default: str | None
    verbose: str | None
    show_all: str | None
    both: str | None


@pytest.mark.parametrize("verbose", [True, False])
@pytest.mark.parametrize("show_all", [True, False])
@pytest.mark.parametrize(
    "output, expected",
    [
        (OUT_OK, TextResult(None, None, "  my_module", " OK foo.py:1 my_module")),
        (
            OUT_NO_PYPROJECT,
            TextResult(
                "!! /foo/pyproject.toml",
                "!!NOPYPROJECT /foo/pyproject.toml",
                "<<",
                "<<",
            ),
        ),
        (OUT_EXTRA, TextResult("+ MyPackage", "+EXTRA MyPackage", "<<", "<<")),
        (OUT_FILE_ERROR, TextResult("!! foo.py", "!!FILE foo.py", "<<", "<<")),
        (OUT_INFO, TextResult(None, "# message", "<<", "<<")),
        (OUT_INFO_VERBOSE, TextResult("# message", "<<", "<<", "<<")),
        (OUT_MISSING, TextResult("! my_module", "!NA foo.py:1 my_module", "<<", "<<")),
        (
            OUT_UNKNOWN,
            TextResult("? my_module", "?UNKNOWN foo.py:1 my_module", "<<", "<<"),
        ),
    ],
)
def test_as_text(
    output: outputs.Output, expected: TextResult, verbose: bool, show_all: bool
) -> None:
    """Test that the as_text method returns the expected output."""
    idx = verbose + int(show_all) * 2
    res = output.to_text(verbose=verbose, show_all=show_all, seen=set())
    expected_res = expected[idx]
    if expected_res == "<<":
        expected_res = expected[int(verbose)]
        if expected_res == "<<":
            expected_res = expected[0]
    if expected_res is None:
        assert list(res) == []
    else:
        assert "--".join(res) == expected_res.format(
            file=PATH.absolute().as_posix(),
            path=PATH.parent.absolute().as_posix(),
        )
