"""Test Optional dependencies parts."""

import textwrap
from pathlib import Path

import pytest

from tests.run import run


def test(tmp_path: Path):
    """Test tool.check-dependencies.optionals in pyproject.toml."""
    pyproject_toml = textwrap.dedent("""\
        [project]
        dependencies = ["foo==*"]
        [project.optional-dependencies]
        optional1 = ["dep1", "dep2"]
        dev = ["dep3"]

        [tool.check-dependencies.optionals]
        optional1 = ["src/src2.py"]
        dev = ["tests/"]
        """)
    src_files = [
        ("pp.toml", pyproject_toml),
        ("tests/test.py", "import dep3"),
        ("src/src2.py", "import dep1, dep2"),
        ("src/src1.py", "import foo"),
    ]
    for file, data in src_files:
        p = tmp_path / file
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(data, encoding="utf-8")

    res = run([tmp_path / x for (x, _) in src_files[1:]], tmp_path / "pp.toml")
    assert res[0] == []


@pytest.mark.parametrize(
    "src_files, expect",
    [
        (
            {"src/src1.py": "import foo, opt1", "src/opt.py": "import opt1, opt2"},
            (["! opt1"], 2),
        ),
        (
            {"src/src1.py": "import foo, opt1", "src/opt.py": "import opt2"},
            (["! opt1"], 2),
        ),
        (
            {
                "src/src.py": "import opt1",
                "src/opt.py": "import opt1, opt2",
                "tests/t.py": "import dev1, foo",
            },
            (["! opt1"], 2),
        ),
        (
            {
                "src/src.py": "import foo",
                "src/opt.py": "import opt1, opt2",
                "tests/t.py": "import dev1, foo",
            },
            ([], 0),
        ),
        (
            {"src/src.py": "import foo"},
            ([], 0),
        ),
        (
            {"src/opt.py": "import foo"},
            (["+ opt1", "+ opt2"], 4),
        ),
    ],
)
def test_optional_dependencies(
    src_files: dict[str, str], expect: tuple[list[str], int], tmp_path: Path
):
    """Test tool.check-dependencies.optional-dependencies in pyproject.toml."""
    pyproject_toml = textwrap.dedent("""\
        [project]
        dependencies = ["foo==*"]

        [project.optional-dependencies]
        optional1 = ["opt1", "opt2"]
        dev = ["dev1"]

        [tool.check-dependencies.optional-dependencies]
        optional1 = ["src/opt.py"]
        dev = ["tests/"]
        """)

    pp = tmp_path / "pyproject.toml"
    files = {tmp_path / file: content for file, content in src_files.items()}
    pp.write_text(pyproject_toml)
    for file, content in files.items():
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content, encoding="utf-8")

    res, exit_code = run(files.keys(), pp)

    assert (res, exit_code) == expect


@pytest.mark.parametrize(
    "src_files, expect",
    [
        (
            {"src/src1.py": "import foo, opt1", "src/opt.py": "import opt2"},
            (["+ dev1"], 4),
        ),
        (
            {
                "src/src.py": "import foo",
                "src/opt.py": "import opt1, opt2",
                "tests/t.py": "import dev1, foo",
            },
            ([], 0),
        ),
        (
            {"src/src.py": "import foo"},
            (["+ dev1", "+ opt1", "+ opt2"], 4),
        ),
        (
            {"src/opt.py": "import foo"},
            (["+ dev1", "+ opt1", "+ opt2"], 4),
        ),
    ],
)
def test_optional_dependencies_no_config(
    src_files: dict[str, str], expect: tuple[list[str], int], tmp_path: Path
):
    """Test tool.check-dependencies.optional-dependencies in pyproject.toml."""
    pyproject_toml = textwrap.dedent("""\
        [project]
        dependencies = ["foo==*"]

        [project.optional-dependencies]
        optional1 = ["opt1", "opt2"]
        dev = ["dev1"]
        """)

    pp = tmp_path / "pyproject.toml"
    files = {tmp_path / file: content for file, content in src_files.items()}
    for file, content in (files | {pp: pyproject_toml}).items():
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content, encoding="utf-8")

    res, exit_code = run(files.keys(), pp)

    assert (res, exit_code) == expect


@pytest.mark.parametrize(
    "src_files, expect",
    [
        ({"src/src1.py": "import foo"}, ([], 0)),
        (
            {"src/src1.py": "import foo", "src/opt.py": "import opt1, opt2"},
            ([], 0),
        ),
        (
            {
                "src/src.py": "import foo",
                "src/opt.py": "import foo, opt1, opt2",
                "tests/t.py": "import dev1, foo",
            },
            ([], 0),
        ),
        (
            {
                "src/src.py": "import foo",
                "src/opt.py": "import opt1",
                "tests/t.py": "import dev1, foo",
            },
            (["+ opt2"], 4),
        ),
        (
            {
                "src/opt.py": "import foo",
                "tests/t.py": "import foo",
            },
            (["+ dev1", "+ opt1", "+ opt2"], 4),
        ),
        (
            {
                "src/opt.py": "",
                "tests/t.py": "",
            },
            (["+ dev1", "+ foo==*", "+ opt1", "+ opt2"], 4),
        ),
        (
            {"src/src.py": "import foo"},
            ([], 0),
        ),
        ({"src/opt.py": "import foo"}, (["+ opt1", "+ opt2"], 4)),
    ],
)
def test_dependency_groups_dependencies(
    src_files: dict[str, str], expect: tuple[list[str], int], tmp_path: Path
):
    """Test tool.check-dependencies.optional-dependencies in pyproject.toml."""
    pyproject_toml = textwrap.dedent("""\
        [project]
        dependencies = ["foo==*"]

        [project.optional-dependencies]
        optional1 = ["opt1", "opt2"]
        dev = ["dev1"]

        [tool.check-dependencies.optional-dependencies]
        optional1 = ["src/opt.py"]
        dev = ["tests/"]
        """)

    pp = tmp_path / "pyproject.toml"
    files = {tmp_path / file: content for file, content in src_files.items()}
    pp.write_text(pyproject_toml)
    for file, content in files.items():
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content, encoding="utf-8")

    res, exit_code = run(files.keys(), pp)

    assert (sorted(res), exit_code) == expect


@pytest.mark.parametrize(
    "src_files, expect",
    [
        (
            {"src/src1.py": "import foo, both", "src/opt.py": "import both, opt2"},
            ([], 0),
        ),
        (
            {"src/src1.py": "import foo", "src/opt.py": "import both, opt2"},
            (["+ both"], 4),
        ),
        (
            {"src/src1.py": "import foo, both", "src/opt.py": "import opt2"},
            ([], 0),
        ),
    ],
)
def test_dependency_groups_dependencies_in_both_main_and_optional(
    src_files: dict[str, str], expect: tuple[list[str], int], tmp_path: Path
):
    """Test tool.check-dependencies.optional-dependencies in pyproject.toml."""
    pyproject_toml = textwrap.dedent("""\
        [project]
        dependencies = ["foo", "both"]

        [project.optional-dependencies]
        optional1 = ["both", "opt2"]
        dev = ["dev1"]

        [tool.check-dependencies.optional-dependencies]
        optional1 = ["src/opt.py"]
        dev = ["tests/"]
        """)

    pp = tmp_path / "pyproject.toml"
    files = {tmp_path / file: content for file, content in src_files.items()}
    pp.write_text(pyproject_toml)
    for file, content in files.items():
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content, encoding="utf-8")

    res, exit_code = run(files.keys(), pp)

    assert (sorted(res), exit_code) == expect


def test_optional_dependencies_and_extra(tmp_path: Path) -> None:
    """Test optional dependencies with extras in pyproject.toml."""
    src_files = {"src/src1.py": "import foo, both", "src/opt.py": "import opt2"}
    expect = ([], 0)
    pyproject_toml = textwrap.dedent("""\
        [project]
        dependencies = ["foo", "both"]

        [project.optional-dependencies]
        optional1 = ["opt-extra > 1.0.0", "opt2"]

        [tool.check-dependencies.optional-dependencies]
        optional1 = ["src/opt.py"]

        [tool.check-dependencies]
        known-extra = ["opt-extra"]
        """)

    pp = tmp_path / "pyproject.toml"
    files = {tmp_path / file: content for file, content in src_files.items()}
    pp.write_text(pyproject_toml)
    for file, content in files.items():
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content, encoding="utf-8")

    res, exit_code = run(files.keys(), pp)

    assert (sorted(res), exit_code) == expect
