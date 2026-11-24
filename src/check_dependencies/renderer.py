"""Presentation layer for rendering output objects."""

from __future__ import annotations

from typing import TYPE_CHECKING

from check_dependencies.app_config import OutputFormat
from check_dependencies.outputs import SeenT

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from check_dependencies.outputs import Output


def make_renderer(
    *, output_format: OutputFormat, verbose: bool
) -> Callable[[Output], Iterator[str]]:
    """Create a renderer function for CLI outputs."""
    if output_format == OutputFormat.GITHUB:

        def render(output: Output) -> Iterator[str]:
            yield from output.as_github()

        return render

    seen: SeenT = set()

    def render(output: Output) -> Iterator[str]:
        yield from output.to_text(
            verbose=verbose,
            show_all=output_format == OutputFormat.FULL,
            seen=seen,
        )

    return render
