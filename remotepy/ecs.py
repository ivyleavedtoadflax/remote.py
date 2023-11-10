from typing import List

import boto3
import typer

ecs_client = boto3.client("ecs")

app = typer.Typer()


def get_all_clusters() -> List[str]:
    """
    Get all ECS clusters

    Returns:
    list: A list of all ECS clusters
    """
    clusters = ecs_client.list_clusters()

    return clusters["clusterArns"]


def get_all_services(cluster_name: str) -> List[str]:
    """
    Get all ECS services

    Args:
    cluster_name (str): The name of the cluster

    Returns:
    list: A list of all ECS services
    """
    services = ecs_client.list_services(cluster=cluster_name)

    return services["serviceArns"]


def scale_service(cluster_name: str, service_name: str, desired_count: int) -> None:
    """
    Scale an ECS service

    Args:
    cluster_name (str): The name of the cluster
    service_name (str): The name of the service
    desired_count (int): The desired count of tasks
    """
    ecs_client.update_service(
        cluster=cluster_name, service=service_name, desiredCount=desired_count
    )


def prompt_for_cluster_name() -> str:
    """
    Prompt the user to select a cluster

    Returns:
    str: The name of the selected cluster
    """
    clusters = get_all_clusters()

    if not clusters:
        typer.echo("No clusters found.")
        raise typer.Exit()
    elif len(clusters) == 1:
        typer.secho(f"Using cluster: {clusters[0]}", fg=typer.colors.BLUE)

        return clusters[0]
    else:
        typer.echo("Please select a cluster from the following list:")

        for i, cluster in enumerate(clusters):
            typer.secho(f"{i+1}. {cluster}", fg=typer.colors.BLUE)
        cluster_choice = typer.prompt("Enter the number of the cluster")

        return clusters[int(cluster_choice) - 1]


def prompt_for_services_name(cluster_name: str) -> List[str]:
    """
    Prompt the user to select one or more services

    Args:
    cluster_name (str): The name of the cluster

    Returns:
    List[str]: The names of the selected services
    """
    services = get_all_services(cluster_name)

    if not services:
        typer.echo("No services found.")
        raise typer.Exit()
    elif len(services) == 1:
        typer.secho(f"Using service: {services[0]}", fg=typer.colors.BLUE)

        return [services[0]]
    else:
        typer.secho(
            "Please select one or more services from the following list:",
            fg=typer.colors.YELLOW,
        )

        for i, service in enumerate(services):
            typer.secho(f"{i+1}. {service}", fg=typer.colors.BLUE)
        service_choices = typer.prompt("Enter the numbers of the services (comma separated)")
        service_choices = [int(choice.strip()) for choice in service_choices.split(",")]
        selected_services = [services[choice - 1] for choice in service_choices]

        return selected_services


@app.command(name="list-clusters")
def list_clusters() -> None:
    """
    List ECS clusters
    """
    clusters = get_all_clusters()

    for cluster in clusters:
        typer.secho(cluster, fg=typer.colors.BLUE)


@app.command(name="list-services")
def list_services(
    cluster_name: str = typer.Argument(None, help="Cluster name")
) -> None:
    """
    List ECS services

    Args:
    cluster_name (str): The name of the cluster
    """

    if not cluster_name:
        cluster_name = prompt_for_cluster_name()

    services = get_all_services(cluster_name)

    for service in services:
        typer.secho(service, fg=typer.colors.BLUE)


@app.command()
def scale(
    cluster_name: str = typer.Argument(None, help="Cluster name"),
    service_name: str = typer.Argument(None, help="Service name"),
    desired_count: int = typer.Option(
        None, "-n", "--count", help="Desired count of tasks"
    ),
) -> None:
    """
    Scale ECS services
    """

    if not cluster_name:
        cluster_name = prompt_for_cluster_name()

    if not service_name:
        services = prompt_for_services_name(cluster_name)
    else:
        services = [service_name]

    if not desired_count:
        desired_count = typer.prompt("Desired count of tasks: ", default=1, type=int)

    for service in services:
        confirm_message = f"Do you really want to scale {service} to {desired_count}?"

        if typer.confirm(confirm_message):
            scale_service(cluster_name, service, desired_count)
            typer.secho(
                f"Scaled {service} to {desired_count} tasks", fg=typer.colors.GREEN
            )
