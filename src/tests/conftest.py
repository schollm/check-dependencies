"""Common fixtures and constans for tests."""

import contextlib
from pathlib import Path

import pytest

DATA = Path(__file__).parent / "data"
with contextlib.suppress(ValueError):
    DATA = DATA.resolve().relative_to(Path.cwd())

SRC = (DATA / "src.py").as_posix()
PEP631 = DATA / "pyproject_pep631.toml"
PEP631_EXTRA = DATA / "pyproject_pep631_extra.toml"
POETRY = DATA / "pyproject_poetry.toml"
POETRY_EXTRA = DATA / "pyproject_poetry_extra.toml"
PYPROJECT_CFG = DATA / "pyproject_cfg.toml"


@pytest.fixture(params=[PEP631, POETRY])
def pyproject(request: pytest.FixtureRequest) -> Path:
    """Fixture for testing pyproject.toml files."""
    return request.param  # type: ignore[attr-defined]


@pytest.fixture(params=[PEP631_EXTRA, POETRY_EXTRA])
def pyproject_extra(request: pytest.FixtureRequest) -> Path:
    """Fixture for testing extra requirements."""
    return request.param  # type: ignore[attr-defined]
