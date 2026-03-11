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
make test  # Run all tests
make test-static  # Run static tests
make test-pytest  # Run pytest tests
make test-typing  # Run mypy type checks
make test-lint  # Run lint and format checks
```

Format and auto-fix lint issues:

```bash
make format  # Format code and apply ruff fixes
```

## Code guidelines

- Keep changes focused and minimal.
- Add or adjust tests for behavioral changes.
- Preserve strict typing (`mypy --strict` should stay clean).
- Follow existing style and naming conventions.

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
