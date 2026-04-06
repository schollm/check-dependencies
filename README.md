# Check Dependencies

Check all imports from python files and compares them against the declared imports of a pyproject dependency list of
expected imports.

It can be used as a stand-alone or as part of a CI/CD to check if an application has all the necessary, but no
superfluous imports.

It supports PEP-621, Poetry (v1.2+), UV (0.2+) and Hatch style dependencies.

This is a pure-Python zero-dependency (Up until Python 3.11 one, toml) package.

It also provides a secondary CLI application `dependency-writer` to write the mapping of imports to packages to the
config file. This can be used to generate the initial config file or to update it after changes in the codebase.


## check-dependencies

```text
usage: check-dependencies [-h] [--include-dev] [--verbose] [--all] [--missing MODULE] [--extra PACKAGE]
                          [--provides PACKAGE=IMPORT] [--include INCLUDE] [--provides-from-venv PYTHON_ENV]
                          file_name [file_name ...]

Find undeclared and unused (or all) imports in Python files

positional arguments:
  file_name             Python Source file to analyse

options:
  -h, --help            show this help message and exit
  --include-dev         Include dev dependencies
  --verbose             Show every import of a package
  --all                 Show all imports (including correct ones)
  --missing MODULE      Comma separated list of requirements known to be missing. Assume they are part of the
                        requirements. Can be specified multiple times.Toml Key: [tool.check-
                        dependencies] known_mising=[]
  --extra PACKAGE       Comma separated list of requirements known to not be imported. Assume they are not part
                        of the requirements. This can be plugins or similar that affect the package but are not
                        imported explicitly. Can be specified multiple times. Toml Key: [tool.check-
                        dependencies] known_extra=[]
  --provides PACKAGE=IMPORT
                        Map a package name to its import name for packages whose import name differs from the
                        package name. Can be specified multiple times. E.g. --provides Pillow=PIL --provides
                        PyJWT=jwt. The package name is normalized (case-insensitive, hyphens and underscores are
                        equivalent), so Pillow=PIL, pillow=PIL and PIL-ow=PIL are all the same.Toml Key:
                        [tool.check-dependencies.provides]
  --include, -I INCLUDE
                        Additional config files to include. Can be specified multiple times. E.g. --include
                        check-dependencies.toml.Toml Key: [tool.check-dependencies] includes=[]
  --provides-from-venv PYTHON_ENV
                        Path to a virtual environment python executable to include all packages installed in it
                        as provides.
```

### Output

The output is a list of imports with a prefix indicating the status of the import.

- `!` - Undeclared import
- `+` - Extra import, declared in pyproject.toml, but not used in the file
- `?` - Dynamic import that could not be resolved.
- `!!` - Could not parse the file (e.g. syntax error)
- ` ` - Correct import (only shown with `--all`)

**In case of `--verbose`**, the output is a list of all imports in the file, prefixed with:

- `!NA` - Undeclared import
- `+EXTRA` - Extra import, declared in pyproject.toml, but not used in the file
- `?UNKNOWN` - Dynamic import that could not be resolved.
- `!!FILE_ERROR` - Could not parse the file (e.g. syntax error)
- ` OK` - Correct import (only shown with `--all`)

Additionally, each import is prefixed with the file name and line number
where it is imported.

### Notes
This can be used as a stand-alone application or as part of a CI/CD pipeline.
In the former case, it can be installed via `uv tool` or `pipx`.

**Using `uv`:**
```commandline
uv tool install check-dependencies
check-dependencies
```

**Using `pipx`:**
```commandline
pipx install check-dependencies
check-dependencies
```

Alternatively, to run without installing:
```commandline
uvx check-dependencies
pipx run check-dependencies
```

### Examples

#### Basic usage

```text
check-dependencies  project/src/
  pandas
! matplotlib
  numpy
+ requests
```

#### Add known extra requirements
Add requirements that are known to be used, but not imported in the codebase (e.g. plugins).

Via CLI:
```text
check-dependencies --extra snowflake-sqlalchemy project/src
```

Via `pyproject.toml`:
```toml
[tool.check-dependencies]
known-extra = [ "snowflake-sqlalchemy" ]
```

#### Translate package names
Some packages have different names for the package and the import (e.g. Pillow is imported as PIL).

Via CLI:
```text
check-dependencies --provides Pillow=PIL --provides PyJWT=jwt project/src
```

Via `pyproject.toml`:
```toml
[tool.check-dependencies.provides]
Pillow = "PIL"
PyJWT = "jwt"
```

#### Add known missing requirements
Add requirements that are known to be missing, but are imported in the codebase.

Via CLI:
```text
check-dependencies --missing numpy check-dependencies project/src
```

Via `pyproject.toml`:
```toml
[tool.check-dependencies]
known-missing = [ "numpy" ]
```


#### Include additional config file
Use an additional config file to include extra or missing dependencies or provides.
This is useful for monorepos or similar setups where multiple packages share a common configuration file.

Via CLI:
```text
> check-dependencies project/src/
! snowflake-sqlalchemy
> check-dependencies --include ../global-check-dependencies.toml project/src/
```

Via `pyproject.toml`:
```toml
[tool.check-dependencies]
includes = [ "../global-check-dependencies.toml" ]
```

#### Include dev dependencies

```shell
check-dependencies --include-dev project/tests/
```

#### Include provides from virtual environment

Get all provides from the virtual environment and include them in the check.
```text
check-dependencies --provides-from-venv .venv/bin/python project/src/
```

#### Output all dependencies

Output all dependencies, including the correct ones.

```text
check-dependencies --all project/src/
  pandas
! matplotlib
  numpy
+ requests
```

#### Verbose output

Output each erroneous import and extra dependency with cause, file name and line number.

```text
check-dependencies --verbose project/src/
# ALL=False
# INCLUDE_DEV=False
# EXTRA pytest
# EXTRA toml
# EXTRA tomllib
# MISSING check_dependencies
# MISSING toml
# MISSING tomllib
!NA matplotlib project/src/main.py:4
+EXTRA project/pyproject.toml requests
```

#### Combine verbose and all

Output all imports, including the correct ones with file name and line number.

```text
check-dependencies --verbose --all project/src/
# ALL=True
# INCLUDE_DEV=False
# EXTRA pytest
# EXTRA toml
# EXTRA tomllib
# MISSING check_dependencies
# MISSING toml
# MISSING tomllib
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

The configuration is read from `pyproject.toml` file.

```toml
[tool.check-dependencies]
known-missing = [
    "undeclared_package",
    "another_package"
]
known-extra = [
    "package_as_extra_for_another_package",
    "yet_another_package"
]
[tool.check-dependencies.provides]
# Maps package name (as declared in dependencies) -> import/module name
Pillow = "PIL"
PyJWT = "jwt"
pyshp = "shapefile"
foxtrox = ["fox", "trox"]  # This package provides both `import fox` and `import trox`, but the package name is `foxtrox`
[tool.check-dependencies]
includes = [
  "check-dependencies.toml",
  "../../common-provides.toml"
]
```

#### Exit code

- `0`: No missing or superfluous dependencies found
- `2`: Missing (used, but not declared in pyproject.toml) dependencies found
- `4`: Extra (declared in pyproject.toml, but unused) dependencies found
- `6`: Both missing and superfluous dependencies found
- `8`: Could not find associated pyproject.toml file
- `16`: Could not parse source file(s)
- `1`: Another error occurred

## Dependency Writer

The `dependency-writer` CLI application can be used to write the mapping of imports to packages to the config file.
It can be used to generate the initial config file or to update it after changes in the codebase.

In combination with `[tool.check-dependencies.includes]` it can be also used to generate a global
`[tool.check-dependencies.provides]` mapping for a monorepo. 

```text
usage: dependency-writer [-h] --python PYTHON --config CONFIG                                                                                                                                                                                                                                                                                                                                                                                                           
options:                                                                                                                                                                                                                            
  -h, --help           show this help message and exit
  --python, -p PYTHON  Python executable to check.
  --config, -c CONFIG  Location of toml config file.
```

### Examples
#### Write to pyproject.toml
The following command will update the `[tool.check-dependencies.provides]` section of the `pyproject.toml` file
with all the mappings of packages to imports found in the virtual environment.

```commandline
dependency-writer -p .venv/bin/python -c pyproject.toml
```

#### Write a global provides file for a monorepo
```commandline
dependency-writer -p apps/my-app/.venv/bin/python -c ./check-dependencies.toml 
```

This requires an entry `[tool.check-dependencies.includes]` in the `pyproject.toml` file of the application to 
include the generated config file:

```toml
[tool.check-dependencies]
includes = [ "../../check-dependencies.toml" ]
```

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.