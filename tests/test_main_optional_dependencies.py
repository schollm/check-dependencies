import textwrap
from pathlib import Path

import pytest

from tests.run import run


def test(tmp_path: Path):
    """Test tool.check-dependencies.optionals in pyproject.toml"""
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


@pytest.mark.xfail
def test_extra_in_non_extra(tmp_path: Path):
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

    src_files = {
        tmp_path / "tests/test.py": "import dep3",
        tmp_path / "src/src2.py": "import dep1, dep2",
        tmp_path / "src/src1.py": "import dep1, foo",
    }
    (pp := (tmp_path / "pp.toml")).write_text(pyproject_toml)
    for file, data in src_files.items():
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(data, encoding="utf-8")

    res = run(src_files.keys(), pp)
    assert res[0] == ["! dep1"]
