# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
## [0.12.2] - 2025-03-10 - Bugfix: github actions upload artifact
### Bugfix
- Use new version 3.0.0 for sigstore/gh-action-sigstore-python for github-release
## [0.12.1] - 2025-03-10 - Bugfix: github actions upload artifact
### Bugfix
- Use new version 4 for actions/download-artifact for github-release
## [0.12.0] - 2025-03-10 - Replace poetry with ruff
### Changed
package manager is now astrals [uv](https://docs.astral.sh/uv/).
## [0.11.1] - 2025-03-10 - Update gitlab action
### Changed
- Update gitlab action
- Update poetry.lock
## [0.11.0] - 2025-02-28 - Replace flake8, black and isort with ruff
### Changed
- Replace flake8, black and isort with ruff, adapt code accordingly
## [0.10.2] - 2024-06-26 Add CLI entry point check-depdencies
### Added
- Add CLI application check-dependencies
- Add homepage and other links, license, tags and classifieriers to pyproject.toml

## [0.10.1] - 2024-06-25 - Describe the project
### Added
- [Minor] tool.poetry.description

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
