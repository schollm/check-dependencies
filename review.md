# Architecture and Code Quality Review

Scope: full review of the repository for clean architecture, clean code principles, and Python 3.9+ best practices.

## TODO 1: Correct Python 3.9 builtin fallback to avoid false negatives: DONE
## TODO 2: Harden venv mapping collection error handling
Severity: Medium

Description:
Infrastructure-edge failures in provides-from-venv mapping can currently bubble up and fail the CLI unexpectedly.

Evidence:
- [src/check_dependencies/provides.py](src/check_dependencies/provides.py#L83)
- [src/check_dependencies/provides.py](src/check_dependencies/provides.py#L58)
- [src/check_dependencies/app_config.py](src/check_dependencies/app_config.py#L198)
- [src/check_dependencies/__main__.py](src/check_dependencies/__main__.py#L31)

Why this matters:
Invalid interpreter path, subprocess failures, or unreadable RECORD files can abort checks in CI or inconsistent environments.

Action items:
- Add explicit handling for subprocess and file read failures in mapping collection.
- Degrade gracefully by skipping unreadable entries and emitting a warning.
- Ensure CLI exits with a clear message when the interpreter itself is invalid.

Acceptance criteria:
- Corrupt or inaccessible dist-info records do not crash the run.
- Invalid Python executable path yields deterministic and user-friendly error output.

## TODO 4: Reduce coupling between analysis and presentation layers: DONE
## TODO 5: Expand tests for semantic correctness of builtin set: DONE