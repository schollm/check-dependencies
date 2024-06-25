# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
## [0.10.0] - 2024-06-25 - PEP-631 support
### Added
- Support PEP-631 style dependencies

### Changes
- Remove `--config-file` option: Always use the `pyprojec.toml` file associated with the source
- Renames in `pyproject.toml` section `tool.check_dependencies`:
  - `ignore-requirements` to `known-missing` 
  - `extra-requirements` to `known-extra` 
- Rename CLI options:
  - `--extra` to `--missing`
  - `--ignore` to `--extra`


## [0.9.1] - 2024-06-24 - Continuous Integration
### Added
- Github actions for automated testing and publishing

## [0.9.0] - 2024-06-22 - Hello World!
Initial version of the package
