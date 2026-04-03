"""Write/Update config file based on an existing environment."""

import sys

import check_dependencies.writer.cli as cli


def main() -> None:
    """Run the CLI for writer."""
    sys.exit(cli.main())


main()
