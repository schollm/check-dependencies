# Check Dependencies
Check all imports from python files and compares them against the declared imports of a pyproject dependency list of expected imports. 
It can be used as a stand-alone or as part of a CI/CD to check if an application has all the necessary, but no superfluous imports.

## Usage
```commandline
usage: check_imports [-h] [--config-file CONFIG_FILE] [--include-dev] [--verbose] [--all] [--extra EXTRA] [--ignore IGNORE] file_name [file_name ...]

Find undeclared and unused (or all) imports in Python files

positional arguments:
  file_name             Python Source file to analyse

optional arguments:
  -h, --help            show this help message and exit
  --config-file CONFIG_FILE
                        Location of pyproject.toml file, can be file or a directory containing pyproject.toml file
  --include-dev         Include dev dependencies
  --verbose             Show every import of a package
  --all                 Show all imports (including correct ones)
  --extra EXTRA         Comma seperated list of extra requirements. Assume they are part of the requirements
  --ignore IGNORE       Comma seperated list of requirements to ignore. Assume they are not part of the requirements
```

```commandline
> python -m  --config-file --all project/ project/src/**/*.py
  pandas
! matplotlib
  numpy
+ requests

> python -m check_dependencies --config-file --verbose project/ project/src/**/*.py
!NA matplotlib project/src/main.py:4
+EXTRA project/pyproject.toml requests 

> python -m check_dependencies --config-file --verbose --all project/ project/src/**/*.py
 OK project/src/data.py:5 pandas
 OK project/src/main.py:3 pandas
 OK project/src/plotting.py:4 pandas
!NA project/src/plotting.py:5 matplotlib
 OK project/src/plotting.py:6 numpy
 
 **** Dependencies in config file not used in application:
+EXTRA project/pyproject.toml requests 

```

### Configuration
The configuration is read from `pyproject.toml` file. The configuration file
supports two entries, `[tool.check_dependencies.extra-requirements]` that can be used to
add extra dependencies to the list of requirements to be treated as existing
requirements.
The second entry, `[tool.check_dependencies.ignore-requirements]` does the opposite, it will
ignore extra requirements that are not used in the application.

```toml
[tool.check_dependencies]
extra-requirements = [
  undeclared_package,
  another_package
]
ignore-requirements = [
  package_as_extra_for_another_package,
  yet_another_package
]
```

### Output
The output is a list of imports with a prefix indicating the status of the import.
- `!` - Undeclared import
- `+` - Extra import, declared in pyproject.toml, but not used in the file
- `  ` - Correct import (only shown with `--all`)

In case of `--verbose`, the output is a list of all imports in the file, prefixed with:
- `!NA` - Undeclared import
- `+EXTRA` - Extra import, declared in pyproject.toml, but not used in the file
- `  OK` - Correct import (only shown with `--all`)

In case of `--verbose`, each import is prefixed with the file name and line number
where it is declared. 

#### Exit code
- 0: No missing or superfluous dependencies found
- 2: Missing (used, but not declared in pyproject.toml) dependencies found
- 4: Extra (declared in pyproject.toml, but unused) dependencies found
- 6: Both missing and superfluous dependencies found
- 1: Another error occured


## Development
Feature requests and merge requests are welcome. For major changes, please open an 
issue first to discuss what you would like to change.

Please make sure to update tests as appropriate. Also with this project, I want
to keep the dependencies to a minimum, so please keep that in mind when proposing
a change. Currently, the only dependencies is `toml` to support Python 3.10 and below.

### Coding Standards

| **Type**      | Package  | Comment                         |
|---------------|----------|---------------------------------|
| **Linter**    | `black`  | Also for auto-formatted modules |
| **Logging**   | `logger` | Minimize additional packages    |
| **Packaging** | `poetry` |                                 |
| **Tests**     | `pytest` |                                 |
| **Typing**    | `mypy`   | Type all methods                |
| **Linting**   | `flake8` |                 |
| **Imports**   | `isort`  |                                 |
