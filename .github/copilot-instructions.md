# Copilot instructions for `check-dependencies`

## What this repo is
- `check-dependencies` is a small Python CLI/library that scans Python imports and compares them with dependencies declared in `pyproject.toml`.
- It supports multiple dependency declaration styles: PEP 621, Poetry, Hatch, and legacy `tool.uv` config.
- It also ships a second CLI, `dependency-writer`, which writes `[tool.check-dependencies.provides]` mappings from an environment into TOML.
- Repo shape: small `src/`-layout Python project, one package under `src/check_dependencies/`, tests under `src/tests/`, one GitHub Actions workflow.
- Target runtime from metadata/CI: Python `>=3.8`; CI covers 3.8–3.14 on Ubuntu, plus 3.14 on Windows and macOS.
- Tooling in use: `uv`, `poethepoet`, `pytest`, `pytest-cov`, `ruff`, `ty`, `pdm-backend`.

## Trust these instructions first
- Prefer the commands and file locations below instead of rediscovering them.
- Only search further if these instructions are incomplete or contradicted by the files you are editing.

## Always do this first
1. `cd` to the repo root.
2. Prefer `uv run ...` for all local commands.

## Validated command recipes
### Bootstrap
```shell
cd repository_root; uv sync
```
- Worked immediately.
- `uv sync` resolved/checked packages successfully.

### Full local validation (recommended before finishing a change)
```shell
uv run poe check
```
- This runs, in order: `ruff format src/`, `ruff check --fix src/`, `ty check src/`, `pytest src/tests`.
- This is the best local approximation of the repo’s quality gate.

### Lint / format only
```shell
uv run poe lint  # ruff format; ruff check --fix
```

### Typing
```shell
uv run poe typing  # ty check src/
```

### Tests
```shell
uv run poe pytest  # pytest src/tests
```
- `pyproject.toml` adds coverage/junit output automatically:
  - `.out/junit-pytest.xml`
  - `.out/coverage.xml`
  - `.out/coverage-html/`
- Default pytest config excludes `@pytest.mark.performance`.

### Performance tests
```shell
uv run pytest -m performance
```
- Only runs the explicitly marked performance test(s).
- This also rewrites `.out/coverage*`; rerun normal pytest afterwards if you need the usual coverage artifacts again.

### Run the main CLI
```shell
uv run check-dependencies src/check_dependencies
```
- Exit codes are documented in `README.md`; nonzero is expected when missing/extra dependencies are found.

### Run the writer CLI
```shell
uv run dependency-writer --python .venv\Scripts\python.exe --config -
```
- Worked and printed a TOML snippet to stdout.
- On Linux/macOS, use `.venv/bin/python` instead.
- `dependency-writer` imports `tomlkit` at module import time. In this dev repo it is present via dev dependencies; for package users it is the optional `write` extra.

### Build
```shell
uv build  # Produces `dist/*.tar.gz` and `dist/*.whl`.
````

## Important repo-specific gotchas
- Keep dependencies minimal. The project intentionally has almost no runtime dependencies (`toml` only for Python < 3.11).
- The package uses `src/` layout. Production code is in `src/check_dependencies/`; tests are in `src/tests/`.
- Frozen dataclasses are good, avoid mutable classes.
- Also avoid mutable state within functions and functions with side effects.
- Prefer list comprehensions or generator functions over mutable lists. 
- The most important architectural files are:
  - `src/check_dependencies/__main__.py` — CLI argument parsing and entry point.
  - `src/check_dependencies/main.py` — import scanning, file walking, exit-status logic.
  - `src/check_dependencies/app_config.py` — merges CLI args, included config files, venv-provided mappings.
  - `src/check_dependencies/pyproject_toml.py` — parses dependency metadata from PEP 621 / Poetry / Hatch / legacy uv.
  - `src/check_dependencies/lib.py` — core `Package`, `Module`, `Packages`, `Dependency` abstractions.
  - `src/check_dependencies/provides.py` — derives package→import mappings from installed `.dist-info/RECORD` files.
  - `src/check_dependencies/writer.py` — writer CLI for generating/updating provides mappings.
- If you change dependency parsing behavior, also inspect:
  - `src/tests/test_pyproject_toml.py`
  - `src/tests/test_main.py`
  - fixtures in `src/tests/data/pyproject_*.toml`
- If you change CLI output or exit behavior, update tests first; `src/tests/test_main.py` is the highest-value test file.
- `src/tests/check-dependencies.toml` is included by default from `[tool.check-dependencies]` in the root `pyproject.toml`; it affects many tests and self-check behavior.
- CI workflow file is `.github/workflows/python.yml`. Before considering a change “done”, make sure it is compatible with:
  - Ruff lint + format check
  - pytest on Python 3.8–3.14
  - `uv build`
- Adapt CHANGELOG.md and README.md as appropriate for user-facing changes.

## Quick layout reference
### Repo root
- `pyproject.toml` — project metadata, tasks, pytest config, ruff config, build backend.
- `uv.lock` — lockfile.
- `README.md` — user-facing CLI docs and examples.
- `CONTRIBUTING.md` — maintainer-preferred dev workflow.
- `.github/workflows/python.yml` — CI/build/publish pipeline.
- `src/` — code and tests.

### Under `src/`
- `check_dependencies/` — package code.
- `tests/` — pytest suite and test fixtures.

## If you need confidence beyond unit tests
Run this exact sequence:
```shell
uv run poe check
uv run check-dependencies src/check_dependencies
uv build
```
That sequence exercises setup, lint, typing, tests, packaging, and the primary CLI.
