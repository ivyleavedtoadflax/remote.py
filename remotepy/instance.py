import configparser
import sys

import boto3
import typer

from remotepy.config import CONFIG_PATH

cfg = configparser.ConfigParser()
cfg.read(CONFIG_PATH)
print([i for i in cfg["DEFAULT"]])
print(cfg["DEFAULT"]["instance_name"])

app = typer.Typer()

ec2_client = boto3.client("ec2")
ec2_resource = boto3.resource("ec2")


def get_instance_id(instance_name):
    instances = ec2_resource.instances.filter(
        Filters=[{"Name": "tag:Name", "Values": [instance_name]}]
    )

    for instance in instances:
        return instance.id


def get_instance_status(instance_id):
    return ec2_client.describe_instance_status(InstanceIds=[instance_id])


def get_instance_name():
    if instance_name := cfg["DEFAULT"].get("instance_name"):
        return instance_name
    else:
        print([i for i in cfg["DEFAULT"]])
        typer.secho("Instance name not found in config file", fg="red")
        typer.secho("Run `config add` to add it", fg="red")
        sys.exit(1)


@app.command()
def status():
    """
    Get the status of an instance
    """
    instance_name = get_instance_name()
    instance_id = get_instance_id(instance_name)
    typer.secho(
        f"Getting status of {instance_name} ({instance_id})", fg=typer.colors.YELLOW
    )
    status = get_instance_status(instance_id)
    typer.secho(status, fg=typer.colors.YELLOW)


@app.command()
def start():
    instance_name = get_instance_name()
    instance_id = get_instance_id(instance_name)
    status = get_instance_status(instance_id)

    if (
        status["InstanceStatuses"]
        and status["InstanceStatuses"][0]["InstanceState"]["Name"] == "running"
    ):
        typer.secho(
            f"Instance {instance_name} is already running", fg=typer.colors.YELLOW
        )

        return

    try:
        ec2_client.start_instances(InstanceIds=[instance_id])
        typer.secho(f"Instance {instance_name} started", fg=typer.colors.GREEN)
    except Exception as e:
        typer.echo(f"Error starting instance {instance_name}: {e}")


@app.command()
def stop():
    instance_name = get_instance_name()
    instance_id = get_instance_id(instance_name)
    status = get_instance_status(instance_id)

    if (
        not status["InstanceStatuses"]
        or status["InstanceStatuses"][0]["InstanceState"]["Name"] == "stopped"
    ):
        typer.secho(f"Instance {instance_name} is already stopped", fg="green")

        return

    try:
        ec2_client.stop_instances(InstanceIds=[instance_id])
        typer.secho(f"Instance {instance_name} is stopping", fg="green")
    except Exception as e:
        typer.secho(f"Error stopping instance: {e}", fg="red")


if __name__ == "__main__":
    app()
