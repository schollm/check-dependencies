from pathlib import Path

DATA = Path(__file__).parent / "data"
try:
    DATA = DATA.resolve().relative_to(Path().resolve())
except ValueError:
    pass

SRC = (DATA / "src.py").as_posix()

POETRY = (DATA / "pyproject_poetry_test.toml").as_posix()
POETRY_EXTRA = (DATA / "pyproject_poetry_extra.toml").as_posix()
