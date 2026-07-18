"""Output for check_dependencies."""

from __future__ import annotations

import abc
import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from check_dependencies.lib import Module, Package

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable, Iterator

    from check_dependencies.app_config import ProjectConfig


SeenT = set[tuple[type, Module | Package | Path]]


@dataclass(frozen=True)
class OutputConfig:
    """Defines a configuration object for check_dependencies."""

    name: str
    short_name: str
    exit_code: int


@dataclass(frozen=True)
class Output(abc.ABC):
    """Output for check_dependencies."""

    @abc.abstractmethod
    def as_github(self) -> Iterator[str]:
        """Return a GitHub issue body for this output."""

    @property
    @abc.abstractmethod
    def config(self) -> OutputConfig:
        """Get the name of the Output."""

    def name(self, verbose: bool) -> str:  # noqa:FBT001
        """Get the name of the Output."""
        cfg = self.config
        return cfg.name if verbose else cfg.short_name

    @property
    def exit_code(self) -> int:
        """Get the exit code of the Output."""
        return self.config.exit_code

    @abc.abstractmethod
    def to_text(self, *, verbose: bool, show_all: bool, seen: SeenT) -> Iterable[str]:
        """Get the string representation of the Output."""


def _github_issue(
    output: Output, path: Path, stmt: ast.stmt, msg: str, level: str = "error"
) -> str:
    check_name = output.name(verbose=True)

    full_msg = f"{path.as_posix()}: {check_name}: {msg}"
    col_offset = stmt.col_offset + 1
    end_col_offset = (stmt.end_col_offset or 0) + 1
    return (
        f"::{level} name=check-dependencies ({check_name}),"
        f"file={path.resolve().as_posix()},"
        f"line={stmt.lineno},col={col_offset},"
        f"endLine={stmt.end_lineno or stmt.lineno},endColumn={end_col_offset}"
        f"::{full_msg}"
    )


@dataclass(frozen=True)
class WithModule(Output, abc.ABC):
    """Defines a module that can be imported."""

    path: Path
    stmt: ast.AST
    module: Module
    show_default: bool = field(init=False, default=True)
    level: str = field(init=False, default="error")

    def as_github(self) -> Iterator[str]:
        """Return a GitHub issue body for this output."""
        if self.show_default and isinstance(self.stmt, ast.stmt):
            yield _github_issue(
                self,
                self.path,
                self.stmt,
                msg=f"module {self.module.name}",
                level=self.level,
            )

    def lineno(self, default: int = -1) -> int:
        """Get the line number of the statement."""
        return getattr(self.stmt, "lineno", default)

    def to_text(self, *, verbose: bool, show_all: bool, seen: SeenT) -> Iterable[str]:
        """Get the string representation of the WithModule."""
        if not (self.show_default or show_all):
            return
        name = self.name(verbose)
        if verbose:
            yield f"{name} {self.path.as_posix()}:{self.lineno()} {self.module.name}"
        elif (key := (type(self), self.module)) not in seen:
            seen.add(key)
            yield f"{name} {self.module.name}"


@dataclass(frozen=True)
class OkDependency(WithModule):
    """Defines a module that is correctly imported and declared in the config file."""

    config: OutputConfig = field(init=False, default=OutputConfig(" OK", " ", 0))
    show_default: bool = field(init=False, default=False)


@dataclass(frozen=True)
class MissingModule(WithModule):
    """Defines an unknown module - imported, but not defined as a dependency."""

    config: OutputConfig = field(init=False, default=OutputConfig("!NA", "!", 2))


@dataclass(frozen=True)
class UnknownModule(WithModule):
    """Defines an unknown module - imported, but package cannot be determined.

    This happens when using importlib with references or calculations within.
    """

    level: str = field(init=False, default="warning")
    config: OutputConfig = field(init=False, default=OutputConfig("?UNKNOWN", "?", 0))


@dataclass(frozen=True)
class ExtraPackage(Output):
    """Defines an extra package - a package that is not imported."""

    project_cfg: ProjectConfig
    package: Package
    config: OutputConfig = field(init=False, default=OutputConfig("+EXTRA", "+", 4))

    def as_github(self) -> Iterator[str]:
        """Return a GitHub issue body for this output."""
        yield _github_issue(
            self,
            self.project_cfg.path,
            stmt=ast.Pass(lineno=1, col_offset=0, end_lineno=1, end_col_offset=1),
            msg=f"Package {self.package!s} is not imported in the project"
            " but is defined as a dependency.",
        )

    def to_text(self, *, verbose: bool, show_all: bool, seen: SeenT) -> Iterable[str]:
        """Get the string representation of the ExtraPackage."""
        name = self.name(verbose)
        if verbose or show_all:
            yield f"{name} {self.package}"
        elif (key := (type(self), self.package)) not in seen:
            seen.add(key)
            yield f"{name} {self.package}"


@dataclass(frozen=True)
class NoPyprojectError(Output):
    """Defines an error when no pyproject.toml file is found."""

    msg: str
    config: OutputConfig = field(
        init=False, default=OutputConfig("!!NOPYPROJECT", "!!", 8)
    )

    def as_github(self) -> Iterator[str]:
        """NoPyProject does not have a corresponding error in a file."""
        yield f"::error::{self.name(verbose=True)} {self.msg}"

    def to_text(self, *, verbose: bool, show_all: bool, seen: SeenT) -> Iterable[str]:
        """Get the string CLI representation of the NoPyprojectError."""
        del show_all, seen
        name = self.name(verbose)
        yield f"{name} {self.msg}"


@dataclass(frozen=True)
class FileError(Output):
    """Error for missing/non-parsable files."""

    path: Path
    message: str
    config: OutputConfig = field(init=False, default=OutputConfig("!!FILE", "!!", 16))

    def as_github(self) -> Iterator[str]:
        """Return a GitHub issue body for this output."""
        yield _github_issue(
            self,
            self.path,
            stmt=ast.Pass(lineno=1, col_offset=0, end_lineno=1, end_col_offset=1),
            msg=f"File {self.path.as_posix()} could not be parsed: {self.message}",
        )

    def __str__(self) -> str:
        """Get the string representation of the FileError."""
        return f"{self.path}: {self.message}"

    def to_text(self, *, verbose: bool, show_all: bool, seen: SeenT) -> Iterable[str]:
        """Get the string representation of the FileError."""
        del show_all
        name = self.name(verbose)
        if (key := (type(self), self.path)) not in seen:
            seen.add(key)
            yield f"{name} {self.path.as_posix()}"


@dataclass(frozen=True)
class InfoMessage(Output):
    """Info message."""

    message: str
    verbose: bool
    config: OutputConfig = field(init=False, default=OutputConfig("#", "#", 0))

    def as_github(self) -> Iterator[str]:
        """GitHub Issue for info is empty."""
        yield from ()

    def to_text(self, *, verbose: bool, show_all: bool, seen: SeenT) -> Iterable[str]:
        """Get the string representation of the InfoMessage."""
        del seen, show_all
        if verbose or self.verbose:
            yield f"{self.name(verbose)} {self.message}"

    @classmethod
    def from_iter(
        cls, messages: Iterable[str], *, verbose: bool
    ) -> Generator[InfoMessage, None, None]:
        """Create InfoMessage instances from an iterable of messages."""
        for message in messages:
            yield cls(message=message, verbose=verbose)
