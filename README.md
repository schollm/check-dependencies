# 🔎 Check Dependencies

`check-dependencies` scans 🐍 Python imports and compares them with the dependencies
declared in `pyproject.toml`.

It can be used locally or in CI/CD pipelines to find dependencies that are
missing from the project configuration or declared but not actually used.

It supports PEP 621, Poetry (v1.2+), Hatch, and legacy `tool.uv`
dependency configuration.

This is a pure-Python package with no runtime dependencies on Python 3.11+
(`toml` is only required on older Python versions).

The project also ships a secondary CLI, `dependency-writer`, which writes
package-to-import mappings to a TOML config file. This is useful for creating
or updating `[tool.check-dependencies.provides]` entries.

## 📦 Installation

Install with `uv`:

```shell
uv tool install check-dependencies
check-dependencies
```

Install with `pipx`:

```shell
pipx install check-dependencies
check-dependencies
```

Run without installing:

```shell
uvx check-dependencies
pipx run check-dependencies
```

## GitHub Action

Use this repository as a reusable GitHub Action in third-party workflows.

The action inputs are derived from `AppConfig.from_cli_args(...)`.

### Usage

```yaml
name: Check dependencies

on:
  pull_request:
  push:

jobs:
  check-dependencies:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: schollm/check-dependencies@v1
        with:
          file-names: |
            src/
          include-dev: "false"
          verbose: "false"
          show-all: "false"
```

### Inputs

- `file-names` (required): newline-separated paths to files/directories
- `known-extra`: comma-separated package list
- `known-missing`: comma-separated module list
- `provides`: comma-separated `PACKAGE=MODULE` mappings
- `include-dev`: `true` or `false`
- `verbose`: `true` or `false`
- `show-all`: `true` or `false` (maps to CLI `--all`)
- `includes`: newline-separated list of additional config files
- `provides-from-venv`: path to venv Python executable


## 🧰 `check-dependencies`

Use `check-dependencies` to scan Python files and compare detected imports with
the dependencies declared in `pyproject.toml`.

### ▶️ Usage

```text
usage: check-dependencies [-h] [--version] [--include-dev] [--verbose] [--all]
                          [--provides-from-venv PYTHON_EXECUTABLE] [--missing MODULE,...]
                          [--extra PACKAGE,...] [--provides PACKAGE=MODULE,...]
                          [--include INCLUDE] file_name [file_name ...]

Find undeclared and unused (or all) imports in Python files

positional arguments:
  file_name             Python Source file to analyse

options:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
  --include-dev         Include dev dependencies
  --verbose             Show every import of a package
  --all                 Show all imports (including correct ones)
  --provides-from-venv PYTHON_EXECUTABLE
                        Path to the virtual environment's Python executable (for example, .venv/bin/python)
                        to include all packages installed in it as provides.
  --missing MODULE,...  Comma separated list of requirements known to be missing. Assume they are part of the
                        requirements. Can be specified multiple times. Toml Key: [tool.check-
                        dependencies] known-missing=[]
  --extra PACKAGE,...   Comma separated list of requirements known to not be imported. Assume they are not part
                        of the requirements. This can be plugins or similar that affect the package but are not
                        imported explicitly. Can be specified multiple times. Toml Key: [tool.check-
                        dependencies] known-extra=[]
  --provides PACKAGE=MODULE,...
                        Map a package name to its import name for packages whose import name differs from the
                        package name. Can be specified multiple times. E.g. --provides Pillow=PIL --provides
                        PyJWT=jwt. The package name is normalized (case-insensitive, hyphens and underscores
                        are equivalent), so Pillow=PIL, pillow=PIL and PIL-ow=PIL are all the same. Toml Key:
                        [tool.check-dependencies.provides]
  --include, -I INCLUDE
                        Additional config files to include. Can be specified multiple times. E.g. --include
                        check-dependencies.toml. Toml Key: [tool.check-dependencies] includes=[]
```

### 📄 Output

The output is a list of imports prefixed with their status.

Default status prefixes:

- `!` - Undeclared import
- `+` - Extra dependency, declared in `pyproject.toml` but not used in the code
- `?` - Dynamic import that could not be resolved.
- `!!` - Could not parse the file (e.g. syntax error)
- ` ` - Correct import (only shown with `--all`)

With `--verbose`, the output includes every matching import together with the
file name and line number where it appears.

Verbose status prefixes:

- `!NA` - Undeclared import
- `+EXTRA` - Extra dependency, declared in `pyproject.toml` but not used in the code
- `?UNKNOWN` - Dynamic import that could not be resolved.
- `!!FILE_ERROR` - Could not parse the file (e.g. syntax error)
- ` OK` - Correct import (only shown with `--all`)

### 📝 Examples

#### Basic usage

▶️ Command:

```shell
check-dependencies project/src/
```

Example output:

```text
  pandas
! matplotlib
  numpy
# Project project/pyproject.toml
+ requests
```

#### Add known extra requirements

Use this when dependencies affect the application but are not imported
directly in the codebase, such as plugins.

- ▶️ Command:
    ```shell
    check-dependencies --extra snowflake-sqlalchemy project/src
    ```
- 📄 `pyproject.toml`:
    ```toml
    [tool.check-dependencies]
    known-extra = [ "snowflake-sqlalchemy" ]
    ```

#### Translate package names

Some packages have different distribution and import names, for example
`Pillow` is imported as `PIL`.

- ▶️ Command:
    ```shell
    check-dependencies --provides Pillow=PIL --provides PyJWT=jwt project/src
    ```
- 📄 `pyproject.toml`:
    ```toml
    [tool.check-dependencies.provides]
    Pillow = "PIL"
    PyJWT = "jwt"
    ```

#### Add known missing requirements

Use this when imports are expected to be missing from the dependency list,
but should not be reported.

- ▶️ Command:
    ```shell
    check-dependencies --missing numpy project/src
    ```
- 📄 `pyproject.toml`:
    ```toml
    [tool.check-dependencies]
    known-missing = [ "numpy" ]
    ```


#### Include additional config file

Use an additional config file to provide extra dependencies, missing
dependencies, or `provides` mappings.

This is especially useful in monorepos where multiple packages share a common
configuration file.

- ▶️ Command:
    ```shell
    check-dependencies --include ../global-check-dependencies.toml project/src/
    ```
- 📄 `pyproject.toml`:
    ```toml
    [tool.check-dependencies]
    includes = [ "../global-check-dependencies.toml" ]
    ```

#### Include dev dependencies

- ▶️ Command:
    ```shell
    check-dependencies --include-dev project/tests/
    ```

#### Include provides from virtual environment

Read package-to-import mappings from a virtual environment and include them in
the check.

- ▶️ Command:
    ```shell
    check-dependencies --provides-from-venv .venv/bin/python project/src/
    ```

#### Output all dependencies

Show all detected dependencies, including the correct ones.

In the following example, `pandas` is declared and used, `requests` is declared
but unused, and `numpy` is used but not declared.

```shell
check-dependencies --all project/src/
```

Example output:

```text
  pandas
! numpy
+ requests
```

#### Verbose output

Show each import together with its status, file name, and line number.

```shell
check-dependencies --verbose project/src/
```

Example output:

```text
# ALL=False
# INCLUDE_DEV=False
# EXTRA pytest
# EXTRA toml
# EXTRA tomllib
# MISSING check_dependencies
# MISSING toml
# MISSING tomllib
!!FILE_ERROR project/src/broken.py
!NA matplotlib project/src/main.py:4

##### project/pyproject.toml ###
# Dependencies in config file not used in application:
+EXTRA requests
```

#### Combine verbose and all

Show all imports, including correct ones, with file names and line numbers.

```shell
check-dependencies --verbose --all project/src/
```

Example output:

```text
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

### ⚙️ Configuration

Configuration is read from `pyproject.toml`.

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

### 🚦 Exit codes

- `0`: No missing or superfluous dependencies found
- `2`: Missing dependencies found (used, but not declared in `pyproject.toml`)
- `4`: Extra dependencies found (declared in `pyproject.toml`, but unused)
- `6`: Both missing and superfluous dependencies found
- `8`: Could not find associated pyproject.toml file
- `16`: Could not parse source file(s)
- `1`: Another error occurred

## ✍️ `dependency-writer`

Use `dependency-writer` to generate or update
`[tool.check-dependencies.provides]` mappings from an existing Python
environment.

This is useful for generating the initial config file or refreshing it after
dependency changes.

Combined with the `includes` setting in `[tool.check-dependencies]`, it can
also be used to generate a shared `[tool.check-dependencies.provides]` mapping
for a monorepo.

If you install the package yourself and want to use `dependency-writer`, make
sure the optional `write` extra is installed because this command depends on
`tomlkit`.

### ▶️ Usage

```text
usage: dependency-writer [-h] --python PYTHON --config CONFIG

options:
  -h, --help           show this help message and exit
  --python, -p PYTHON  Python executable to check.
  --config, -c CONFIG  Location of toml config file.
```

### 📝 Examples

#### Write to pyproject.toml

The following command updates the
`[tool.check-dependencies.provides]` table of `pyproject.toml` with all
mappings found in the virtual environment.

- ▶️ Command:

```shell
dependency-writer -p .venv/bin/python -c pyproject.toml
```

#### Write a global provides file for a monorepo

- ▶️ Command:

```shell
dependency-writer -p apps/my-app/.venv/bin/python -c ./check-dependencies.toml
```

This requires an `includes = [...]` entry under `[tool.check-dependencies]` in
the application's `pyproject.toml` so that the generated config file is
included:

```toml
[tool.check-dependencies]
includes = [ "../../check-dependencies.toml" ]
```

## 🛠️ Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.