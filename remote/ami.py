from typing import Any, cast

import typer

from remote.exceptions import (
    AWSServiceError,
    ResourceNotFoundError,
)
from remote.instance_resolver import resolve_instance_or_exit
from remote.utils import (
    confirm_action,
    console,
    create_table,
    get_account_id,
    get_ec2_client,
    get_launch_template_versions,
    get_launch_templates,
    get_status_style,
    handle_aws_errors,
    handle_cli_errors,
    print_error,
    print_success,
    print_warning,
    styled_column,
)
from remote.validation import validate_aws_response_structure, validate_instance_type

app = typer.Typer()


@app.command()
@handle_cli_errors
def create(
    instance_name: str | None = typer.Argument(None, help="Instance name"),
    name: str | None = typer.Option(None, help="AMI name"),
    description: str | None = typer.Option(None, help="Description"),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt (for scripting)",
    ),
) -> None:
    """
    Create an AMI from an EC2 instance.

    Creates an Amazon Machine Image without rebooting the instance.
    Uses the default instance from config if no instance name is provided.
    Prompts for confirmation before creating.

    Examples:
        remote ami create                                 # From default instance
        remote ami create my-server                       # From specific instance
        remote ami create my-server --name my-ami --description "Production snapshot"
        remote ami create my-server --yes                 # Create without confirmation
    """
    instance_name, instance_id = resolve_instance_or_exit(instance_name)

    # Ensure required fields have values
    ami_name = name if name else f"ami-{instance_name}"
    ami_description = description if description else ""

    # Confirm AMI creation
    if not yes:
        if not confirm_action("create", "AMI", ami_name, details=f"from instance {instance_name}"):
            print_warning("AMI creation cancelled")
            return

    with handle_aws_errors("EC2", "create_image"):
        ami = get_ec2_client().create_image(
            InstanceId=instance_id,
            Name=ami_name,
            Description=ami_description,
            NoReboot=True,
        )
        validate_aws_response_structure(ami, ["ImageId"], "create_image")
    print_success(f"AMI {ami['ImageId']} created")


@app.command("ls")
@app.command("list")
@handle_cli_errors
def list_amis() -> None:
    """
    List all AMIs owned by the current account.

    Displays image ID, name, state, and creation date.
    """
    account_id = get_account_id()

    # Use paginator to handle large AMI counts
    with handle_aws_errors("EC2", "describe_images"):
        paginator = get_ec2_client().get_paginator("describe_images")
        images: list[dict[str, Any]] = []

        for page in paginator.paginate(Owners=[account_id]):
            validate_aws_response_structure(page, ["Images"], "describe_images")
            images.extend(cast(list[dict[str, Any]], page["Images"]))

    columns = [
        styled_column("ImageId", "id"),
        styled_column("Name", "name"),
        styled_column("State"),
        styled_column("CreationDate"),
    ]

    rows = []
    for ami in images:
        state = ami["State"]
        state_style = get_status_style(state)
        rows.append(
            [
                ami["ImageId"],
                ami["Name"],
                f"[{state_style}]{state}[/{state_style}]",
                str(ami["CreationDate"]),
            ]
        )

    console.print(create_table("Amazon Machine Images", columns, rows))


@app.command("ls-templates")
@app.command("list-templates")
@handle_cli_errors
def list_launch_templates(
    filter: str | None = typer.Option(None, "-f", "--filter", help="Filter by name"),
    details: bool = typer.Option(False, "-d", "--details", help="Show template details"),
) -> None:
    """
    List all available EC2 launch templates.

    Displays template ID, name, and latest version number.
    Use --filter to search templates by name pattern.
    Use --details to show additional template information.

    Examples:
        remote ami list-templates                   # List all templates
        remote ami list-templates -f web            # Filter by 'web' in name
        remote ami list-templates -d                # Show details
    """
    templates = get_launch_templates(name_filter=filter)

    if not templates:
        print_warning("No launch templates found")
        return

    if details:
        # Show detailed view with version info
        for template in templates:
            console.print()
            console.print(
                f"[bold cyan]{template['LaunchTemplateName']}[/bold cyan] ({template['LaunchTemplateId']})"
            )
            console.print(f"  Latest Version: {template['LatestVersionNumber']}")
            console.print(f"  Created: {template.get('CreateTime', 'N/A')}")

            # Get latest version details
            try:
                versions = get_launch_template_versions(template["LaunchTemplateName"])
                if versions:
                    latest = versions[0]
                    data = latest.get("LaunchTemplateData", {})
                    console.print(f"  Instance Type: {data.get('InstanceType', 'N/A')}")
                    console.print(f"  AMI: {data.get('ImageId', 'N/A')}")
                    console.print(f"  Key Pair: {data.get('KeyName', 'N/A')}")
                    security_groups = data.get("SecurityGroupIds", [])
                    if security_groups:
                        console.print(f"  Security Groups: {', '.join(security_groups)}")
            except (ResourceNotFoundError, AWSServiceError):
                console.print("  [yellow]Warning: Could not fetch version details[/yellow]")
    else:
        # Standard table view
        columns = [
            styled_column("Number", "numeric", justify="right"),
            styled_column("LaunchTemplateId", "id"),
            styled_column("LaunchTemplateName", "name"),
            styled_column("Version", "numeric", justify="right"),
        ]

        rows = [
            [
                str(i),
                template["LaunchTemplateId"],
                template["LaunchTemplateName"],
                str(template["LatestVersionNumber"]),
            ]
            for i, template in enumerate(templates, 1)
        ]

        console.print(create_table("Launch Templates", columns, rows))


@app.command("template-versions")
@handle_cli_errors
def template_versions(
    template_name: str = typer.Argument(..., help="Launch template name"),
) -> None:
    """
    Show version history for a launch template.

    Displays all versions with creation date and description.

    Examples:
        remote ami template-versions my-template
    """
    versions = get_launch_template_versions(template_name)

    if not versions:
        print_warning("No versions found")
        return

    columns = [
        styled_column("Version", "numeric", justify="right"),
        styled_column("Created"),
        styled_column("Description"),
        styled_column("Default", justify="center"),
    ]

    rows = []
    for version in versions:
        is_default = "✓" if version.get("DefaultVersion", False) else ""
        description = version.get("VersionDescription", "")
        created = str(version.get("CreateTime", "N/A"))
        rows.append(
            [
                str(version["VersionNumber"]),
                created,
                description,
                is_default,
            ]
        )

    console.print(create_table(f"Versions for {template_name}", columns, rows))


@app.command("template-info")
@handle_cli_errors
def template_info(
    template_name: str = typer.Argument(..., help="Launch template name"),
    version: str = typer.Option("$Latest", "-V", "--version", help="Template version"),
) -> None:
    """
    Show detailed information for a launch template.

    Displays instance type, AMI, key pair, security groups, and more.

    Examples:
        remote ami template-info my-template
        remote ami template-info my-template -V 2
    """
    versions = get_launch_template_versions(template_name)

    if not versions:
        print_warning("No versions found")
        return

    # Find the requested version
    target_version = None
    if version == "$Latest":
        target_version = versions[0]  # First is latest
    else:
        for v in versions:
            if str(v["VersionNumber"]) == version:
                target_version = v
                break

    if not target_version:
        print_error(f"Version {version} not found")
        raise typer.Exit(1)

    data = target_version.get("LaunchTemplateData", {})

    console.print()
    console.print(f"[bold cyan]Template:[/bold cyan] {template_name}")
    console.print(f"[bold cyan]Version:[/bold cyan] {target_version['VersionNumber']}")
    console.print(
        f"[bold cyan]Description:[/bold cyan] {target_version.get('VersionDescription', 'N/A')}"
    )
    console.print(f"[bold cyan]Created:[/bold cyan] {target_version.get('CreateTime', 'N/A')}")
    console.print()
    console.print("[bold]Instance Configuration:[/bold]")
    console.print(f"  Instance Type: {data.get('InstanceType', 'N/A')}")
    console.print(f"  AMI: {data.get('ImageId', 'N/A')}")
    console.print(f"  Key Pair: {data.get('KeyName', 'N/A')}")

    security_groups = data.get("SecurityGroupIds", [])
    if security_groups:
        console.print(f"  Security Groups: {', '.join(security_groups)}")

    # Network interfaces
    network_interfaces = data.get("NetworkInterfaces", [])
    if network_interfaces:
        console.print()
        console.print("[bold]Network Configuration:[/bold]")
        for i, ni in enumerate(network_interfaces):
            console.print(f"  Interface {i}: Subnet {ni.get('SubnetId', 'N/A')}")

    # Block device mappings
    block_devices = data.get("BlockDeviceMappings", [])
    if block_devices:
        console.print()
        console.print("[bold]Storage:[/bold]")
        for bd in block_devices:
            ebs = bd.get("Ebs", {})
            console.print(
                f"  {bd.get('DeviceName', 'N/A')}: {ebs.get('VolumeSize', 'N/A')} GB ({ebs.get('VolumeType', 'N/A')})"
            )


@app.command("create-template")
@handle_cli_errors
def create_template(
    name: str = typer.Argument(..., help="Name for the launch template"),
    ami: str = typer.Option(..., "--ami", "-a", help="AMI ID"),
    instance_type: str = typer.Option(..., "--instance-type", "-t", help="Instance type"),
    key_name: str = typer.Option(..., "--key-name", "-k", help="SSH key pair name"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    """
    Create a new EC2 launch template.

    Creates a launch template with the specified AMI, instance type, and key pair.
    The template can then be used to launch instances with consistent configuration.

    Examples:
        remote ami create-template my-template --ami ami-123 --instance-type t3.small --key-name my-key
        remote ami create-template my-template -a ami-123 -t t3.micro -k my-key --yes
    """
    # Validate instance type
    validate_instance_type(instance_type)

    # Confirm
    if not yes:
        details = f"AMI: {ami}, Type: {instance_type}, Key: {key_name}"
        if not confirm_action("create launch template", "template", name, details=details):
            print_warning("Cancelled.")
            return

    # Create template
    with handle_aws_errors("EC2", "create_launch_template"):
        response = get_ec2_client().create_launch_template(
            LaunchTemplateName=name,
            LaunchTemplateData={
                "ImageId": ami,
                "InstanceType": instance_type,
                "KeyName": key_name,
            },
            TagSpecifications=[
                {
                    "ResourceType": "launch-template",
                    "Tags": [{"Key": "Name", "Value": name}],
                }
            ],
        )

    template_id = response["LaunchTemplate"]["LaunchTemplateId"]
    print_success(f"Created launch template '{name}' ({template_id})")
