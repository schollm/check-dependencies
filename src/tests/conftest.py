"""Common fixtures and constans for tests."""

from pathlib import Path

import pytest

DATA = (Path(__file__).parent / "data").resolve()
SRC_MODULE = DATA / "src"
SRC = (SRC_MODULE / "src.py").as_posix()
SRC_UNICODE = (DATA / "src_unicode.py").as_posix()
PYPROJECT_UNICODE = DATA / "pyproject_unicode.toml"
PEP631 = DATA / "pyproject_pep631.toml"
PEP631_EXTRA = DATA / "pyproject_pep631_extra.toml"
POETRY = DATA / "pyproject_poetry.toml"
POETRY_EXTRA = DATA / "pyproject_poetry_extra.toml"
HATCH = DATA / "pyproject_hatch.toml"
HATCH_EXTRA = DATA / "pyproject_hatch_extra.toml"
UV_LEGACY = DATA / "pyproject_uv_legacy.toml"
UV_LEGACY_EXTRA = DATA / "pyproject_uv_legacy_extra.toml"
PYPROJECT_CFG = DATA / "pyproject_cfg.toml"
PYPROJECT_EMPTY = DATA / "pyproject_empty.toml"
PYPROJECT_PROVIDES = DATA / "pyproject_pep631_provides.toml"


@pytest.fixture(params=[PEP631, POETRY, HATCH, UV_LEGACY])
def pyproject(request: pytest.FixtureRequest) -> Path:
    """Fixture for testing pyproject.toml files."""
    return request.param


@pytest.fixture(params=[PEP631_EXTRA, POETRY_EXTRA, HATCH_EXTRA, UV_LEGACY_EXTRA])
def pyproject_extra(request: pytest.FixtureRequest) -> Path:
    """Fixture for testing extra requirements."""
    return request.param
