import typer
import wasabi

from remotepy.config import cfg
from remotepy.utils import (
    ec2_client,
    get_instance_id,
    get_instance_name,
    get_volume_ids,
)

app = typer.Typer()


@app.command()
def create(
    volume_id: str = typer.Option(None, help="Volume ID"),
    name: str = typer.Option(None, help="Snapshot name"),
    description: str = typer.Option(None, help="Description"),
):
    """
    Snapshot a volume
    """

    snapshot = ec2_client.create_snapshot(
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
def list(instance_name: str = typer.Argument(None, help="Instance name")):
    """
    List the snapshots
    """

    if not instance_name:
        instance_name = get_instance_name(cfg)

    typer.secho(
        f"Listing snapshots for instance {instance_name}", fg=typer.colors.YELLOW
    )

    instance_id = get_instance_id(instance_name)
    volume_ids = get_volume_ids(instance_id)

    header = ["SnapshotId", "VolumeId", "State", "StartTime", "Description"]
    aligns = ["l", "l", "l", "l", "l"]
    data = []

    for volume_id in volume_ids:

        snapshots = ec2_client.describe_snapshots(
            Filters=[{"Name": "volume-id", "Values": [volume_id]}]
        )

        for snapshot in snapshots["Snapshots"]:
            data.append(
                [
                    snapshot["SnapshotId"],
                    snapshot["VolumeId"],
                    snapshot["State"],
                    snapshot["StartTime"],
                    snapshot["Description"],
                ]
            )

    # Format table using wasabi

    formatted = wasabi.table(data, header=header, divider=True, aligns=aligns)
    typer.secho(formatted, fg=typer.colors.YELLOW)


if __name__ == "__main__":
    app()
