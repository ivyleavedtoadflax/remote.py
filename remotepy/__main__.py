import importlib.metadata

import typer

from remotepy.ami import app as ami_app
from remotepy.config import app as config_app
from remotepy.ecs import app as ecs_app
from remotepy.instance import app as instance_app
from remotepy.snapshot import app as snapshot_app
from remotepy.volume import app as volume_app

# The instance app is the default app, so instance commands are at root level
# This provides backwards compatibility with `remote start`, `remote stop`, etc.
app = instance_app


@app.command()
def version() -> None:
    """Show version."""
    typer.echo(importlib.metadata.version("remotepy"))


# Register service subcommands
app.add_typer(ami_app, name="ami", help="Manage Amazon Machine Images")
app.add_typer(config_app, name="config", help="Manage configuration")
app.add_typer(snapshot_app, name="snapshot", help="Manage EBS snapshots")
app.add_typer(volume_app, name="volume", help="Manage EBS volumes")
app.add_typer(ecs_app, name="ecs", help="Manage ECS clusters and services")

if __name__ == "__main__":
    app()
