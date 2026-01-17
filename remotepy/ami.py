import random
import string
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from remotepy.exceptions import ValidationError
from remotepy.utils import (
    get_account_id,
    get_ec2_client,
    get_instance_id,
    get_instance_name,
    get_launch_template_id,
)
from remotepy.validation import safe_get_array_item, validate_array_index

app = typer.Typer()
console = Console(force_terminal=True, width=200)


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


@app.command()
def list_launch_templates() -> dict[str, Any]:
    """
    List all available EC2 launch templates.

    Displays template ID, name, and latest version number.
    """
    launch_templates = get_ec2_client().describe_launch_templates()

    # Format table using rich
    table = Table(title="Launch Templates")
    table.add_column("Number", justify="right")
    table.add_column("LaunchTemplateId", style="green")
    table.add_column("LaunchTemplateName", style="cyan")
    table.add_column("Version", justify="right")

    for i, launch_template in enumerate(launch_templates["LaunchTemplates"], 1):
        table.add_row(
            str(i),
            launch_template["LaunchTemplateId"],
            launch_template["LaunchTemplateName"],
            str(launch_template["LatestVersionNumber"]),
        )

    console.print(table)

    return dict(launch_templates)


@app.command()
def launch(
    name: str | None = typer.Option(None, help="Name of the instance to be launched"),
    launch_template: str | None = typer.Option(None, help="Launch template name"),
    version: str = typer.Option("$Latest", help="Launch template version"),
) -> None:
    """
    Launch a new EC2 instance from a launch template.

    If no launch template is provided, lists available templates for selection.
    If no name is provided, suggests a name based on the template name.

    Examples:
        remote ami launch                                    # Interactive selection
        remote ami launch --launch-template my-template      # Use specific template
        remote ami launch --name my-server --launch-template my-template
    """

    # Variables to track launch template details
    launch_template_name: str = ""
    launch_template_id: str = ""

    # if no launch template is specified, list all the launch templates
    if not launch_template:
        typer.secho("Please specify a launch template", fg=typer.colors.RED)
        typer.secho("Available launch templates:", fg=typer.colors.YELLOW)
        launch_templates = list_launch_templates()["LaunchTemplates"]
        typer.secho("Select a launch template by number", fg=typer.colors.YELLOW)
        launch_template_number = typer.prompt("Launch template", type=str)
        # Validate user input and safely access array
        try:
            template_index = validate_array_index(
                launch_template_number, len(launch_templates), "launch templates"
            )
            selected_template = launch_templates[template_index]
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

        typer.secho(
            f"Instance {instance_id} with name '{name}' launched",
            fg=typer.colors.GREEN,
        )
    except ValidationError as e:
        typer.secho(f"Error accessing launch result: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
