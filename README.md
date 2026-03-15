# Check Dependencies

Check all imports from python files and compares them against the declared imports of a pyproject dependency list of
expected imports.

It can be used as a stand-alone or as part of a CI/CD to check if an application has all the necessary, but no
superfluous imports.

It supports PEP-621, Poetry (v1.2+), UV (0.2+) and Hatch style dependencies.

This is a pure-Python zero-dependency (Up until Python 3.11 one, toml) package.

## Usage

```text
usage: check-dependencies [-h] [--include-dev] [--verbose] [--all] [--missing MISSING] [--extra EXTRA] [--provides PROVIDES] file_name [file_name ...]

Find undeclared and unused (or all) imports in Python files

positional arguments:
  file_name          Python Source file to analyse

options:
  -h, --help         show this help message and exit
  --include-dev      Include dev dependencies
  --verbose          Show every import of a package
  --all              Show all imports (including correct ones)
  --missing MISSING  Comma separated list of requirements known to be missing.
                     Assume they are part of the requirements.
  --extra EXTRA      Comma separated list of requirements known to not be imported.
                     Assume they are not part of the requirements.
  --provides PACKAGE=IMPORT
                     Map a package name to its import name for packages whose
                     import name differs from the package name. Can be specified
                     multiple times. E.g. --provides Pillow=PIL --provides PyJWT=jwt.
                     Package name is normalized (case-insensitive, hyphens and
                     underscores equivalent), so Pillow=PIL and pillow=PIL are the same.
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

### Examples

#### Basic usage

```text
check-dependencies  project/src/
  pandas
! matplotlib
  numpy
+ requests
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
!NA matplotlib project/src/main.py:4
+EXTRA project/pyproject.toml requests
```

#### Combine verbose and all

Output all imports, including the correct ones with file name and line number.

```commandline
check-dependencies --verbose --all project/src/
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
supports the following entries:

- `[tool.check-dependencies.known-extra]` to
  add extra packages to the list of dependencies.

- `[tool.check-dependencies.known-missing]` does the opposite, it will
  ignore existing dependencies even if they are not imported. This is useful for
  packages, that provide functionality via plugins (e.g. sqlalchemy plugins)
  and are not imported directly in the codebase.
- `[tool.check-dependencies.provides]` to map package names to import names for
  packages whose import name differs from the package name.
  E.g. Pillow is imported as PIL, but the package name is Pillow.
  The value can be either a single module or a list of modules.

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
```

#### Exit code

- 0: No missing or superfluous dependencies found
- 2: Missing (used, but not declared in pyproject.toml) dependencies found
- 4: Extra (declared in pyproject.toml, but unused) dependencies found
- 6: Both missing and superfluous dependencies found
- 8: Could not find associated pyproject.toml file
- 16: Could not parse source file(s)
- 1: Another error occurred

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.