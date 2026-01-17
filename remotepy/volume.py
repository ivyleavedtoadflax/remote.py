import typer
import wasabi

from remotepy.utils import (
    ec2_client,
    get_instance_id,
    get_instance_name,
    get_volume_name,
)

app = typer.Typer()


@app.command("ls")
@app.command("list")
def list(instance_name: str = typer.Argument(None, help="Instance name")):
    """
    List the volumes and the instances they are attached to
    """

    if not instance_name:
        instance_name = get_instance_name()
    typer.secho(f"Listing volumes attached to instance {instance_name}", fg=typer.colors.YELLOW)

    instance_id = get_instance_id(instance_name)
    volumes = ec2_client.describe_volumes()

    # Format table using wasabi

    header = [
        "Instance Name",
        "Instance",
        "Volume Name",
        "VolumeId",
        "Size",
        "State",
        "AvailabilityZone",
    ]
    aligns = ["l", "l", "l", "l", "l", "l", "l"]
    data = []

    # Get the volumes attached to instance

    for volume in volumes["Volumes"]:
        for attachment in volume["Attachments"]:
            if attachment["InstanceId"] == instance_id:
                data.append(
                    [
                        instance_name,
                        instance_id,
                        get_volume_name(volume["VolumeId"]),
                        volume["VolumeId"],
                        volume["Size"],
                        volume["State"],
                        volume["AvailabilityZone"],
                    ]
                )

    formatted = wasabi.table(data, header=header, divider=True, aligns=aligns)
    typer.secho(formatted, fg=typer.colors.YELLOW)


if __name__ == "__main__":
    app()
