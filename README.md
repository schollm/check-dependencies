# Check Dependencies
Check all imports from python files and compares them against the declared imports of a pyproject dependency list of expected imports. 
It can be used as a stand-alone or as part of a CI/CD to check if an application has all the necessary, but no superfluous imports.

## Usage
```commandline
usage: check_dependencies [-h] [--include-extra] [--verbose] [--all] [--missing MISSING] [--extra EXTRA] file_name [file_name ...]

Find undeclared and unused (or all) imports in Python files

positional arguments:
  file_name          Python Source file to analyse

optional arguments:
  -h, --help         show this help message and exit
  --include-extra    Include dev dependencies
  --verbose          Show every import of a package
  --all              Show all imports (including correct ones)
  --missing MISSING  Comma seperated list of requirements known to be missing. Assume they are part of the requirements
  --extra EXTRA      Comma seperated list of requirements known to not be imported. Assume they are not part of the requirements```
```

### Output
The output is a list of imports with a prefix indicating the status of the import.
- `!` - Undeclared import
- `+` - Extra import, declared in pyproject.toml, but not used in the file
- ` ` - Correct import (only shown with `--all`)

**In case of `--verbose`**, the output is a list of all imports in the file, prefixed with:
- `!NA` - Undeclared import
- `+EXTRA` - Extra import, declared in pyproject.toml, but not used in the file
- ` OK` - Correct import (only shown with `--all`)

Additionally, each import is prefixed with the file name and line number
where it is imported.


### Examples
#### Basic usage
```commandline
> python -m check_dependencies  project/src/
  pandas
! matplotlib
  numpy
+ requests
```

#### Output all dependencies
Output all dependencies, including the correct ones.
```commandline
> python -m check_dependencies --all project/src/
  pandas
! matplotlib
  numpy
+ requests
```
#### Verbose output
Output each erroneous import and extra dependency with cause, file name and line number.
```commandline
> python -m check_dependencies --verbose project/src/
!NA matplotlib project/src/main.py:4
+EXTRA project/pyproject.toml requests
```

#### Combine verbose and all
Output all imports, including the correct ones with file name and line number.
```commandline
> python -m check_dependencies --verbose --all project/src/
 OK project/src/data.py:5 pandas
 OK project/src/main.py:3 pandas
 OK project/src/plotting.py:4 pandas
!NA project/src/plotting.py:5 matplotlib
 OK project/src/plotting.py:6 numpy

### Dependencies in config file not used in application:
# Config file: project/pyproject.toml
+EXTRA requests
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
known-missing = [
  undeclared_package,
  another_package
]
known-extra = [
  package_as_extra_for_another_package,
  yet_another_package
]
```

#### Exit code
- 0: No missing or superfluous dependencies found
- 2: Missing (used, but not declared in pyproject.toml) dependencies found
- 4: Extra (declared in pyproject.toml, but unused) dependencies found
- 6: Both missing and superfluous dependencies found
- 8: Could not find associated pyproject.toml file
- 1: Another error occurred

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
