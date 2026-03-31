"""Test for the mapping modules."""

from __future__ import annotations

import sys
from pathlib import Path
from textwrap import dedent

import pytest

from check_dependencies.writer import provides
from tests.conftest import DATA


def test_mappings_for_env() -> None:
    """Test the mapping function."""
    res = provides.mappings_for_env(Path(sys.executable))
    assert res


def test_mappings_for_env__mocked_python(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test mappings_for_env with mocked python."""
    monkeypatch.setattr(
        provides, "_get_paths", lambda _: [DATA / "mapping" / "site-packages"]
    )
    mappings = provides.mappings_for_env(Path("some-python"))
    assert mappings == {
        "mapped_package": ["_mapped_import_file", "mapped_import"],
        "pillow": ["PIL"],
    }
    assert sorted(mappings.keys()) == list(mappings.keys())


def test__get_paths() -> None:
    """Test the _get_paths function."""
    paths = list(provides._get_paths(Path(sys.executable)))
    assert paths


@pytest.mark.parametrize(
    "content, expected",
    [
        ("", set()),
        (
            dedent("""
            pillow.libs/lib.so,sha=abc123,123
            PIL/Image.py,sha256=abc123,123
            PIL/__init__.py,sha256=abc123,123
            PIL-1.0.0.dist-info/RECORD,sha256=abc123,123
            """),
            {"PIL"},
        ),
        ("package.lib/lib.so", set()),
        ("package.py", {"package"}),
        ("package/foo.py", {"package"}),
        ("package.dist-info/foo.py", set()),
        ("p1/foo.py\np2.py", {"p1", "p2"}),
        ("p1.py/foo.py", {"p1"}),
    ],
)
def test__yield_modules(content: str, expected: set[str]) -> None:
    """Test the _yield_modules function with various content inputs."""
    res = set(provides._yield_modules(content))
    assert res == expected
