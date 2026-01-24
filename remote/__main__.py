import importlib.metadata
import sys

import typer

from remote.ami import app as ami_app
from remote.config import app as config_app
from remote.ecs import app as ecs_app
from remote.instance import app as instance_app
from remote.logo import print_logo
from remote.sg import app as sg_app
from remote.snapshot import app as snapshot_app
from remote.utils import handle_cli_errors
from remote.volume import app as volume_app

# Create main app
app = typer.Typer(
    name="remote",
    help="AWS EC2 instance management CLI",
    epilog="Run 'remote COMMAND --help' for more information on a command.",
    no_args_is_help=True,
)


def _should_show_logo() -> bool:
    """Determine if the logo should be displayed.

    Returns True when showing root-level help (--help with no subcommand,
    or no arguments at all).
    """
    args = sys.argv[1:]  # Exclude the program name

    # No args means we'll show help (due to no_args_is_help=True)
    if not args:
        return True

    # Only --help at root level
    if args == ["--help"] or args == ["-h"]:
        return True

    return False


@app.command()
@handle_cli_errors
def version() -> None:
    """Show version."""
    typer.echo(importlib.metadata.version("remotepy"))


# Register service subcommands
app.add_typer(instance_app, name="instance", help="Manage EC2 instances")
app.add_typer(ami_app, name="ami", help="Manage Amazon Machine Images")
app.add_typer(config_app, name="config", help="Manage configuration")
app.add_typer(snapshot_app, name="snapshot", help="Manage EBS snapshots")
app.add_typer(volume_app, name="volume", help="Manage EBS volumes")
app.add_typer(ecs_app, name="ecs", help="Manage ECS clusters and services")
app.add_typer(sg_app, name="sg", help="Manage security group IP rules")


def main() -> None:
    """Entry point that displays logo before help."""
    if _should_show_logo():
        print_logo()
    app()


if __name__ == "__main__":
    main()
