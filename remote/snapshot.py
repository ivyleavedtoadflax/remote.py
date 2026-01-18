import typer
from rich.table import Table

from remote.utils import (
    console,
    get_ec2_client,
    get_instance_id,
    get_instance_name,
    get_volume_ids,
)

app = typer.Typer()


@app.command()
def create(
    volume_id: str = typer.Option(..., "--volume-id", "-v", help="Volume ID (required)"),
    name: str = typer.Option(..., "--name", "-n", help="Snapshot name (required)"),
    description: str = typer.Option("", "--description", "-d", help="Description"),
) -> None:
    """
    Create an EBS snapshot from a volume.

    Examples:
        remote snapshot create -v vol-123456 -n my-snapshot
        remote snapshot create -v vol-123456 -n backup -d "Daily backup"
    """

    snapshot = get_ec2_client().create_snapshot(
        VolumeId=volume_id,
        Description=description,
        TagSpecifications=[
            {
                "ResourceType": "snapshot",
                "Tags": [{"Key": "Name", "Value": name}],
            }
        ],
    )

    typer.secho(f"Snapshot {snapshot['SnapshotId']} created", fg=typer.colors.GREEN)


@app.command("ls")
@app.command("list")
def list_snapshots(instance_name: str | None = typer.Argument(None, help="Instance name")) -> None:
    """
    List EBS snapshots for an instance.

    Shows snapshots for all volumes attached to the instance.
    Uses the default instance from config if no name is provided.
    """

    if not instance_name:
        instance_name = get_instance_name()

    typer.secho(f"Listing snapshots for instance {instance_name}", fg=typer.colors.YELLOW)

    instance_id = get_instance_id(instance_name)
    volume_ids = get_volume_ids(instance_id)

    # Format table using rich
    table = Table(title="Snapshots")
    table.add_column("SnapshotId", style="green")
    table.add_column("VolumeId")
    table.add_column("State")
    table.add_column("StartTime")
    table.add_column("Description")

    for volume_id in volume_ids:
        snapshots = get_ec2_client().describe_snapshots(
            Filters=[{"Name": "volume-id", "Values": [volume_id]}]
        )

        for snapshot in snapshots["Snapshots"]:
            state = str(snapshot["State"])
            state_style = "green" if state == "completed" else "yellow"
            table.add_row(
                str(snapshot["SnapshotId"]),
                str(snapshot["VolumeId"]),
                f"[{state_style}]{state}[/{state_style}]",
                str(snapshot["StartTime"]),
                str(snapshot.get("Description", "")),
            )

    console.print(table)


if __name__ == "__main__":
    app()
