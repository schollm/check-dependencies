"""Tests for renderer module."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from check_dependencies.app_config import OutputFormat, ProjectConfig
from check_dependencies.lib import Module, Package, Packages
from check_dependencies.outputs import ExtraPackage, MissingModule, OkDependency
from check_dependencies.renderer import make_renderer


@pytest.fixture
def stmt() -> ast.stmt:
    """AST import statement fixture."""
    return ast.parse("import foo.bar").body[0]


def _project_cfg() -> ProjectConfig:
    return ProjectConfig(
        known_missing=(),
        defined_dependencies=(),
        allowed_dependencies=(),
        known_extra=(),
        packages=Packages(),
        path=Path("pyproject.toml"),
        optional_dependencies={},
    )


@pytest.mark.parametrize("verbose", [True, False])
def test_renderer_no_show_all_on_status_ok(stmt: ast.stmt, verbose: bool) -> None:
    """If the import is expected, we do not show it in concise mode."""
    formatter = make_renderer(output_format=OutputFormat.CONCISE, verbose=verbose)
    lines = formatter(
        OkDependency(path=Path("src.py"), stmt=stmt, module=Module("foo.bar"))
    )
    assert list(lines) == []


@pytest.mark.parametrize(
    "verbose, output_format, output, expected",
    [
        (True, OutputFormat.CONCISE, MissingModule, "!NA src.py:1 foo"),
        (True, OutputFormat.FULL, MissingModule, "!NA src.py:1 foo"),
        (True, OutputFormat.FULL, OkDependency, " OK src.py:1 foo"),
        (False, OutputFormat.CONCISE, MissingModule, "! foo"),
        (False, OutputFormat.FULL, MissingModule, "! foo"),
        (False, OutputFormat.FULL, OkDependency, "  foo"),
    ],
)
def test_text_renderer(
    stmt: ast.stmt,
    verbose: bool,
    output_format: OutputFormat,
    output: type[MissingModule | OkDependency],
    expected: str,
) -> None:
    """Render text output according to verbosity and format."""
    formatter = make_renderer(output_format=output_format, verbose=verbose)
    lines = formatter(output(path=Path("src.py"), stmt=stmt, module=Module("foo")))
    assert next(lines) == expected
    assert list(lines) == []


def test_renderer_cache(stmt: ast.stmt) -> None:
    """Formatter emits deduplicated concise output across calls."""
    formatter = make_renderer(output_format=OutputFormat.CONCISE, verbose=False)
    lines = [
        *formatter(MissingModule(path=Path("src.py"), stmt=stmt, module=Module("foo"))),
        *formatter(MissingModule(path=Path("src.py"), stmt=stmt, module=Module("foo"))),
    ]
    assert len(lines) == 1


def test_renderer_github() -> None:
    """Renderer emits GitHub annotations in GitHub mode."""
    formatter = make_renderer(output_format=OutputFormat.GITHUB, verbose=False)
    project_cfg = _project_cfg()
    output = ExtraPackage(project_cfg=project_cfg, package=Package("foo"))
    assert list(formatter(output))
