import builtins
import random
import string
from collections.abc import Sequence
from typing import Any, Literal, cast

import typer
import wasabi

from remotepy.exceptions import ValidationError
from remotepy.utils import (
    get_account_id,
    get_ec2_client,
    get_instance_id,
    get_instance_name,
    get_launch_template_id,
)
from remotepy.validation import safe_get_array_item

app = typer.Typer()


@app.command()
def create(
    instance_name: str | None = typer.Option(None, help="Instance name"),
    name: str | None = typer.Option(None, help="AMI name"),
    description: str | None = typer.Option(None, help="Description"),
) -> None:
    """
    Create an Amazon Machine Image (AMI) from a specified EC2 instance.

    The function takes as input the name of an EC2 instance, the desired name for the AMI, and a description.
    It sends a request to the AWS EC2 service to create an AMI from the specified instance.
    If the AMI creation is successful, it returns the ID of the created AMI.

    Parameters:
    instance_name: str, optional
        The name of the EC2 instance from which to create the AMI.
        If not specified, the name of the current instance is used.

    name: str, optional
        The desired name for the AMI.

    description: str, optional
        A description for the AMI.

    Returns:
    None

    Example usage:
        python remotepy/instance.py create_ami --instance_name my-instance --name my-ami --description "My first AMI"

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
def list() -> None:
    """
    List all Amazon Machine Images (AMIs) owned by the current account.

    This function queries AWS EC2 to get details of all AMIs that are owned by the current AWS account.
    It formats the response data into a tabular form and displays it in the console.
    The returned table includes the following columns: ImageId, Name, State, and CreationDate.

    Example usage:
        python remotepy/instance.py list_amis
    """
    account_id = get_account_id()

    amis = get_ec2_client().describe_images(
        Owners=[account_id],
    )

    header = ["ImageId", "Name", "State", "CreationDate"]
    aligns = cast(Sequence[Literal["l", "r", "c"]], ["l", "l", "l", "l"])
    data: builtins.list[builtins.list[str]] = []

    for ami in amis["Images"]:
        data.append(
            [
                ami["ImageId"],
                ami["Name"],
                ami["State"],
                ami["CreationDate"],
            ]
        )

    # Format table using wasabi
    formatted = wasabi.table(data, header=header, divider=True, aligns=aligns)
    typer.secho(formatted, fg=typer.colors.YELLOW)


@app.command()
def list_launch_templates() -> dict[str, Any]:
    """
    List all launch templates available in the AWS EC2.

    This function queries AWS EC2 to get details of all available launch templates.
    It formats the response data into a tabular form and displays it in the console.
    The returned table includes the following columns: Number, LaunchTemplateId, LaunchTemplateName, and Version.

    Returns:
        dict: The full response from the AWS EC2 describe_launch_templates call.

    Example usage:
        python remotepy/instance.py list_launch_templates
    """
    launch_templates = get_ec2_client().describe_launch_templates()

    header = ["Number", "LaunchTemplateId", "LaunchTemplateName", "Version"]
    aligns = cast(Sequence[Literal["l", "r", "c"]], ["l"] * len(header))
    data: builtins.list[tuple[int, str, str, int]] = []

    for i, launch_template in enumerate(launch_templates["LaunchTemplates"], 1):
        data.append(
            (
                i,
                launch_template["LaunchTemplateId"],
                launch_template["LaunchTemplateName"],
                launch_template["LatestVersionNumber"],
            )
        )

    # Format table using wasabi
    formatted = wasabi.table(data, header=header, divider=True, aligns=aligns)
    typer.secho(formatted, fg=typer.colors.YELLOW)

    return dict(launch_templates)


@app.command()
def launch(
    name: str | None = typer.Option(None, help="Name of the instance to be launched"),
    launch_template: str | None = typer.Option(None, help="Launch template name"),
    version: str = typer.Option("$Latest", help="Launch template version"),
) -> None:
    """
    Launch an AWS EC2 instance based on a launch template.

    This function will launch an instance using the specified launch template and version.
    If no launch template is provided, the function will list all available launch templates and
    prompt the user to select one.

    The name of the instance can be specified with the --name option. If not provided,
    the function will prompt the user for the name and provide a suggested name based on
    the launch template name appended with a random alphanumeric string.

    Example usage:
    python remotepy/instance.py launch --launch_template my-launch-template --version 2

    Parameters:
    name: The name of the instance to be launched. This will be used as a tag for the instance.
    launch_template: The name of the launch template to use.
    version: The version of the launch template to use. Default is the latest version.
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
        selected_template = launch_templates[int(launch_template_number) - 1]
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
