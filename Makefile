.PHONY: .ALWAYS
.ALWAYS:
format: .ALWAYS
	uv run sh -c "ruff format src/; ruff check --fix"

test: .ALWAYS test-static test-pytest ## Run almost all tests (use test-all to include cli tests)
test-static: test-lint test-mypy .ALWAYS  ## Run static tests

test-pytest: .ALWAYS  ## Run pytest
	uv run pytest src/tests/ --junit-xml=.out/junit-pytest.xml \
      --cov=src/check_dependencies \
      --cov-report=xml:.out/coverage.xml \
      --cov-report=html:.out/coverage-html \
      --cov-branch

test-mypy: .ALWAYS  ## Run mypy
	uv run mypy --non-interactive --install-types --show-error-codes --strict --junit-xml=.out/junit-mypy-strict.xml \
	--exclude=src/tests/data  src/

test-lint: .ALWAYS
	uv run ruff format --check src/
	uv run ruff check src/

