.PHONY: .ALWAYS
.ALWAYS:
format: .ALWAYS
	uv run sh -c "ruff format src/; ruff check --fix"

test: .ALWAYS test-static test-pytest ## Run almost all tests (use test-all to include cli tests)
test-static: test-lint test-typing .ALWAYS  ## Run static tests

test-pytest: .ALWAYS  ## Run pytest
	uv run pytest src/tests/

test-typing: .ALWAYS  ## Run mypy
	uv run mypy --non-interactive src/

test-lint: .ALWAYS
	uv run ruff format --check src/
	uv run ruff check src/

