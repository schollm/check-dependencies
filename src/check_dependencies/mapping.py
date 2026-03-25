from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from re import Pattern

_home_path_regex: Pattern[str] = re.compile(r"^home\s=\s(?P<home>.*)$", re.MULTILINE)
_include_system_site_packages_regex: Pattern[str] = re.compile(
    r"^include-system-site-packages\s=\s(?P<include_system_site_packages>.*)$",
    re.MULTILINE,
)


@dataclass(frozen=True)
class VenvConfig:
    base_installation_path: Path
    include_base_site_packages: bool


def parse_venv_config(file_content: str) -> VenvConfig:
    home_match = re.search(_home_path_regex, file_content)
    if home_match is None:
        raise RuntimeError("Could not parse `home` property from venv config")
    include_system_site_packages_match = re.search(
        _include_system_site_packages_regex, file_content
    )
    if include_system_site_packages_match is None:
        raise RuntimeError(
            "Could not parse `include-system-site-packages` property from venv config"
        )
    return VenvConfig(
        base_installation_path=Path(home_match.group("home")),
        include_base_site_packages=include_system_site_packages_match.group(
            "include_system_site_packages"
        ).lower()
        == "true",
    )


@dataclass(frozen=True)
class DependencyMapping:
    pip_name: str
    import_names: tuple[str]


def find_smallest_valid_index(indices: list[int]) -> int:
    valid_indices = [index for index in indices if index != -1]
    return min(valid_indices)


def create_mapping(pip_name: str, record_content: str) -> DependencyMapping:
    import_names: set[str] = set()
    for line in record_content.split("\n"):
        line = line.strip()
        if line != "":
            first_slash = line.find("/")
            first_dotpy = line.find(".py")
            potential_import_name = line[
                : find_smallest_valid_index([first_slash, first_dotpy])
            ]
            if not potential_import_name.endswith(".dist-info"):
                import_names.add(potential_import_name)
    return DependencyMapping(pip_name, tuple(sorted(import_names)))


def get_package_name_from_directory(directory_name: str) -> str:
    return directory_name[: directory_name.find("-")]


def gather_dependency_mappings(
    project_id: str, directory: Path
) -> set[DependencyMapping]:
    mappings: set[DependencyMapping] = set()
    for meta_directory in directory.glob("*.dist-info/"):
        # is_dir(): guard against bug pre py11: https://docs.python.org/3.11/whatsnew/3.11.html#pathlib
        if meta_directory.is_dir() and not meta_directory.name.startswith(project_id):
            mappings.add(
                create_mapping(
                    get_package_name_from_directory(meta_directory.name),
                    (meta_directory / "RECORD").read_text(),
                )
            )
    return mappings


def gather_venv_mappings(
    project_id: str, venv: Path
) -> set[DependencyMapping]:
    venv_config = parse_venv_config(
        (venv / "pyvenv.cfg").read_text()
    )
    mappings = gather_dependency_mappings(project_id, venv / "Lib" / "site-packages")
    if venv_config.include_base_site_packages:
        mappings.update(
            gather_dependency_mappings(
                project_id, venv_config.base_installation_path / "Lib" / "site-packages"
            )
        )
    return mappings


def _get_venv() -> Path:
    return Path(sys.prefix)


def _get_root_installation() -> Path:
    return Path(sys.base_prefix)


def _uses_venv() -> bool:
    return _get_venv() != _get_root_installation()


def get_mappings(project_id: str) -> set[DependencyMapping]:
    if _uses_venv():
        return gather_venv_mappings(project_id, _get_venv())
    return gather_dependency_mappings(project_id, _get_root_installation())
