"""Instance resolution utilities that depend on both config and utils.

This module contains functions that need to access both the config manager
and AWS utility functions, which would otherwise create a circular import
between config.py and utils.py.

Functions in this module:
- get_instance_name: Get the configured default instance name
- resolve_instance: Resolve instance name to (name, id) tuple
- resolve_instance_or_exit: Same as above with CLI error handling
- launch_instance_from_template: Launch an EC2 instance from a template
"""

import random
import string

import typer
from rich.panel import Panel

from remote.config import config_manager
from remote.exceptions import (
    InstanceNotFoundError,
    MultipleInstancesFoundError,
    ValidationError,
)
from remote.utils import (
    console,
    create_table,
    get_ec2_client,
    get_instance_id,
    get_launch_template_id,
    get_launch_templates,
    handle_aws_errors,
    print_error,
    print_warning,
)
from remote.validation import (
    safe_get_array_item,
    sanitize_input,
    validate_array_index,
)


def get_instance_name() -> str:
    """Returns the name of the instance as defined in the config file.

    Returns:
        str: Instance name if found

    Raises:
        typer.Exit: If no instance name is configured
    """
    instance_name = config_manager.get_instance_name()

    if instance_name:
        return instance_name
    else:
        print_error("No default instance configured.")
        print_error("Run `remote config add` to set up your default instance.")
        raise typer.Exit(1)


def resolve_instance(instance_name: str | None = None) -> tuple[str, str]:
    """Resolve an optional instance name to both name and instance ID.

    This helper consolidates the common pattern of:
    1. Using the default instance from config if no name is provided
    2. Looking up the instance ID from the name

    Args:
        instance_name: Optional instance name. If None, uses default from config.

    Returns:
        Tuple of (instance_name, instance_id)

    Raises:
        typer.Exit: If no instance name is configured or instance not found
    """
    if not instance_name:
        instance_name = get_instance_name()
    instance_id = get_instance_id(instance_name)
    return instance_name, instance_id


def resolve_instance_or_exit(instance_name: str | None = None) -> tuple[str, str]:
    """Resolve an optional instance name to both name and instance ID, with CLI error handling.

    This is a CLI helper that wraps resolve_instance() with standardized error
    handling. It prints user-friendly error messages and exits on failure.

    Use this in CLI commands instead of:
        try:
            instance_name, instance_id = resolve_instance(instance_name)
        except (InstanceNotFoundError, MultipleInstancesFoundError) as e:
            typer.secho(f"Error: {e}", fg=typer.colors.RED)
            raise typer.Exit(1)

    Args:
        instance_name: Optional instance name. If None, uses default from config.

    Returns:
        Tuple of (instance_name, instance_id)

    Raises:
        typer.Exit(1): If instance cannot be resolved (with error message printed)
    """
    try:
        return resolve_instance(instance_name)
    except (InstanceNotFoundError, MultipleInstancesFoundError) as e:
        print_error(f"Error: {e}")
        raise typer.Exit(1) from e


def launch_instance_from_template(
    name: str | None = None,
    launch_template: str | None = None,
    version: str = "$Latest",
    yes: bool = False,
    create_sg: bool = False,
) -> None:
    """Launch a new EC2 instance from a launch template.

    This is a shared utility function used by both the instance and ami modules.
    Uses default template from config if not specified.
    If no launch template is configured, lists available templates for selection.
    If no name is provided, suggests a name based on the template name.

    Args:
        name: Name for the new instance. If None, prompts for name.
        launch_template: Launch template name. If None, uses default or interactive selection.
        version: Launch template version. Defaults to "$Latest".
        yes: If True, skip interactive prompts and require all parameters.
        create_sg: If True, create and attach a per-instance security group after launch.

    Raises:
        typer.Exit: If no templates found or user cancels selection.
        ValidationError: If user input is invalid.
        AWSServiceError: If AWS API call fails.
    """
    # Variables to track launch template details
    launch_template_name: str = ""
    launch_template_id: str = ""

    # Check for default template from config if not specified
    if not launch_template:
        default_template = config_manager.get_value("default_launch_template")
        if default_template:
            print_warning(f"Using default template: {default_template}")
            launch_template = default_template

    # if no launch template is specified, list all the launch templates
    if not launch_template:
        if yes:
            print_error("Error: --launch-template is required when using --yes")
            raise typer.Exit(1)
        print_error("Please specify a launch template")
        print_warning("Available launch templates:")
        templates = get_launch_templates()

        if not templates:
            print_error("No launch templates found")
            raise typer.Exit(1)

        # Display templates
        columns = [
            {"name": "Number", "justify": "right"},
            {"name": "LaunchTemplateId", "style": "green"},
            {"name": "LaunchTemplateName", "style": "cyan"},
            {"name": "Version", "justify": "right"},
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

        print_warning("Select a launch template by number")
        launch_template_number = typer.prompt("Launch template", type=str)
        # Sanitize and validate user input before accessing array
        sanitized_number = sanitize_input(launch_template_number)
        if not sanitized_number:
            print_error("Error: Template number cannot be empty")
            raise typer.Exit(1)
        try:
            template_index = validate_array_index(
                sanitized_number, len(templates), "launch templates"
            )
            selected_template = templates[template_index]
        except ValidationError as e:
            print_error(f"Error: {e}")
            raise typer.Exit(1)
        launch_template_name = selected_template["LaunchTemplateName"]
        launch_template_id = selected_template["LaunchTemplateId"]

        print_warning(f"Launch template {launch_template_name} selected")
        print_warning(f"Defaulting to latest version: {selected_template['LatestVersionNumber']}")
        typer.echo(f"Launching instance based on launch template {launch_template_name}")
    else:
        # launch_template was provided as a string
        launch_template_name = launch_template
        launch_template_id = get_launch_template_id(launch_template)

    # if no name is specified, ask the user for the name
    # Sanitize name input to handle whitespace-only values
    sanitized_name = sanitize_input(name)
    if not sanitized_name:
        if yes:
            print_error("Error: --name is required when using --yes")
            raise typer.Exit(1)
        random_string = "".join(random.choices(string.ascii_letters + string.digits, k=6))
        name_suggestion = launch_template_name + "-" + random_string
        name = typer.prompt(
            "Please enter a name for the instance", type=str, default=name_suggestion
        )
        # Sanitize the prompted name as well
        sanitized_name = sanitize_input(name)
        if not sanitized_name:
            print_error("Error: Instance name cannot be empty")
            raise typer.Exit(1)
    name = sanitized_name

    # Launch the instance with the specified launch template, version, and name
    with handle_aws_errors("EC2", "run_instances"):
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
            print_warning("Warning: No instance information returned from launch")
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

        # Create and attach per-instance security group if requested
        if create_sg and name:
            from remote.sg import (
                attach_security_group_to_instance,
                create_instance_security_group,
                get_instance_vpc_id,
            )
            from remote.utils import print_info, print_success

            print_info(f"Creating security group remotepy-{name}...")
            try:
                vpc_id = get_instance_vpc_id(instance_id)
                sg_id = create_instance_security_group(name, vpc_id)
                attach_security_group_to_instance(instance_id, sg_id)
                print_success(f"Created and attached security group remotepy-{name} ({sg_id})")
            except Exception as e:
                print_warning(f"Warning: Failed to create security group: {e}")

    except ValidationError as e:
        print_error(f"Error accessing launch result: {e}")
        raise typer.Exit(1)
