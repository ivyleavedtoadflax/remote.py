from typing import Any

import typer

from remote.instance_resolver import resolve_instance_or_exit
from remote.utils import (
    confirm_action,
    console,
    create_table,
    get_ec2_client,
    get_status_style,
    get_volume_name,
    handle_aws_errors,
    handle_cli_errors,
    print_warning,
    styled_column,
)
from remote.validation import validate_aws_response_structure, validate_volume_id

app = typer.Typer()


@app.command("ls")
@app.command("list")
@handle_cli_errors
def list_volumes(instance_name: str | None = typer.Argument(None, help="Instance name")) -> None:
    """
    List EBS volumes attached to an instance.

    Shows volume ID, size, state, and availability zone.
    Uses the default instance from config if no name is provided.

    Examples:
        remote volume ls                  # List volumes for default instance
        remote volume ls my-instance      # List volumes for specific instance
        remote volume list my-instance    # Verbose form
    """
    instance_name, instance_id = resolve_instance_or_exit(instance_name)

    print_warning(f"Listing volumes attached to instance {instance_name}")

    # Use server-side filtering to only fetch volumes attached to this instance
    with handle_aws_errors("EC2", "describe_volumes"):
        volumes = get_ec2_client().describe_volumes(
            Filters=[{"Name": "attachment.instance-id", "Values": [instance_id]}]
        )
        validate_aws_response_structure(volumes, ["Volumes"], "describe_volumes")

    columns: list[dict[str, Any]] = [
        styled_column("Instance Name", "name", no_wrap=True),
        styled_column("Instance", "id", no_wrap=True),
        styled_column("Volume Name", "name", no_wrap=True),
        styled_column("VolumeId", "id", no_wrap=True),
        styled_column("Size", "numeric", justify="right"),
        styled_column("State"),
        styled_column("AvailabilityZone"),
    ]

    rows = []
    for volume in volumes["Volumes"]:
        state = volume["State"]
        state_style = get_status_style(state)
        rows.append(
            [
                instance_name or "",
                instance_id,
                get_volume_name(volume["VolumeId"]),
                volume["VolumeId"],
                str(volume["Size"]),
                f"[{state_style}]{state}[/{state_style}]",
                volume["AvailabilityZone"],
            ]
        )

    console.print(create_table("Volumes", columns, rows))


# Root device patterns - devices that are typically the root/boot volume
ROOT_DEVICE_PATTERNS = (
    "/dev/sda1",
    "/dev/xvda",
    "/dev/nvme0n1",
)


def _find_root_volume(volumes: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Find the root volume from a list of volumes.

    Identifies the root volume by checking device attachment names against
    common root device patterns.

    Args:
        volumes: List of volume dictionaries from describe_volumes

    Returns:
        The root volume dictionary, or None if not found
    """
    for volume in volumes:
        attachments = volume.get("Attachments", [])
        for attachment in attachments:
            device = attachment.get("Device", "")
            if device in ROOT_DEVICE_PATTERNS or device.startswith("/dev/xvda"):
                return volume
    return None


def _find_volume_by_id(volumes: list[dict[str, Any]], volume_id: str) -> dict[str, Any] | None:
    """Find a specific volume by ID from a list of volumes.

    Args:
        volumes: List of volume dictionaries from describe_volumes
        volume_id: The volume ID to find

    Returns:
        The volume dictionary, or None if not found
    """
    for volume in volumes:
        if volume.get("VolumeId") == volume_id:
            return volume
    return None


@app.command("resize")
@handle_cli_errors
def resize_volume(
    instance_name: str | None = typer.Argument(None, help="Instance name"),
    size: int = typer.Option(
        ...,
        "--size",
        "-s",
        help="New size in GB (must be larger than current size)",
    ),
    volume_id: str | None = typer.Option(
        None,
        "--volume",
        "-v",
        help="Specific volume ID to resize. If not provided, resizes the root volume.",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt",
    ),
) -> None:
    """
    Resize an EBS volume attached to an instance.

    By default, resizes the root volume. Use --volume to specify a different volume.
    The new size must be larger than the current size (EBS volumes cannot be shrunk).

    After resizing, you may need to extend the filesystem on the instance:
        sudo growpart /dev/nvme0n1 1
        sudo resize2fs /dev/nvme0n1p1

    Examples:
        remote volume resize my-instance --size 20           # Resize root to 20GB
        remote volume resize --size 50                       # Resize default instance root
        remote volume resize my-instance -s 100 --volume vol-xxx  # Resize specific volume
        remote volume resize my-instance --size 20 --yes     # Skip confirmation
    """
    instance_name, instance_id = resolve_instance_or_exit(instance_name)

    # Validate volume_id format if provided
    if volume_id:
        volume_id = validate_volume_id(volume_id)

    # Get volumes attached to the instance
    with handle_aws_errors("EC2", "describe_volumes"):
        response = get_ec2_client().describe_volumes(
            Filters=[{"Name": "attachment.instance-id", "Values": [instance_id]}]
        )

    volumes = response.get("Volumes", [])

    if not volumes:
        typer.secho(
            f"Error: No volumes attached to instance {instance_name}",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    # Find the target volume
    if volume_id:
        target_volume = _find_volume_by_id(volumes, volume_id)
        if not target_volume:
            typer.secho(
                f"Error: Volume {volume_id} is not attached to instance {instance_name}",
                fg=typer.colors.RED,
            )
            raise typer.Exit(1)
    else:
        target_volume = _find_root_volume(volumes)
        if not target_volume:
            typer.secho(
                f"Error: No root volume found for instance {instance_name}",
                fg=typer.colors.RED,
            )
            raise typer.Exit(1)

    current_size = target_volume["Size"]
    target_volume_id = target_volume["VolumeId"]

    # Validate new size
    if size == current_size:
        typer.secho(
            f"Error: Volume {target_volume_id} is already {current_size}GB",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    if size < current_size:
        typer.secho(
            f"Error: New size ({size}GB) must be greater than current size ({current_size}GB). "
            "EBS volumes cannot be shrunk.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    # Confirm action
    if not yes:
        if not confirm_action(
            "resize",
            "volume",
            target_volume_id,
            details=f"from {current_size}GB to {size}GB",
        ):
            typer.secho("Resize cancelled", fg=typer.colors.YELLOW)
            raise typer.Exit(1)

    # Resize the volume
    typer.secho(
        f"Resizing volume {target_volume_id} from {current_size}GB to {size}GB...",
        fg=typer.colors.YELLOW,
    )

    with handle_aws_errors("EC2", "modify_volume"):
        response = get_ec2_client().modify_volume(
            VolumeId=target_volume_id,
            Size=size,
        )

    modification = response.get("VolumeModification", {})
    state = modification.get("ModificationState", "unknown")

    typer.secho(
        f"Volume {target_volume_id} resize initiated (state: {state})",
        fg=typer.colors.GREEN,
    )
    typer.secho(f"  Original size: {modification.get('OriginalSize', current_size)}GB")
    typer.secho(f"  Target size: {modification.get('TargetSize', size)}GB")

    typer.secho(
        "\nNote: After the volume modification completes, extend the filesystem:",
        fg=typer.colors.YELLOW,
    )
    typer.secho("  sudo growpart /dev/nvme0n1 1")
    typer.secho("  sudo resize2fs /dev/nvme0n1p1")
