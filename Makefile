.PHONY: .ALWAYS
.ALWAYS:

test: .ALWAYS test-src  ## Run all tests

test-src: .ALWAYS test-format test-pytest test-static  ## Run almost all tests (use test-all to include cli tests)
test-format: test-isort test-black test-flake8

test-pytest: .ALWAYS  ## Run pytest
	poetry run pytest src/tests/ --cov check_dependencies --cov-branch --cov-report=xml:.out/coverage.xml --cov-report term-missing \
          --junit-xml=.out/junit-pytest.xml

test-mypy: .ALWAYS  ## Run mypy
	poetry run mypy --non-interactive --install-types --show-error-codes --strict --junit-xml=.out/junit-mypy-strict.xml \
	--exclude=src/tests/data  src/

test-isort: .ALWAYS
	poetry run isort --check src

test-black: .ALWAYS
	poetry run black --check src

test-flake8: .ALWAYS
	poetry run flake8 src/ --exclude=src/tests/data

test-static: test-black test-isort test-flake8 test-flake8 test-mypy .ALWAYS  ## Run static tests

format: .ALWAYS
	poetry run isort src
	poetry run black src
