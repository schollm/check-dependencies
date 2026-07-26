from collections.abc import Iterable
from pathlib import Path
from typing import Sequence
from unittest.mock import patch

def run(
    files: Iterable[Path | str], pyproject_toml: Path, args: str | Sequence[str]= (), comment: bool = False
):
    lines: list[str] = []
    if isinstance(args, str):
        args = args.split()
    with (
        patch(
            "sys.argv",
            new=["check-dependencies", *(Path(f).as_posix() for f in files), *args],
        ),
        patch("check_dependencies.pyproject_toml._PYPROJECT_TOML", pyproject_toml),
        patch("sys.argv", ["check-dependencies", *args, *map(str, files)]),
        patch("check_dependencies.__main__._writer", lines.append),
    ):
        exit_satus = main()
    return [
        line
        for line in lines
        if line != "\n" and (comment or not line.startswith("#"))
    ], exit_satus



from check_dependencies.__main__ import main
