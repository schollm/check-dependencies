"""Output for check_dependencies."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import TYPE_CHECKING

from check_dependencies.lib import Module, Package

if TYPE_CHECKING:
    import ast
    from collections.abc import Generator, Iterable

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


@dataclass(frozen=True)
class WithModule(Output, abc.ABC):
    """Defines a module that can be imported."""

    path: Path
    stmt: ast.AST
    module: Module
    show_default: bool = field(init=False, default=True)

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

    config: OutputConfig = field(init=False, default=OutputConfig("?UNKNOWN", "?", 0))


@dataclass(frozen=True)
class ExtraPackage(Output):
    """Defines an extra package - a package that is not imported."""

    project_cfg: ProjectConfig
    package: Package
    config: OutputConfig = field(init=False, default=OutputConfig("+EXTRA", "+", 4))

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
