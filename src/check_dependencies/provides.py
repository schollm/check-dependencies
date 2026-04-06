"""Get the package provides modules mappings directly from an installed environment."""

from __future__ import annotations

import subprocess
from itertools import groupby
from pathlib import Path
from typing import Iterable


def mappings_for_env(python: Path) -> list[tuple[str, str]]:
    """Get the mappings.

    :arg python: Path to python executable belonging to the virtual
        environment, e.g. $VIRTUAL_ENV/bin/python.
    :return: a list of mappings of package name to module name.
    """
    return sorted(
        (package_name, import_name)
        for path in _get_paths(python)
        for record_file in path.glob("*.dist-info/")
        if record_file.is_dir()
        for package_name, import_name in _mapping_from_record(record_file)
    )


def collect_mappings(
    package_mappings: Iterable[tuple[str, str]],
) -> dict[str, list[str]]:
    """Collect package provides modules mappings directly from an installed environment.

    :param package_mappings: package mappings to collect, as an iterable
        of (package_name, import_name) tuples.
        The packages must be sorted.

    :return a mapping of packages to lists of module names.
    """
    return {
        key: sorted({value for _, value in values})
        for key, values in groupby(package_mappings, lambda x: x[0])
    }


def _mapping_from_record(dist_info_path: Path) -> Iterable[tuple[str, str]]:
    """Parse a single records file for python packages.

    :param dist_info_path: packages dist-info path.
    :return: DependencyMapping with pip name and import names.
    """
    package_name, _ = dist_info_path.stem.split("-", 1)

    record_file = dist_info_path / "RECORD"
    for import_name in _yield_modules(record_file.read_text("utf-8")):
        if package_name != import_name:
            yield package_name, import_name


def _yield_modules(package_content: str) -> Iterable[str]:
    seen = {""}
    for full_line in package_content.split("\n"):
        line = full_line.strip()
        if not (line.endswith(".py") or ".py," in line):
            continue

        root = Path(line).parts[0]
        if root.endswith(".dist-info"):
            continue

        if "." in root:
            root = root[: root.find(".")]
        if root not in seen:
            seen.add(root)
            yield root


def _get_paths(python: Path) -> Iterable[Path]:
    """Get all paths to check for dependencies."""
    proc = subprocess.run(  # noqa: S603
        [python.as_posix(), "-c", "import sys\nfor x in sys.path: print(x)"],
        capture_output=True,
        check=True,
        timeout=10,
        shell=False,
    )
    return (Path(p.strip()) for p in proc.stdout.decode().split("\n") if p.strip())
