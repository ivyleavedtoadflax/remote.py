import builtins
from collections.abc import Sequence
from typing import Literal, cast

import typer
import wasabi

from remotepy.utils import (
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
    Snapshot a volume
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
    List the snapshots
    """

    if not instance_name:
        instance_name = get_instance_name()

    typer.secho(f"Listing snapshots for instance {instance_name}", fg=typer.colors.YELLOW)

    instance_id = get_instance_id(instance_name)
    volume_ids = get_volume_ids(instance_id)

    header = ["SnapshotId", "VolumeId", "State", "StartTime", "Description"]
    aligns = cast(Sequence[Literal["l", "r", "c"]], ["l", "l", "l", "l", "l"])
    data: builtins.list[builtins.list[str]] = []

    for volume_id in volume_ids:
        snapshots = get_ec2_client().describe_snapshots(
            Filters=[{"Name": "volume-id", "Values": [volume_id]}]
        )

        for snapshot in snapshots["Snapshots"]:
            data.append(
                [
                    str(snapshot["SnapshotId"]),
                    str(snapshot["VolumeId"]),
                    str(snapshot["State"]),
                    str(snapshot["StartTime"]),
                    str(snapshot.get("Description", "")),
                ]
            )

    # Format table using wasabi

    formatted = wasabi.table(data, header=header, divider=True, aligns=aligns)
    typer.secho(formatted, fg=typer.colors.YELLOW)


if __name__ == "__main__":
    app()
