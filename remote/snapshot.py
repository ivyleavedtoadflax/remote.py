import typer

from remote.instance_resolver import resolve_instance_or_exit
from remote.utils import (
    confirm_action,
    console,
    create_table,
    get_ec2_client,
    get_status_style,
    get_volume_ids,
    handle_aws_errors,
    handle_cli_errors,
    print_success,
    print_warning,
    styled_column,
)
from remote.validation import validate_aws_response_structure, validate_volume_id

app = typer.Typer()


@app.command()
@handle_cli_errors
def create(
    volume_id: str = typer.Option(..., "--volume-id", "-v", help="Volume ID (required)"),
    name: str = typer.Option(..., "--name", "-n", help="Snapshot name (required)"),
    description: str = typer.Option("", "--description", "-d", help="Description"),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt (for scripting)",
    ),
) -> None:
    """
    Create an EBS snapshot from a volume.

    Prompts for confirmation before creating.

    Examples:
        remote snapshot create -v vol-123456 -n my-snapshot
        remote snapshot create -v vol-123456 -n backup -d "Daily backup"
        remote snapshot create -v vol-123456 -n backup --yes  # Skip confirmation
    """
    validate_volume_id(volume_id)

    # Confirm snapshot creation
    if not yes:
        if not confirm_action("create", "snapshot", name, details=f"from volume {volume_id}"):
            print_warning("Snapshot creation cancelled")
            return

    with handle_aws_errors("EC2", "create_snapshot"):
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
        validate_aws_response_structure(snapshot, ["SnapshotId"], "create_snapshot")
    print_success(f"Snapshot {snapshot['SnapshotId']} created")


@app.command("ls")
@app.command("list")
@handle_cli_errors
def list_snapshots(instance_name: str | None = typer.Argument(None, help="Instance name")) -> None:
    """
    List EBS snapshots for an instance.

    Shows snapshots for all volumes attached to the instance.
    Uses the default instance from config if no name is provided.
    """
    instance_name, instance_id = resolve_instance_or_exit(instance_name)

    print_warning(f"Listing snapshots for instance {instance_name}")
    volume_ids = get_volume_ids(instance_id)

    columns = [
        styled_column("SnapshotId", "id"),
        styled_column("VolumeId", "id"),
        styled_column("State"),
        styled_column("StartTime"),
        styled_column("Description"),
    ]

    rows = []
    for volume_id in volume_ids:
        with handle_aws_errors("EC2", "describe_snapshots"):
            snapshots = get_ec2_client().describe_snapshots(
                Filters=[{"Name": "volume-id", "Values": [volume_id]}]
            )
            validate_aws_response_structure(snapshots, ["Snapshots"], "describe_snapshots")

        for snapshot in snapshots["Snapshots"]:
            state = snapshot["State"]
            state_style = get_status_style(state)
            rows.append(
                [
                    snapshot["SnapshotId"],
                    snapshot["VolumeId"],
                    f"[{state_style}]{state}[/{state_style}]",
                    str(snapshot["StartTime"]),
                    snapshot.get("Description", ""),
                ]
            )

    console.print(create_table("Snapshots", columns, rows))
