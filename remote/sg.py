"""Security group management commands for RemotePy.

This module provides commands for managing IP whitelisting on EC2 instance
security groups, including adding/removing IP addresses and listing current rules.
"""

import urllib.request
from typing import Any

import typer

from remote.exceptions import AWSServiceError, ValidationError
from remote.instance_resolver import resolve_instance_or_exit
from remote.settings import SSH_PORT
from remote.utils import (
    confirm_action,
    console,
    create_table,
    get_ec2_client,
    handle_aws_errors,
    handle_cli_errors,
    print_error,
    print_info,
    print_success,
    print_warning,
    styled_column,
)
from remote.validation import sanitize_input

app = typer.Typer()

# URL to retrieve public IP address
PUBLIC_IP_SERVICE_URL = "https://checkip.amazonaws.com"
PUBLIC_IP_TIMEOUT_SECONDS = 10


def get_public_ip() -> str:
    """Get the current user's public IP address.

    Uses AWS's checkip service to retrieve the public IP address.

    Returns:
        The public IP address as a string (e.g., "203.0.113.1")

    Raises:
        ValidationError: If unable to retrieve the public IP address
    """
    try:
        with urllib.request.urlopen(  # nosec B310
            PUBLIC_IP_SERVICE_URL, timeout=PUBLIC_IP_TIMEOUT_SECONDS
        ) as response:
            ip: str = response.read().decode("utf-8").strip()
            # Validate it looks like an IP address
            parts = ip.split(".")
            if len(parts) != 4 or not all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
                raise ValidationError(f"Invalid IP address received: {ip}")
            return ip
    except urllib.error.URLError as e:
        raise ValidationError(f"Failed to retrieve public IP address: {e}")
    except TimeoutError:
        raise ValidationError("Timeout while retrieving public IP address")


def get_instance_security_groups(instance_id: str) -> list[dict[str, Any]]:
    """Get the security groups attached to an instance.

    Args:
        instance_id: The EC2 instance ID

    Returns:
        List of security group dictionaries with 'GroupId' and 'GroupName' keys

    Raises:
        AWSServiceError: If AWS API call fails
    """
    with handle_aws_errors("EC2", "describe_instances"):
        response = get_ec2_client().describe_instances(InstanceIds=[instance_id])

    reservations = response.get("Reservations", [])
    if not reservations:
        return []

    instances = reservations[0].get("Instances", [])
    if not instances:
        return []

    # Cast security groups to list[dict[str, Any]] for type checker
    security_groups = instances[0].get("SecurityGroups", [])
    return [dict(sg) for sg in security_groups]


def get_security_group_rules(security_group_id: str) -> list[dict[str, Any]]:
    """Get the inbound rules for a security group.

    Args:
        security_group_id: The security group ID

    Returns:
        List of inbound permission rules

    Raises:
        AWSServiceError: If AWS API call fails
    """
    with handle_aws_errors("EC2", "describe_security_groups"):
        response = get_ec2_client().describe_security_groups(GroupIds=[security_group_id])

    security_groups = response.get("SecurityGroups", [])
    if not security_groups:
        return []

    # Cast permissions to list[dict[str, Any]] for type checker
    permissions = security_groups[0].get("IpPermissions", [])
    return [dict(p) for p in permissions]


def add_ip_to_security_group(
    security_group_id: str,
    ip_address: str,
    port: int = SSH_PORT,
    description: str = "Added by remote.py",
) -> None:
    """Add an IP address to a security group's inbound rules.

    Args:
        security_group_id: The security group ID
        ip_address: The IP address or CIDR block to add (e.g., "10.0.0.1" or "0.0.0.0/0")
        port: The port to allow (default: 22 for SSH)
        description: Description for the rule

    Raises:
        AWSServiceError: If AWS API call fails
    """
    # Use CIDR as-is if already provided, otherwise append /32
    cidr = ip_address if "/" in ip_address else f"{ip_address}/32"

    with handle_aws_errors("EC2", "authorize_security_group_ingress"):
        get_ec2_client().authorize_security_group_ingress(
            GroupId=security_group_id,
            IpPermissions=[
                {
                    "IpProtocol": "tcp",
                    "FromPort": port,
                    "ToPort": port,
                    "IpRanges": [{"CidrIp": cidr, "Description": description}],
                }
            ],
        )


def remove_ip_from_security_group(
    security_group_id: str,
    ip_address: str,
    port: int = SSH_PORT,
) -> None:
    """Remove an IP address from a security group's inbound rules.

    Args:
        security_group_id: The security group ID
        ip_address: The IP address or CIDR block to remove (e.g., "10.0.0.1" or "0.0.0.0/0")
        port: The port to remove the rule for (default: 22 for SSH)

    Raises:
        AWSServiceError: If AWS API call fails
    """
    # Use CIDR as-is if already provided, otherwise append /32
    cidr = ip_address if "/" in ip_address else f"{ip_address}/32"

    with handle_aws_errors("EC2", "revoke_security_group_ingress"):
        get_ec2_client().revoke_security_group_ingress(
            GroupId=security_group_id,
            IpPermissions=[
                {
                    "IpProtocol": "tcp",
                    "FromPort": port,
                    "ToPort": port,
                    "IpRanges": [{"CidrIp": cidr}],
                }
            ],
        )


def get_ssh_ip_rules(security_group_id: str, port: int = SSH_PORT) -> list[str]:
    """Get all IP addresses that have SSH access to a security group.

    Args:
        security_group_id: The security group ID
        port: The port to check (default: 22 for SSH)

    Returns:
        List of CIDR blocks with access to the specified port
    """
    rules = get_security_group_rules(security_group_id)
    ip_ranges = []

    for rule in rules:
        # Check if this rule applies to our port
        from_port = rule.get("FromPort", 0)
        to_port = rule.get("ToPort", 0)

        if from_port <= port <= to_port and rule.get("IpProtocol") in ("tcp", "-1"):
            for ip_range in rule.get("IpRanges", []):
                cidr = ip_range.get("CidrIp", "")
                if cidr:
                    ip_ranges.append(cidr)

    return ip_ranges


def clear_ssh_rules(
    security_group_id: str, port: int = SSH_PORT, exclude_ip: str | None = None
) -> int:
    """Remove all SSH IP rules from a security group.

    Args:
        security_group_id: The security group ID
        port: The port to clear rules for (default: 22 for SSH)
        exclude_ip: Optional IP to exclude from clearing (with or without /32 suffix)

    Returns:
        Number of rules removed
    """
    rules = get_security_group_rules(security_group_id)
    removed_count = 0

    # Normalize exclude_ip to CIDR format
    exclude_cidr = None
    if exclude_ip:
        exclude_cidr = exclude_ip if "/" in exclude_ip else f"{exclude_ip}/32"

    for rule in rules:
        from_port = rule.get("FromPort", 0)
        to_port = rule.get("ToPort", 0)

        if from_port <= port <= to_port and rule.get("IpProtocol") in ("tcp", "-1"):
            for ip_range in rule.get("IpRanges", []):
                cidr = ip_range.get("CidrIp", "")
                if cidr and cidr != exclude_cidr:
                    # Extract IP from CIDR
                    ip = cidr.split("/")[0]
                    try:
                        remove_ip_from_security_group(security_group_id, ip, port)
                        removed_count += 1
                    except AWSServiceError:
                        # Rule might have already been removed or have different structure
                        pass

    return removed_count


def whitelist_ip_for_instance(
    instance_id: str,
    ip_address: str | None = None,
    exclusive: bool = False,
    port: int = SSH_PORT,
) -> tuple[str, list[str]]:
    """Whitelist an IP address for SSH access to an instance.

    Args:
        instance_id: The EC2 instance ID
        ip_address: The IP to whitelist (defaults to current public IP)
        exclusive: If True, remove all other IPs before adding
        port: The port to whitelist (default: 22 for SSH)

    Returns:
        Tuple of (whitelisted IP, list of security group IDs modified)

    Raises:
        ValidationError: If no security groups found or IP retrieval fails
        AWSServiceError: If AWS API call fails
    """
    # Get the IP to whitelist
    if ip_address is None:
        ip_address = get_public_ip()

    # Get the instance's security groups
    security_groups = get_instance_security_groups(instance_id)
    if not security_groups:
        raise ValidationError(f"No security groups found for instance {instance_id}")

    modified_groups = []

    for sg in security_groups:
        sg_id = sg["GroupId"]

        # If exclusive, clear existing SSH rules first
        if exclusive:
            clear_ssh_rules(sg_id, port, exclude_ip=ip_address)

        # Check if the IP is already whitelisted
        existing_ips = get_ssh_ip_rules(sg_id, port)
        # Use CIDR as-is if provided, otherwise append /32
        ip_cidr = ip_address if "/" in ip_address else f"{ip_address}/32"

        if ip_cidr in existing_ips:
            continue  # Already whitelisted

        # Add the IP
        try:
            add_ip_to_security_group(sg_id, ip_address, port)
            modified_groups.append(sg_id)
        except AWSServiceError as e:
            # Check if it's a duplicate rule error
            if "InvalidPermission.Duplicate" in str(e):
                continue
            raise

    return ip_address, modified_groups


@app.command("add-ip")
@handle_cli_errors
def add_ip(
    instance_name: str | None = typer.Argument(None, help="Instance name"),
    ip_address: str | None = typer.Option(
        None,
        "--ip",
        "-i",
        help="IP address to add (defaults to your current public IP)",
    ),
    port: int = typer.Option(
        SSH_PORT,
        "--port",
        "-p",
        help="Port to allow access on (default: 22)",
    ),
    exclusive: bool = typer.Option(
        False,
        "--exclusive",
        "-e",
        help="Remove all other IPs before adding (makes this IP the only one allowed)",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt for --exclusive",
    ),
) -> None:
    """
    Add an IP address to an instance's security group.

    Adds an inbound rule allowing the specified IP to access the instance
    on the given port (default: SSH port 22).

    If no IP is specified, your current public IP address is used.
    Use --exclusive to remove all other IPs first, making this the only
    allowed IP address.

    Examples:
        remote sg add-ip my-instance                    # Add your current IP
        remote sg add-ip my-instance --ip 1.2.3.4      # Add specific IP
        remote sg add-ip --exclusive                    # Add your IP, remove others
        remote sg add-ip --port 443 --ip 1.2.3.4       # Allow HTTPS from specific IP
    """
    instance_name, instance_id = resolve_instance_or_exit(instance_name)

    # Get the IP to whitelist
    if ip_address is None:
        print_info("Retrieving your public IP address...")
        ip_address = get_public_ip()
        print_info(f"Your public IP: {ip_address}")
    else:
        # Validate and sanitize the provided IP
        ip_address = sanitize_input(ip_address)
        if not ip_address:
            print_error("IP address cannot be empty")
            raise typer.Exit(1)

    # Confirm exclusive operation
    if exclusive and not yes:
        if not confirm_action(
            "remove all other IPs and add",
            "IP",
            ip_address,
            details=f"to instance '{instance_name}'",
        ):
            print_warning("Operation cancelled")
            return

    # Get security groups
    security_groups = get_instance_security_groups(instance_id)
    if not security_groups:
        print_error(f"No security groups found for instance {instance_name}")
        raise typer.Exit(1)

    sg_names = [f"{sg['GroupName']} ({sg['GroupId']})" for sg in security_groups]
    print_info(f"Security groups: {', '.join(sg_names)}")

    modified_count = 0
    for sg in security_groups:
        sg_id = sg["GroupId"]
        sg_name = sg["GroupName"]

        if exclusive:
            removed = clear_ssh_rules(sg_id, port, exclude_ip=ip_address)
            if removed > 0:
                print_warning(f"Removed {removed} existing IP rule(s) from {sg_name}")

        # Check if already whitelisted
        existing_ips = get_ssh_ip_rules(sg_id, port)
        # Use CIDR as-is if provided, otherwise append /32
        ip_cidr = ip_address if "/" in ip_address else f"{ip_address}/32"

        if ip_cidr in existing_ips:
            print_info(f"IP {ip_address} already whitelisted in {sg_name}")
            continue

        try:
            add_ip_to_security_group(sg_id, ip_address, port, "Added by remote.py")
            print_success(f"Added {ip_address} to {sg_name} on port {port}")
            modified_count += 1
        except AWSServiceError as e:
            if "InvalidPermission.Duplicate" in str(e):
                print_info(f"IP {ip_address} already whitelisted in {sg_name}")
            else:
                raise

    if modified_count == 0:
        print_info("No changes made - IP already whitelisted in all security groups")
    else:
        print_success(f"IP {ip_address} whitelisted for instance '{instance_name}'")


@app.command("remove-ip")
@handle_cli_errors
def remove_ip(
    instance_name: str | None = typer.Argument(None, help="Instance name"),
    ip_address: str | None = typer.Option(
        None,
        "--ip",
        "-i",
        help="IP address to remove (defaults to your current public IP)",
    ),
    port: int = typer.Option(
        SSH_PORT,
        "--port",
        "-p",
        help="Port to remove access from (default: 22)",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt",
    ),
) -> None:
    """
    Remove an IP address from an instance's security group.

    Removes the inbound rule allowing the specified IP to access the instance
    on the given port (default: SSH port 22).

    If no IP is specified, your current public IP address is used.

    Examples:
        remote sg remove-ip my-instance                 # Remove your current IP
        remote sg remove-ip my-instance --ip 1.2.3.4  # Remove specific IP
        remote sg remove-ip --port 443 --ip 1.2.3.4    # Remove HTTPS access
    """
    instance_name, instance_id = resolve_instance_or_exit(instance_name)

    # Get the IP to remove
    if ip_address is None:
        print_info("Retrieving your public IP address...")
        ip_address = get_public_ip()
        print_info(f"Your public IP: {ip_address}")
    else:
        ip_address = sanitize_input(ip_address)
        if not ip_address:
            print_error("IP address cannot be empty")
            raise typer.Exit(1)

    # Confirm removal
    if not yes:
        if not confirm_action(
            "remove",
            "IP",
            ip_address,
            details=f"from instance '{instance_name}'",
        ):
            print_warning("Operation cancelled")
            return

    # Get security groups
    security_groups = get_instance_security_groups(instance_id)
    if not security_groups:
        print_error(f"No security groups found for instance {instance_name}")
        raise typer.Exit(1)

    removed_count = 0
    for sg in security_groups:
        sg_id = sg["GroupId"]
        sg_name = sg["GroupName"]

        # Check if the IP exists in this security group
        existing_ips = get_ssh_ip_rules(sg_id, port)
        # Use CIDR as-is if provided, otherwise append /32
        ip_cidr = ip_address if "/" in ip_address else f"{ip_address}/32"

        if ip_cidr not in existing_ips:
            continue

        try:
            remove_ip_from_security_group(sg_id, ip_address, port)
            print_success(f"Removed {ip_address} from {sg_name} on port {port}")
            removed_count += 1
        except AWSServiceError as e:
            if "InvalidPermission.NotFound" in str(e):
                continue
            raise

    if removed_count == 0:
        print_warning(f"IP {ip_address} was not found in any security group")
    else:
        print_success(f"Removed {ip_address} from {removed_count} security group(s)")


@app.command("list-ips")
@handle_cli_errors
def list_ips(
    instance_name: str | None = typer.Argument(None, help="Instance name"),
    port: int = typer.Option(
        SSH_PORT,
        "--port",
        "-p",
        help="Port to list rules for (default: 22)",
    ),
) -> None:
    """
    List IP addresses allowed to access an instance.

    Shows all IP addresses that have inbound access to the instance
    on the specified port (default: SSH port 22).

    Examples:
        remote sg list-ips my-instance                  # List SSH-allowed IPs
        remote sg list-ips --port 443                   # List HTTPS-allowed IPs
    """
    instance_name, instance_id = resolve_instance_or_exit(instance_name)

    # Get security groups
    security_groups = get_instance_security_groups(instance_id)
    if not security_groups:
        print_error(f"No security groups found for instance {instance_name}")
        raise typer.Exit(1)

    # Build table data
    columns = [
        styled_column("Security Group", "name"),
        styled_column("Group ID", "id"),
        styled_column("CIDR Block"),
        styled_column("Description"),
    ]

    rows: list[list[str]] = []

    for sg in security_groups:
        sg_id = sg["GroupId"]
        sg_name = sg["GroupName"]

        # Get detailed rules to include descriptions
        rules = get_security_group_rules(sg_id)

        for rule in rules:
            from_port = rule.get("FromPort", 0)
            to_port = rule.get("ToPort", 0)

            if from_port <= port <= to_port and rule.get("IpProtocol") in ("tcp", "-1"):
                for ip_range in rule.get("IpRanges", []):
                    cidr = ip_range.get("CidrIp", "")
                    description = ip_range.get("Description", "-")
                    if cidr:
                        rows.append([sg_name, sg_id, cidr, description])

    if not rows:
        print_warning(f"No IP rules found for port {port} on instance '{instance_name}'")
        return

    console.print(create_table(f"IP Rules for Port {port}", columns, rows))


@app.command("my-ip")
@handle_cli_errors
def my_ip() -> None:
    """
    Display your current public IP address.

    Uses AWS's checkip service to retrieve your public IP address.
    This is the IP that would be used when adding rules without specifying an IP.

    Examples:
        remote sg my-ip
    """
    print_info("Retrieving your public IP address...")
    ip = get_public_ip()
    print_success(f"Your public IP: {ip}")
