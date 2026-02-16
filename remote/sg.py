"""Security group management commands for RemotePy.

This module provides commands for managing IP whitelisting on EC2 instance
security groups, including adding/removing IP addresses, listing current rules,
and creating/deleting per-instance security groups.
"""

import urllib.request
from typing import Any

import typer

from remote.exceptions import AWSServiceError, ValidationError
from remote.instance_resolver import resolve_instance_or_exit
from remote.settings import PORT_PRESETS, SSH_PORT
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
from remote.validation import sanitize_input, validate_port

app = typer.Typer()

# URL to retrieve public IP address
PUBLIC_IP_SERVICE_URL = "https://checkip.amazonaws.com"
PUBLIC_IP_TIMEOUT_SECONDS = 10


def resolve_port(port_str: str) -> int:
    """Resolve a port string to an integer port number.

    Accepts either a numeric string or a service name from PORT_PRESETS.

    Args:
        port_str: A numeric port string (e.g., "22") or service name (e.g., "ssh")

    Returns:
        The resolved port number

    Raises:
        ValidationError: If the port string is not a valid port or known service name
    """
    # Try numeric port first
    try:
        port = int(port_str)
        return validate_port(port)
    except (ValueError, TypeError):
        pass

    # Try service name lookup (case-insensitive)
    service = port_str.lower().strip()
    if service in PORT_PRESETS:
        return PORT_PRESETS[service]

    available = ", ".join(sorted(PORT_PRESETS.keys()))
    raise ValidationError(
        f"Unknown port or service: '{port_str}'. "
        f"Use a port number (1-65535) or a service name: {available}"
    )


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


def get_security_group_details(security_group_ids: list[str]) -> list[dict[str, Any]]:
    """Get full details for one or more security groups.

    Args:
        security_group_ids: List of security group IDs

    Returns:
        List of full security group dictionaries from the AWS API

    Raises:
        AWSServiceError: If AWS API call fails
    """
    if not security_group_ids:
        return []

    with handle_aws_errors("EC2", "describe_security_groups"):
        response = get_ec2_client().describe_security_groups(GroupIds=security_group_ids)

    return [dict(sg) for sg in response.get("SecurityGroups", [])]


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


def get_ip_rules_for_port(security_group_id: str, port: int = SSH_PORT) -> list[str]:
    """Get all IP addresses that have access to a security group on a given port.

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


# Backward-compatible alias
get_ssh_ip_rules = get_ip_rules_for_port


def clear_port_rules(
    security_group_id: str, port: int = SSH_PORT, exclude_ip: str | None = None
) -> int:
    """Remove all IP rules for a given port from a security group.

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


# Backward-compatible alias
clear_ssh_rules = clear_port_rules


def whitelist_ip_for_instance(
    instance_id: str,
    instance_name: str,
    ip_address: str | None = None,
    exclusive: bool = False,
    port: int = SSH_PORT,
    ports: list[int] | None = None,
) -> tuple[str, list[str]]:
    """Whitelist an IP address for access to an instance on one or more ports.

    Targets only the remotepy-managed security group (auto-created if needed).
    Pre-checks all SGs for existing rules to avoid duplicates.

    Args:
        instance_id: The EC2 instance ID
        instance_name: The instance name (used for managed SG naming)
        ip_address: The IP to whitelist (defaults to current public IP)
        exclusive: If True, remove all other IPs before adding
        port: The port to whitelist (default: 22 for SSH). Used when ports is None.
        ports: Optional list of ports to whitelist across. Overrides port parameter.

    Returns:
        Tuple of (whitelisted IP, list of security group IDs modified)

    Raises:
        ValidationError: If IP retrieval fails
        AWSServiceError: If AWS API call fails
    """
    # Get the IP to whitelist
    if ip_address is None:
        ip_address = get_public_ip()

    # Determine the port list
    port_list = ports if ports else [port]

    # Target the remotepy-managed SG
    sg_id = find_or_create_remotepy_sg(instance_name, instance_id)
    modified = False

    for p in port_list:
        # Pre-check: does the rule already exist in ANY SG?
        existing = check_existing_rule(instance_id, ip_address, p)
        if existing:
            continue  # Already whitelisted somewhere

        # If exclusive, clear existing rules in the target SG first
        if exclusive:
            clear_port_rules(sg_id, p, exclude_ip=ip_address)

        # Add the IP
        try:
            add_ip_to_security_group(sg_id, ip_address, p)
            modified = True
        except AWSServiceError as e:
            if "InvalidPermission.Duplicate" in str(e):
                continue
            raise

    modified_groups = [sg_id] if modified else []
    return ip_address, modified_groups


# ============================================================================
# Per-instance security group management (Phase 3)
# ============================================================================


def get_instance_vpc_id(instance_id: str) -> str:
    """Get the VPC ID for an instance.

    Args:
        instance_id: The EC2 instance ID

    Returns:
        The VPC ID

    Raises:
        ValidationError: If VPC ID cannot be determined
        AWSServiceError: If AWS API call fails
    """
    with handle_aws_errors("EC2", "describe_instances"):
        response = get_ec2_client().describe_instances(InstanceIds=[instance_id])

    reservations = response.get("Reservations", [])
    if not reservations:
        raise ValidationError(f"Instance {instance_id} not found")

    instances = reservations[0].get("Instances", [])
    if not instances:
        raise ValidationError(f"Instance {instance_id} not found")

    vpc_id = instances[0].get("VpcId")
    if not vpc_id:
        raise ValidationError(f"Instance {instance_id} has no VPC ID")

    return vpc_id


def create_instance_security_group(instance_name: str, vpc_id: str) -> str:
    """Create a per-instance security group managed by remotepy.

    Args:
        instance_name: The instance name (used in SG name)
        vpc_id: The VPC to create the SG in

    Returns:
        The created security group ID

    Raises:
        AWSServiceError: If AWS API call fails
    """
    sg_name = f"remotepy-{instance_name}"

    with handle_aws_errors("EC2", "create_security_group"):
        response = get_ec2_client().create_security_group(
            GroupName=sg_name,
            Description=f"Managed by remotepy for instance {instance_name}",
            VpcId=vpc_id,
            TagSpecifications=[
                {
                    "ResourceType": "security-group",
                    "Tags": [
                        {"Key": "Name", "Value": sg_name},
                        {"Key": "ManagedBy", "Value": "remotepy"},
                    ],
                }
            ],
        )

    return response["GroupId"]


def delete_instance_security_group(instance_name: str, vpc_id: str) -> str | None:
    """Find and delete the remotepy-managed security group for an instance.

    Args:
        instance_name: The instance name (used to find SG)
        vpc_id: The VPC the SG is in

    Returns:
        The deleted security group ID, or None if not found

    Raises:
        AWSServiceError: If AWS API call fails
    """
    sg_name = f"remotepy-{instance_name}"

    with handle_aws_errors("EC2", "describe_security_groups"):
        response = get_ec2_client().describe_security_groups(
            Filters=[
                {"Name": "group-name", "Values": [sg_name]},
                {"Name": "vpc-id", "Values": [vpc_id]},
            ]
        )

    security_groups = response.get("SecurityGroups", [])
    if not security_groups:
        return None

    sg_id = security_groups[0]["GroupId"]

    with handle_aws_errors("EC2", "delete_security_group"):
        get_ec2_client().delete_security_group(GroupId=sg_id)

    return sg_id


def attach_security_group_to_instance(instance_id: str, sg_id: str) -> None:
    """Add a security group to an instance's existing security group list.

    Args:
        instance_id: The EC2 instance ID
        sg_id: The security group ID to attach

    Raises:
        AWSServiceError: If AWS API call fails
    """
    # Get current security groups
    current_sgs = get_instance_security_groups(instance_id)
    current_sg_ids = [sg["GroupId"] for sg in current_sgs]

    if sg_id in current_sg_ids:
        return  # Already attached

    new_sg_ids = current_sg_ids + [sg_id]

    with handle_aws_errors("EC2", "modify_instance_attribute"):
        get_ec2_client().modify_instance_attribute(
            InstanceId=instance_id,
            Groups=new_sg_ids,
        )


def detach_security_group_from_instance(instance_id: str, sg_id: str) -> None:
    """Remove a security group from an instance's security group list.

    Args:
        instance_id: The EC2 instance ID
        sg_id: The security group ID to detach

    Raises:
        ValidationError: If removing would leave instance with no security groups
        AWSServiceError: If AWS API call fails
    """
    current_sgs = get_instance_security_groups(instance_id)
    current_sg_ids = [sg["GroupId"] for sg in current_sgs]

    if sg_id not in current_sg_ids:
        return  # Not attached

    new_sg_ids = [s for s in current_sg_ids if s != sg_id]

    if not new_sg_ids:
        raise ValidationError("Cannot remove the last security group from an instance")

    with handle_aws_errors("EC2", "modify_instance_attribute"):
        get_ec2_client().modify_instance_attribute(
            InstanceId=instance_id,
            Groups=new_sg_ids,
        )


def find_or_create_remotepy_sg(instance_name: str, instance_id: str) -> str:
    """Find the remotepy-managed SG for an instance, or create and attach one.

    Args:
        instance_name: The instance name
        instance_id: The EC2 instance ID

    Returns:
        The security group ID of the remotepy-managed SG
    """
    sg_name = f"remotepy-{instance_name}"

    # Check if it already exists among attached SGs
    attached_sgs = get_instance_security_groups(instance_id)
    for sg in attached_sgs:
        if sg["GroupName"] == sg_name:
            return sg["GroupId"]

    # Not found — create, attach, and return
    vpc_id = get_instance_vpc_id(instance_id)
    sg_id = create_instance_security_group(instance_name, vpc_id)
    attach_security_group_to_instance(instance_id, sg_id)
    print_info(f"Created managed security group {sg_name} ({sg_id})")
    return sg_id


def check_existing_rule(instance_id: str, ip_address: str, port: int) -> dict[str, str] | None:
    """Check all SGs on an instance for an existing matching rule (same IP+port).

    Args:
        instance_id: The EC2 instance ID
        ip_address: The IP address or CIDR to check
        port: The port to check

    Returns:
        Dict with 'GroupId' and 'GroupName' of the SG where the rule exists,
        or None if not found in any SG.
    """
    cidr = ip_address if "/" in ip_address else f"{ip_address}/32"
    security_groups = get_instance_security_groups(instance_id)

    for sg in security_groups:
        existing_ips = get_ip_rules_for_port(sg["GroupId"], port)
        if cidr in existing_ips:
            return {"GroupId": sg["GroupId"], "GroupName": sg["GroupName"]}

    return None


def validate_sg_for_instance(sg_id: str, instance_id: str) -> dict[str, str]:
    """Validate that a security group is attached to an instance.

    Args:
        sg_id: The security group ID to validate
        instance_id: The EC2 instance ID

    Returns:
        The SG dict with GroupId and GroupName

    Raises:
        ValidationError: If not attached
    """
    security_groups = get_instance_security_groups(instance_id)
    for sg in security_groups:
        if sg["GroupId"] == sg_id:
            return {"GroupId": sg["GroupId"], "GroupName": sg["GroupName"]}

    attached_ids = [sg["GroupId"] for sg in security_groups]
    raise ValidationError(
        f"Security group {sg_id} is not attached to instance {instance_id}. "
        f"Attached SGs: {', '.join(attached_ids)}"
    )


# ============================================================================
# CLI Commands
# ============================================================================


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
    ports: list[str] | None = typer.Option(
        None,
        "--port",
        "-p",
        help="Port(s) or service name(s) (ssh, syncthing, etc). Repeatable. Default: ssh.",
    ),
    exclusive: bool = typer.Option(
        False,
        "--exclusive",
        "-e",
        help="Remove all other IPs on the target SG before adding",
    ),
    sg: str | None = typer.Option(
        None,
        "--sg",
        "-s",
        help="Target a specific security group ID instead of the remotepy-managed SG",
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
    on the given port(s) (default: SSH port 22).

    By default, rules are added to the remotepy-managed security group
    (remotepy-{instance}), which is auto-created if needed. Use --sg to
    target a specific security group instead.

    Before adding, all security groups are checked for existing matching
    rules to avoid duplicates.

    If no IP is specified, your current public IP address is used.
    Use --exclusive to remove all other IPs from the target SG first.

    Examples:
        remote sg add-ip my-instance                              # Add your current IP for SSH
        remote sg add-ip my-instance --ip 1.2.3.4                # Add specific IP
        remote sg add-ip --exclusive                              # Add your IP, remove others
        remote sg add-ip --port 443 --ip 1.2.3.4                 # Allow HTTPS from specific IP
        remote sg add-ip --port ssh --port syncthing              # Multiple ports
        remote sg add-ip --sg sg-12345                            # Target specific SG
    """
    instance_name, instance_id = resolve_instance_or_exit(instance_name)

    # Resolve ports (default to SSH)
    resolved_ports = [resolve_port(p) for p in ports] if ports else [SSH_PORT]

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

    # Determine the target SG
    if sg:
        target_sg = validate_sg_for_instance(sg, instance_id)
        target_sg_id = target_sg["GroupId"]
        target_sg_name = target_sg["GroupName"]
    else:
        target_sg_id = find_or_create_remotepy_sg(instance_name, instance_id)
        target_sg_name = f"remotepy-{instance_name}"

    added_count = 0
    for port in resolved_ports:
        # Pre-check: does this rule already exist in ANY SG?
        existing = check_existing_rule(instance_id, ip_address, port)
        if existing:
            print_info(
                f"{ip_address} already has access to port {port} (via '{existing['GroupName']}')"
            )
            continue

        if exclusive:
            removed = clear_port_rules(target_sg_id, port, exclude_ip=ip_address)
            if removed > 0:
                print_warning(
                    f"Removed {removed} existing IP rule(s) from {target_sg_name} on port {port}"
                )

        try:
            add_ip_to_security_group(target_sg_id, ip_address, port, "Added by remote.py")
            print_success(f"Allowed {ip_address} on port {port}")
            added_count += 1
        except AWSServiceError as e:
            if "InvalidPermission.Duplicate" in str(e):
                print_info(
                    f"{ip_address} already has access to port {port} (via '{target_sg_name}')"
                )
            else:
                raise

        # Stale rule nudge: check if other IPs exist on this port in the target SG
        other_ips = get_ip_rules_for_port(target_sg_id, port)
        ip_cidr = ip_address if "/" in ip_address else f"{ip_address}/32"
        other_count = sum(1 for ip in other_ips if ip != ip_cidr)
        if other_count > 0 and not exclusive:
            print_info(
                f"Note: {other_count} other IP(s) have access on port {port}. "
                f"Use --exclusive to keep only yours."
            )

    if added_count == 0:
        print_info("No changes needed")


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
    ports: list[str] | None = typer.Option(
        None,
        "--port",
        "-p",
        help="Port(s) or service name(s) (ssh, syncthing, etc). Repeatable. Default: ssh.",
    ),
    sg: str | None = typer.Option(
        None,
        "--sg",
        "-s",
        help="Only remove from a specific security group ID",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt",
    ),
) -> None:
    """
    Remove an IP address from an instance's security groups.

    Searches all security groups attached to the instance for matching rules
    and removes them, reporting which SGs were affected. Use --sg to only
    remove from a specific security group.

    If no IP is specified, your current public IP address is used.

    Examples:
        remote sg remove-ip my-instance                 # Remove your current IP from SSH
        remote sg remove-ip my-instance --ip 1.2.3.4  # Remove specific IP
        remote sg remove-ip --port 443 --ip 1.2.3.4    # Remove HTTPS access
        remote sg remove-ip --port ssh --port syncthing # Remove from multiple ports
        remote sg remove-ip --sg sg-12345               # Only remove from specific SG
    """
    instance_name, instance_id = resolve_instance_or_exit(instance_name)

    # Resolve ports (default to SSH)
    resolved_ports = [resolve_port(p) for p in ports] if ports else [SSH_PORT]

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

    # Determine which SGs to search
    if sg:
        target_sg = validate_sg_for_instance(sg, instance_id)
        security_groups = [target_sg]
    else:
        security_groups = get_instance_security_groups(instance_id)
        if not security_groups:
            print_error(f"No security groups found for instance {instance_name}")
            raise typer.Exit(1)

    affected_sgs: list[str] = []
    for sg_info in security_groups:
        sg_id = sg_info["GroupId"]
        sg_name = sg_info["GroupName"]

        for port in resolved_ports:
            # Check if the IP exists in this security group
            existing_ips = get_ip_rules_for_port(sg_id, port)
            ip_cidr = ip_address if "/" in ip_address else f"{ip_address}/32"

            if ip_cidr not in existing_ips:
                continue

            try:
                remove_ip_from_security_group(sg_id, ip_address, port)
                if sg_name not in affected_sgs:
                    affected_sgs.append(sg_name)
            except AWSServiceError as e:
                if "InvalidPermission.NotFound" in str(e):
                    continue
                raise

    if not affected_sgs:
        print_warning(f"IP {ip_address} was not found in any security group")
    else:
        sg_list = " and ".join(f"'{s}'" for s in affected_sgs)
        port_desc = ", ".join(str(p) for p in resolved_ports)
        print_success(f"Removed {ip_address} from port {port_desc} in {sg_list}")


@app.command("list-ips")
@handle_cli_errors
def list_ips(
    instance_name: str | None = typer.Argument(None, help="Instance name"),
    ports: list[str] | None = typer.Option(
        None,
        "--port",
        "-p",
        help="Port(s) or service name(s) to filter by. Repeatable.",
    ),
    sg: str | None = typer.Option(
        None,
        "--sg",
        "-s",
        help="Filter by a specific security group ID",
    ),
) -> None:
    """
    List IP addresses allowed to access an instance.

    Shows all inbound IP rules across all security groups attached to the
    instance, with attribution showing which SG each rule belongs to.
    Use --port to filter by specific port(s). Use --sg to filter by a
    specific security group.

    Examples:
        remote sg list-ips my-instance                  # List all inbound rules
        remote sg list-ips --port 22                    # Filter by SSH port
        remote sg list-ips --port ssh --port syncthing  # Filter by multiple ports
        remote sg list-ips --sg sg-12345                # Filter by specific SG
    """
    instance_name, instance_id = resolve_instance_or_exit(instance_name)

    # Determine which SGs to show
    if sg:
        target_sg = validate_sg_for_instance(sg, instance_id)
        security_groups = [target_sg]
    else:
        security_groups = get_instance_security_groups(instance_id)
        if not security_groups:
            print_error(f"No security groups found for instance {instance_name}")
            raise typer.Exit(1)

    # Resolve port filter (None = show all)
    resolved_ports = [resolve_port(p) for p in ports] if ports else None

    # Always show port/protocol columns (default is now all rules)
    columns = [
        styled_column("Security Group", "name"),
        styled_column("Group ID", "id"),
        styled_column("Port", "numeric"),
        styled_column("Protocol"),
        styled_column("CIDR Block"),
        styled_column("Description"),
    ]

    rows: list[list[str]] = []

    for sg_info in security_groups:
        sg_id = sg_info["GroupId"]
        sg_name = sg_info["GroupName"]

        rules = get_security_group_rules(sg_id)

        for rule in rules:
            from_port = rule.get("FromPort", 0)
            to_port = rule.get("ToPort", 0)
            protocol = rule.get("IpProtocol", "tcp")

            # Filter by port if specified
            if resolved_ports is not None:
                match = False
                for p in resolved_ports:
                    if from_port <= p <= to_port and protocol in ("tcp", "-1"):
                        match = True
                        break
                if not match:
                    continue

            for ip_range in rule.get("IpRanges", []):
                cidr = ip_range.get("CidrIp", "")
                description = ip_range.get("Description", "-")
                if cidr:
                    if from_port == to_port:
                        port_display = str(from_port)
                    else:
                        port_display = f"{from_port}-{to_port}"

                    rows.append([sg_name, sg_id, port_display, protocol, cidr, description])

    if not rows:
        if resolved_ports:
            port_desc = ", ".join(str(p) for p in resolved_ports)
            print_warning(
                f"No IP rules found for port(s) {port_desc} on instance '{instance_name}'"
            )
        else:
            print_warning(f"No inbound IP rules found on instance '{instance_name}'")
        return

    if resolved_ports and len(resolved_ports) == 1:
        title = f"IP Rules for Port {resolved_ports[0]}"
    elif resolved_ports:
        title = f"IP Rules for Ports {', '.join(str(p) for p in resolved_ports)}"
    else:
        title = "All Inbound IP Rules"
    console.print(create_table(title, columns, rows))


@app.command("list")
@handle_cli_errors
def list_sgs(
    instance_name: str | None = typer.Argument(None, help="Instance name"),
) -> None:
    """
    List security groups attached to an instance.

    Shows all security groups associated with the instance, including
    their inbound rule count and whether they are managed by remotepy.

    Examples:
        remote sg list my-instance
        remote sg list
    """
    instance_name, instance_id = resolve_instance_or_exit(instance_name)

    # Get basic SG list from the instance
    security_groups = get_instance_security_groups(instance_id)
    if not security_groups:
        print_error(f"No security groups found for instance '{instance_name}'")
        raise typer.Exit(1)

    # Get full details for all SGs in a single call
    sg_ids = [sg["GroupId"] for sg in security_groups]
    sg_details = get_security_group_details(sg_ids)

    columns = [
        styled_column("Name", "name"),
        styled_column("Group ID", "id"),
        styled_column("Inbound Rules", "numeric"),
        styled_column("Managed"),
        styled_column("Description"),
    ]

    rows: list[list[str]] = []
    for sg in sg_details:
        tags = {t["Key"]: t["Value"] for t in sg.get("Tags", [])}
        managed = "Yes" if tags.get("ManagedBy") == "remotepy" else "-"
        inbound_count = str(len(sg.get("IpPermissions", [])))
        rows.append(
            [
                sg.get("GroupName", "-"),
                sg.get("GroupId", "-"),
                inbound_count,
                managed,
                sg.get("Description", "-"),
            ]
        )

    console.print(create_table(f"Security Groups for '{instance_name}'", columns, rows))


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


@app.command("create")
@handle_cli_errors
def create_sg(
    instance_name: str | None = typer.Argument(None, help="Instance name"),
) -> None:
    """
    Create a per-instance security group and attach it.

    Creates a security group named 'remotepy-{instance_name}' in the instance's
    VPC and attaches it to the instance. This allows managing IP rules independently
    from the instance's existing security groups.

    If the security group already exists and is attached, this is a no-op.

    Examples:
        remote sg create my-instance
    """
    instance_name, instance_id = resolve_instance_or_exit(instance_name)

    sg_name = f"remotepy-{instance_name}"

    # Check if already exists
    attached_sgs = get_instance_security_groups(instance_id)
    for existing_sg in attached_sgs:
        if existing_sg["GroupName"] == sg_name:
            print_info(
                f"Security group {sg_name} ({existing_sg['GroupId']}) already exists and is attached"
            )
            return

    print_info(f"Creating security group for instance '{instance_name}'...")

    vpc_id = get_instance_vpc_id(instance_id)
    sg_id = create_instance_security_group(instance_name, vpc_id)
    attach_security_group_to_instance(instance_id, sg_id)

    print_success(f"Created and attached security group {sg_name} ({sg_id})")


@app.command("delete")
@handle_cli_errors
def delete_sg(
    instance_name: str | None = typer.Argument(None, help="Instance name"),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt",
    ),
) -> None:
    """
    Delete a per-instance security group.

    Detaches and deletes the 'remotepy-{instance_name}' security group.

    Examples:
        remote sg delete my-instance
        remote sg delete my-instance --yes
    """
    instance_name, instance_id = resolve_instance_or_exit(instance_name)

    sg_name = f"remotepy-{instance_name}"

    if not yes:
        if not confirm_action("delete", "security group", sg_name):
            print_warning("Operation cancelled")
            return

    vpc_id = get_instance_vpc_id(instance_id)

    # Find the SG first to get its ID for detaching
    with handle_aws_errors("EC2", "describe_security_groups"):
        response = get_ec2_client().describe_security_groups(
            Filters=[
                {"Name": "group-name", "Values": [sg_name]},
                {"Name": "vpc-id", "Values": [vpc_id]},
            ]
        )

    security_groups = response.get("SecurityGroups", [])
    if not security_groups:
        print_warning(f"Security group '{sg_name}' not found")
        return

    sg_id = security_groups[0]["GroupId"]

    # Detach from instance first
    detach_security_group_from_instance(instance_id, sg_id)

    # Then delete
    deleted_id = delete_instance_security_group(instance_name, vpc_id)
    if deleted_id:
        print_success(f"Deleted security group {sg_name} ({deleted_id})")
    else:
        print_warning(f"Security group '{sg_name}' not found")
