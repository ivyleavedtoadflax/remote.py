import random
import string
from typing import Any

import typer
from rich.panel import Panel
from rich.table import Table

from remote.config import config_manager
from remote.exceptions import AWSServiceError, ResourceNotFoundError, ValidationError
from remote.utils import (
    console,
    get_account_id,
    get_ec2_client,
    get_instance_id,
    get_instance_name,
    get_launch_template_id,
    get_launch_template_versions,
    get_launch_templates,
)
from remote.validation import safe_get_array_item, validate_array_index

app = typer.Typer()


@app.command()
def create(
    instance_name: str | None = typer.Option(None, help="Instance name"),
    name: str | None = typer.Option(None, help="AMI name"),
    description: str | None = typer.Option(None, help="Description"),
) -> None:
    """
    Create an AMI from an EC2 instance.

    Creates an Amazon Machine Image without rebooting the instance.
    Uses the default instance from config if no instance name is provided.

    Examples:
        remote ami create                                 # From default instance
        remote ami create --instance-name my-server       # From specific instance
        remote ami create --name my-ami --description "Production snapshot"
    """

    if not instance_name:
        instance_name = get_instance_name()
    instance_id = get_instance_id(instance_name)

    # Ensure required fields have values
    ami_name = name if name else f"ami-{instance_name}"
    ami_description = description if description else ""

    ami = get_ec2_client().create_image(
        InstanceId=instance_id,
        Name=ami_name,
        Description=ami_description,
        NoReboot=True,
    )

    typer.secho(f"AMI {ami['ImageId']} created", fg=typer.colors.GREEN)


@app.command("ls")
@app.command("list")
def list_amis() -> None:
    """
    List all AMIs owned by the current account.

    Displays image ID, name, state, and creation date.
    """
    account_id = get_account_id()

    amis = get_ec2_client().describe_images(
        Owners=[account_id],
    )

    # Format table using rich
    table = Table(title="Amazon Machine Images")
    table.add_column("ImageId", style="green")
    table.add_column("Name", style="cyan")
    table.add_column("State")
    table.add_column("CreationDate")

    for ami in amis["Images"]:
        state = ami["State"]
        state_style = "green" if state == "available" else "yellow"
        table.add_row(
            ami["ImageId"],
            ami["Name"],
            f"[{state_style}]{state}[/{state_style}]",
            str(ami["CreationDate"]),
        )

    console.print(table)


@app.command("list-templates")
def list_launch_templates(
    filter: str | None = typer.Option(None, "-f", "--filter", help="Filter by name"),
    details: bool = typer.Option(False, "-d", "--details", help="Show template details"),
) -> list[dict[str, Any]]:
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
        typer.secho("No launch templates found", fg=typer.colors.YELLOW)
        return []

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
                pass
    else:
        # Standard table view
        table = Table(title="Launch Templates")
        table.add_column("Number", justify="right")
        table.add_column("LaunchTemplateId", style="green")
        table.add_column("LaunchTemplateName", style="cyan")
        table.add_column("Version", justify="right")

        for i, template in enumerate(templates, 1):
            table.add_row(
                str(i),
                template["LaunchTemplateId"],
                template["LaunchTemplateName"],
                str(template["LatestVersionNumber"]),
            )

        console.print(table)

    return templates


@app.command()
def launch(
    name: str | None = typer.Option(None, help="Name of the instance to be launched"),
    launch_template: str | None = typer.Option(None, help="Launch template name"),
    version: str = typer.Option("$Latest", help="Launch template version"),
) -> None:
    """
    Launch a new EC2 instance from a launch template.

    Uses default template from config if not specified.
    If no launch template is configured, lists available templates for selection.
    If no name is provided, suggests a name based on the template name.

    Examples:
        remote ami launch                                    # Use default or interactive
        remote ami launch --launch-template my-template      # Use specific template
        remote ami launch --name my-server --launch-template my-template
    """

    # Variables to track launch template details
    launch_template_name: str = ""
    launch_template_id: str = ""

    # Check for default template from config if not specified
    if not launch_template:
        default_template = config_manager.get_value("default_launch_template")
        if default_template:
            typer.secho(f"Using default template: {default_template}", fg=typer.colors.YELLOW)
            launch_template = default_template

    # if no launch template is specified, list all the launch templates
    if not launch_template:
        typer.secho("Please specify a launch template", fg=typer.colors.RED)
        typer.secho("Available launch templates:", fg=typer.colors.YELLOW)
        templates = get_launch_templates()

        if not templates:
            typer.secho("No launch templates found", fg=typer.colors.RED)
            raise typer.Exit(1)

        # Display templates
        table = Table(title="Launch Templates")
        table.add_column("Number", justify="right")
        table.add_column("LaunchTemplateId", style="green")
        table.add_column("LaunchTemplateName", style="cyan")
        table.add_column("Version", justify="right")

        for i, template in enumerate(templates, 1):
            table.add_row(
                str(i),
                template["LaunchTemplateId"],
                template["LaunchTemplateName"],
                str(template["LatestVersionNumber"]),
            )

        console.print(table)

        typer.secho("Select a launch template by number", fg=typer.colors.YELLOW)
        launch_template_number = typer.prompt("Launch template", type=str)
        # Validate user input and safely access array
        try:
            template_index = validate_array_index(
                launch_template_number, len(templates), "launch templates"
            )
            selected_template = templates[template_index]
        except ValidationError as e:
            typer.secho(f"Error: {e}", fg=typer.colors.RED)
            raise typer.Exit(1)
        launch_template_name = str(selected_template["LaunchTemplateName"])
        launch_template_id = str(selected_template["LaunchTemplateId"])

        typer.secho(f"Launch template {launch_template_name} selected", fg=typer.colors.YELLOW)
        typer.secho(
            f"Defaulting to latest version: {selected_template['LatestVersionNumber']}",
            fg=typer.colors.YELLOW,
        )
        typer.secho(f"Launching instance based on launch template {launch_template_name}")
    else:
        # launch template name was provided, get the ID and set variables
        launch_template_name = launch_template
        launch_template_id = get_launch_template_id(launch_template)

    # if no name is specified, ask the user for the name
    if not name:
        random_string = "".join(random.choices(string.ascii_letters + string.digits, k=6))
        name_suggestion = launch_template_name + "-" + random_string
        name = typer.prompt(
            "Please enter a name for the instance", type=str, default=name_suggestion
        )

    # Launch the instance with the specified launch template, version, and name
    instance = get_ec2_client().run_instances(
        LaunchTemplate={"LaunchTemplateId": launch_template_id, "Version": version},
        MaxCount=1,
        MinCount=1,
        TagSpecifications=[
            {
                "ResourceType": "instance",
                "Tags": [
                    {"Key": "Name", "Value": name},
                ],
            },
        ],
    )

    # Safely access the launched instance ID
    try:
        instances = instance.get("Instances", [])
        if not instances:
            typer.secho(
                "Warning: No instance information returned from launch", fg=typer.colors.YELLOW
            )
            return

        launched_instance = safe_get_array_item(instances, 0, "launched instances")
        instance_id = launched_instance.get("InstanceId", "unknown")
        instance_type = launched_instance.get("InstanceType", "unknown")

        # Display launch summary as Rich panel
        summary_lines = [
            f"[cyan]Instance ID:[/cyan] {instance_id}",
            f"[cyan]Name:[/cyan]        {name}",
            f"[cyan]Template:[/cyan]    {launch_template_name}",
            f"[cyan]Type:[/cyan]        {instance_type}",
        ]
        panel = Panel(
            "\n".join(summary_lines),
            title="[green]Instance Launched[/green]",
            border_style="green",
            expand=False,
        )
        console.print(panel)
    except ValidationError as e:
        typer.secho(f"Error accessing launch result: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)


@app.command("template-versions")
def template_versions(
    template_name: str = typer.Argument(..., help="Launch template name"),
) -> None:
    """
    Show version history for a launch template.

    Displays all versions with creation date and description.

    Examples:
        remote ami template-versions my-template
    """
    try:
        versions = get_launch_template_versions(template_name)
    except ResourceNotFoundError:
        typer.secho(f"Template '{template_name}' not found", fg=typer.colors.RED)
        raise typer.Exit(1)

    if not versions:
        typer.secho("No versions found", fg=typer.colors.YELLOW)
        return

    table = Table(title=f"Versions for {template_name}")
    table.add_column("Version", justify="right")
    table.add_column("Created")
    table.add_column("Description")
    table.add_column("Default", justify="center")

    for version in versions:
        is_default = "✓" if version.get("DefaultVersion", False) else ""
        description = version.get("VersionDescription", "")
        created = str(version.get("CreateTime", "N/A"))

        table.add_row(
            str(version["VersionNumber"]),
            created,
            description,
            is_default,
        )

    console.print(table)


@app.command("template-info")
def template_info(
    template_name: str = typer.Argument(..., help="Launch template name"),
    version: str = typer.Option("$Latest", "-v", "--version", help="Template version"),
) -> None:
    """
    Show detailed information for a launch template.

    Displays instance type, AMI, key pair, security groups, and more.

    Examples:
        remote ami template-info my-template
        remote ami template-info my-template -v 2
    """
    try:
        versions = get_launch_template_versions(template_name)
    except ResourceNotFoundError:
        typer.secho(f"Template '{template_name}' not found", fg=typer.colors.RED)
        raise typer.Exit(1)

    if not versions:
        typer.secho("No versions found", fg=typer.colors.YELLOW)
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
        typer.secho(f"Version {version} not found", fg=typer.colors.RED)
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


if __name__ == "__main__":
    app()
