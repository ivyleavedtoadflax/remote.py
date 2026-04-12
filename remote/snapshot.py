import typer

from remote.exceptions import AWSServiceError
from remote.instance_resolver import resolve_instance_or_exit
from remote.utils import (
    confirm_action,
    console,
    create_table,
    get_ec2_client,
    get_status_style,
    get_volume_ids,
    get_volumes_for_instance,
    handle_aws_errors,
    handle_cli_errors,
    print_error,
    print_success,
    print_warning,
    styled_column,
)
from remote.validation import validate_aws_response_structure, validate_volume_id

app = typer.Typer()


def _get_device_name(volume: dict, instance_id: str) -> str:
    """Extract the device name for a volume's attachment to a specific instance.

    Args:
        volume: Volume dictionary from describe_volumes
        instance_id: The instance ID to match against

    Returns:
        The device name (e.g., "/dev/sdf") or empty string if not found
    """
    for attachment in volume.get("Attachments", []):
        if attachment.get("InstanceId") == instance_id:
            return attachment.get("Device", "")
    return ""


def _make_snapshot_name(base_name: str, device: str) -> str:
    """Create a snapshot name with a device suffix.

    Strips the /dev/ prefix and replaces slashes with dashes.

    Args:
        base_name: The base snapshot name
        device: The device path (e.g., "/dev/sdf")

    Returns:
        Name with device suffix (e.g., "my-snapshot-sdf")
    """
    suffix = device.replace("/dev/", "").replace("/", "-")
    return f"{base_name}-{suffix}" if suffix else base_name


@app.command()
@handle_cli_errors
def create(
    instance_name: str | None = typer.Argument(
        None, help="Instance name (auto-detects attached volumes)"
    ),
    volume_id: str | None = typer.Option(
        None, "--volume-id", "-v", help="Volume ID to snapshot (alternative to instance name)"
    ),
    device: str | None = typer.Option(
        None, "--device", "-D", help="Device filter when using instance name (e.g., /dev/sdf)"
    ),
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
    Create EBS snapshot(s) from a volume or instance.

    Provide an instance name to auto-detect and snapshot all attached volumes,
    or use --volume-id for a single specific volume.

    Prompts for confirmation before creating.

    Examples:
        remote snapshot create my-instance -n my-snapshot
        remote snapshot create my-instance --device /dev/sdf -n my-snapshot
        remote snapshot create -v vol-123456 -n my-snapshot
        remote snapshot create -v vol-123456 -n backup -d "Daily backup"
        remote snapshot create -v vol-123456 -n backup --yes  # Skip confirmation
    """
    # Validate option combinations
    if device and not instance_name:
        print_error("Error: --device can only be used with an instance name")
        raise typer.Exit(1)
    if volume_id and instance_name:
        print_error("Error: --volume-id and instance name are mutually exclusive")
        raise typer.Exit(1)
    if not volume_id and not instance_name:
        print_error("Error: Either an instance name or --volume-id is required")
        raise typer.Exit(1)

    if volume_id:
        # Single-volume path
        validate_volume_id(volume_id)

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
    else:
        # Instance-based path: auto-detect volumes
        resolved_name, instance_id = resolve_instance_or_exit(instance_name)
        volumes = get_volumes_for_instance(instance_id)

        if not volumes:
            print_error(f"Error: No volumes attached to instance {resolved_name}")
            raise typer.Exit(1)

        # Filter by device if specified
        if device:
            volumes = [v for v in volumes if _get_device_name(v, instance_id) == device]
            if not volumes:
                print_error(
                    f"Error: No volume with device {device} attached to instance {resolved_name}"
                )
                raise typer.Exit(1)

        # Build list of (volume_id, device, snapshot_name) tuples
        snapshot_targets = []
        for vol in volumes:
            vid = vol["VolumeId"]
            dev = _get_device_name(vol, instance_id)
            if len(volumes) == 1:
                snap_name = name
            else:
                snap_name = _make_snapshot_name(name, dev) if dev else f"{name}-{vid}"
            snapshot_targets.append((vid, dev, snap_name))

        # Confirm
        if not yes:
            details_lines = ", ".join(
                f"{vid} ({dev})" if dev else vid for vid, dev, _ in snapshot_targets
            )
            if not confirm_action(
                "create",
                "snapshot(s) for instance",
                resolved_name,
                details=f"from volumes: {details_lines}",
            ):
                print_warning("Snapshot creation cancelled")
                return

        # Create snapshots, tracking successes and failures
        created = []
        failed = []
        for vid, dev, snap_name in snapshot_targets:
            dev_info = f" ({dev})" if dev else ""
            try:
                with handle_aws_errors("EC2", "create_snapshot"):
                    snapshot = get_ec2_client().create_snapshot(
                        VolumeId=vid,
                        Description=description,
                        TagSpecifications=[
                            {
                                "ResourceType": "snapshot",
                                "Tags": [{"Key": "Name", "Value": snap_name}],
                            }
                        ],
                    )
                    validate_aws_response_structure(snapshot, ["SnapshotId"], "create_snapshot")
                print_success(f"Snapshot {snapshot['SnapshotId']} created from {vid}{dev_info}")
                created.append(vid)
            except AWSServiceError as e:
                print_error(f"Failed to create snapshot from {vid}{dev_info}: {e}")
                failed.append(vid)

        if failed:
            print_warning(f"{len(created)} snapshot(s) created, {len(failed)} failed")
            raise typer.Exit(1)


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
