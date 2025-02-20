.PHONY: .ALWAYS
.ALWAYS:

test: .ALWAYS test-lint test-pytest test-mypy ## Run almost all tests (use test-all to include cli tests)

test-pytest: .ALWAYS  ## Run pytest
	poetry run pytest src/tests/ --junit-xml=.out/junit-pytest.xml # --cov check_dependencies --cov-branch --cov-report=xml:.out/coverage.xml --cov-report term-missing

test-mypy: .ALWAYS  ## Run mypy
	poetry run mypy --non-interactive --install-types --show-error-codes --strict --junit-xml=.out/junit-mypy-strict.xml \
	--exclude=src/tests/data  src/

test-lint: .ALWAYS
	poetry run sh -c "ruff format --check src/ && ruff check src/"

test-static: test-lint test-mypy .ALWAYS  ## Run static tests

format: .ALWAYS
	poetry run sh -c "ruff format src/; ruff check --fix"
	poetry run black src
