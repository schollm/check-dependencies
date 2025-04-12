.PHONY: .ALWAYS
.ALWAYS:

test: .ALWAYS test-lint test-pytest test-mypy ## Run almost all tests (use test-all to include cli tests)

test-pytest: .ALWAYS  ## Run pytest
	uv run pytest src/tests/ --junit-xml=.out/junit-pytest.xml \
      --cov=src/check_dependencies \
      --cov-report=xml:.out/coverage.xml \
      --cov-report=html:.out/coverage-html \
      --cov-branch \
      --cov-fail-under 80

test-mypy: .ALWAYS  ## Run mypy
	uv run mypy --non-interactive --install-types --show-error-codes --strict --junit-xml=.out/junit-mypy-strict.xml \
	--exclude=src/tests/data  src/

test-lint: .ALWAYS
	uv run sh -c "ruff format --check src/ && ruff check src/"

test-static: test-lint test-mypy .ALWAYS  ## Run static tests

format: .ALWAYS
	uv run sh -c "ruff format src/; ruff check --fix"
