# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
## Checklist for release
- [ ] Create a new branch release/v<x.y.z> from main
- [ ] Update the changelog with the new version and changes
- [ ] Update the version in pyproject.toml
- [ ] Run uv lock to update the lock file
- [ ] Update the README.md if necessary
- [ ] Merge the release branch into main
- [ ] Create a new release on GitHub with the new version and changelog
## Planned

## Upcoming
### Added
- New Script dependency-writer to write dependency mappings to config file.

## [1.1.0] - 2026-04-03 - Support for including additional config files
### Added
- Add support --include/-I/[tool.check_dependencies.include] to include config.
- Limited support of __import__ style dynamic imports

## [1.0.0] - 2026-03-14 - Initial stable release
### Added
- Add support for Hatch and uv-legacy style dependencies.
- Add support for Python 3.13 -- 3.15
- New status (!!) for source files that could not be parsed
- Add CONTRIBUTING.md with contribution guidelines and coding standards
- Fix README.md with correct usage of the CLI application
### Bugfix
- Fix PEP621 parsing of development dependencies
- Handle Python source files that declare a non-UTF8 encoding (PEP 263 encoding cookie or BOM)
## [0.13.0] - 2026-03-06 - Support for package - module mapping in pyproject.toml
### Added
- Support for package - module mapping in pyproject.toml, to allow for different package and module names.
## [0.12.6] -  2025-04-11 - Fix typos and pipelines
### Changed
- Fix typos in changelog and pipelines
## [0.12.5] - 2025-04-11 - Fix typos
### Changed
- Fix typos in changelog
## [0.12.4] - 2025-04-11 - Bugfix: github actions upload artifact overwrite
### Bugfix
- Use --clobber when uploading signed artifact
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
