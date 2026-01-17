import importlib.metadata

import typer

from remote.ami import app as ami_app
from remote.config import app as config_app
from remote.ecs import app as ecs_app
from remote.instance import app as instance_app
from remote.snapshot import app as snapshot_app
from remote.volume import app as volume_app

# Create main app
app = typer.Typer(
    name="remote",
    help="Remote.py - AWS EC2 instance management CLI",
    epilog="Run 'remote COMMAND --help' for more information on a command.",
    no_args_is_help=True,
)


@app.command()
def version() -> None:
    """Show version."""
    typer.echo(importlib.metadata.version("remotepy"))


# Copy instance commands to root level for backwards compatibility
# This allows `remote start`, `remote stop`, etc. to work
for command in instance_app.registered_commands:
    if command.callback is not None:
        app.command(command.name, help=command.callback.__doc__)(command.callback)

# Register service subcommands
app.add_typer(instance_app, name="instance", help="Manage EC2 instances")
app.add_typer(ami_app, name="ami", help="Manage Amazon Machine Images")
app.add_typer(config_app, name="config", help="Manage configuration")
app.add_typer(snapshot_app, name="snapshot", help="Manage EBS snapshots")
app.add_typer(volume_app, name="volume", help="Manage EBS volumes")
app.add_typer(ecs_app, name="ecs", help="Manage ECS clusters and services")

if __name__ == "__main__":
    app()
