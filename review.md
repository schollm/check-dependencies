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

## TODO 4: Reduce coupling between analysis and presentation layers
Severity: Low

Description:
Dependency analysis and output formatting are currently coupled through formatter callbacks carried in config objects.

Evidence:
- [src/check_dependencies/main.py](src/check_dependencies/main.py#L67)
- [src/check_dependencies/app_config.py](src/check_dependencies/app_config.py#L91)
- [src/check_dependencies/app_config.py](src/check_dependencies/app_config.py#L161)

Why this matters:
This makes it harder to add output modes such as JSON, API responses, or reusable programmatic interfaces without threading formatter concerns through domain code.

Action items:
- Introduce a structured analysis result model separate from rendering.
- Keep CLI formatting in adapter/presentation layer only.
- Add tests for both raw analysis results and rendered output.

Acceptance criteria:
- Core analyzer can be consumed without string formatting dependencies.
- Existing CLI output remains backward compatible.

## TODO 5: Expand tests for semantic correctness of builtin set
Severity: Low

Description:
Builtin module tests verify shape and identifier format, but not semantic correctness of the fallback list contents.

Evidence:
- [tests/test_builtin_modules.py](tests/test_builtin_modules.py#L23)
- [tests/test_builtin_modules.py](tests/test_builtin_modules.py#L26)

Why this matters:
High coverage can still miss regression classes where invalid modules are accidentally considered stdlib.

Action items:
- Add explicit negative tests for known third-party modules.
- Add a small positive canonical sample for true stdlib modules.
- Keep tests stable across supported Python versions by guarding version-specific expectations.

Acceptance criteria:
- Test suite fails if non-stdlib modules are introduced into BUILTINS fallback.
- Tests remain deterministic across Python 3.9 to 3.14.
