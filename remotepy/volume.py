import typer
from rich.console import Console
from rich.table import Table

from remotepy.utils import (
    get_ec2_client,
    get_instance_id,
    get_instance_name,
    get_volume_name,
)

app = typer.Typer()
console = Console(force_terminal=True, width=200)


@app.command("ls")
@app.command("list")
def list_volumes(instance_name: str | None = typer.Argument(None, help="Instance name")) -> None:
    """
    List EBS volumes attached to an instance.

    Shows volume ID, size, state, and availability zone.
    Uses the default instance from config if no name is provided.
    """

    if not instance_name:
        instance_name = get_instance_name()
    typer.secho(f"Listing volumes attached to instance {instance_name}", fg=typer.colors.YELLOW)

    instance_id = get_instance_id(instance_name)
    volumes = get_ec2_client().describe_volumes()

    # Format table using rich
    table = Table(title="Volumes")
    table.add_column("Instance Name", style="cyan", no_wrap=True)
    table.add_column("Instance", no_wrap=True)
    table.add_column("Volume Name", no_wrap=True)
    table.add_column("VolumeId", style="green", no_wrap=True)
    table.add_column("Size", justify="right")
    table.add_column("State")
    table.add_column("AvailabilityZone")

    # Get the volumes attached to instance
    for volume in volumes["Volumes"]:
        for attachment in volume["Attachments"]:
            if attachment["InstanceId"] == instance_id:
                state = volume["State"]
                state_style = "green" if state == "in-use" else "yellow"
                table.add_row(
                    instance_name or "",
                    instance_id,
                    get_volume_name(volume["VolumeId"]),
                    volume["VolumeId"],
                    str(volume["Size"]),
                    f"[{state_style}]{state}[/{state_style}]",
                    volume["AvailabilityZone"],
                )

    console.print(table)


if __name__ == "__main__":
    app()
