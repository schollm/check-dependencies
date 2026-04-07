# Contributing

Thanks for contributing to `check-dependencies`!


## Development setup

### Requirements
- Python 3.8+
- [uv](https://docs.astral.sh/uv/) (recommended)

### Install
```bash
uv sync
```

## Common tasks

Run tests:

```bash
poe check  # Run all checks (lint, typing, and tests)
poe lint  # Format and lint code
poe pytest  # Run pytest tests
poe typing  # Run ty type checks
```

### Performance tests

Performance tests are marked with `@pytest.mark.performance`.

By default, they are excluded via `pyproject.toml`.

Run performance tests explicitly when needed:

```bash
uv run pytest -m performance
```

Format and auto-fix lint issues:

```bash
poe lint  # Format code and apply ruff fixes
```

## Code guidelines

Please make sure to update tests as appropriate. Also with this project, I want
to keep the dependencies to a minimum, so please keep that in mind when proposing
a change. Currently, the only dependencies is `toml` to support Python 3.10 and below and
`tomlkit` as an extra for the `dependency-writer` CLI.

- Keep changes focused and minimal.
- Add or adjust tests for behavioral changes.
- Preserve strict typing (`ty check` should stay clean).
- Follow existing style and naming conventions.
- Use a functional approach where possible, minimizing class usage unless it provides clear benefits.
- Frozen dataclasses are preferred when a class is necessary, to ensure immutability and simplicity.
- When in doubt, prioritize simplicity and readability.
- Avoid mutable state and side effects; prefer pure functions.

### Coding Standards

| **Type**      | Package      | Comment                      |
|---------------|--------------|------------------------------|
| **Logging**   | `logger`     | Minimize additional packages |
| **Packaging** | `uv`         |                              |
| **Tests**     | `pytest`     |                              |
| **Typing**    | `ty`         | Type all methods             |
| **Linting**   | `ruff`       | Also used for formatting     |
| **CLI**       | `argparse`   | Avoid click/typer to minimize dependencies |
| **Runner**    | `poethepoet` | Use `poe` for task automation |

## Commit and PR guidelines

- Use clear, descriptive commit messages.
- Open small, reviewable pull requests.
- In PR descriptions, include:
  - what changed
  - why it changed
  - how it was tested

## Reporting issues

When opening an issue, please include:
- expected behavior
- actual behavior
- reproduction steps
- Python version and platform

Thanks again for helping improve this project.
