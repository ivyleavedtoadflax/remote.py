from functools import lru_cache
from typing import TYPE_CHECKING, Any

import boto3
import typer
from botocore.exceptions import ClientError, NoCredentialsError
from rich.console import Console
from rich.table import Table

from remote.exceptions import AWSServiceError, ValidationError
from remote.validation import safe_get_array_item, validate_array_index, validate_positive_integer

if TYPE_CHECKING:
    from mypy_boto3_ecs.client import ECSClient


@lru_cache
def get_ecs_client() -> "ECSClient":
    """Get or create the ECS client.

    Uses lazy initialization and caches the client for reuse.

    Returns:
        boto3 ECS client instance
    """
    return boto3.client("ecs")


# Backwards compatibility: ecs_client is now accessed lazily via __getattr__
# to avoid creating the client at import time (which breaks tests without AWS region)


def __getattr__(name: str) -> Any:
    """Lazy module attribute access for backwards compatibility."""
    if name == "ecs_client":
        return get_ecs_client()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


app = typer.Typer()
console = Console(force_terminal=True, width=200)


def _extract_name_from_arn(arn: str) -> str:
    """Extract the resource name from an AWS ARN.

    Args:
        arn: Full AWS ARN (e.g., arn:aws:ecs:us-east-1:123456789:cluster/prod)

    Returns:
        The resource name (e.g., prod)
    """
    if "/" in arn:
        return arn.split("/")[-1]
    return arn


def get_all_clusters() -> list[str]:
    """
    Get all ECS clusters.

    Uses pagination to handle large numbers of clusters (>100).

    Returns:
        list: A list of all ECS clusters

    Raises:
        AWSServiceError: If AWS API call fails
    """
    try:
        # Use paginator to handle >100 clusters
        paginator = get_ecs_client().get_paginator("list_clusters")
        clusters: list[str] = []

        for page in paginator.paginate():
            clusters.extend(page.get("clusterArns", []))

        return clusters
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        raise AWSServiceError("ECS", "list_clusters", error_code, error_message)
    except NoCredentialsError:
        raise AWSServiceError(
            "ECS", "list_clusters", "NoCredentials", "AWS credentials not found or invalid"
        )


def get_all_services(cluster_name: str) -> list[str]:
    """
    Get all ECS services.

    Uses pagination to handle large numbers of services (>100).

    Args:
        cluster_name: The name of the cluster

    Returns:
        list: A list of all ECS services

    Raises:
        AWSServiceError: If AWS API call fails
    """
    try:
        # Use paginator to handle >100 services
        paginator = get_ecs_client().get_paginator("list_services")
        services: list[str] = []

        for page in paginator.paginate(cluster=cluster_name):
            services.extend(page.get("serviceArns", []))

        return services
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        raise AWSServiceError("ECS", "list_services", error_code, error_message)
    except NoCredentialsError:
        raise AWSServiceError(
            "ECS", "list_services", "NoCredentials", "AWS credentials not found or invalid"
        )


def scale_service(cluster_name: str, service_name: str, desired_count: int) -> None:
    """
    Scale an ECS service

    Args:
    cluster_name (str): The name of the cluster
    service_name (str): The name of the service
    desired_count (int): The desired count of tasks

    Raises:
        AWSServiceError: If AWS API call fails
    """
    try:
        get_ecs_client().update_service(
            cluster=cluster_name, service=service_name, desiredCount=desired_count
        )
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        raise AWSServiceError("ECS", "update_service", error_code, error_message)
    except NoCredentialsError:
        raise AWSServiceError(
            "ECS", "update_service", "NoCredentials", "AWS credentials not found or invalid"
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
        # Safely access the single cluster
        cluster = safe_get_array_item(clusters, 0, "clusters")
        typer.secho(f"Using cluster: {cluster}", fg=typer.colors.BLUE)
        return str(cluster)
    else:
        typer.echo("Please select a cluster from the following list:")

        # Display clusters in a Rich table
        table = Table(title="ECS Clusters")
        table.add_column("Number", justify="right")
        table.add_column("Cluster", style="cyan")
        table.add_column("ARN", style="dim")

        for i, cluster in enumerate(clusters, 1):
            cluster_name = _extract_name_from_arn(cluster)
            table.add_row(str(i), cluster_name, cluster)

        console.print(table)

        cluster_choice = typer.prompt("Enter the number of the cluster")

        # Validate user input and safely access array
        try:
            cluster_index = validate_array_index(cluster_choice, len(clusters), "clusters")
            return clusters[cluster_index]
        except ValidationError as e:
            typer.secho(f"Error: {e}", fg=typer.colors.RED)
            raise typer.Exit(1)


def prompt_for_services_name(cluster_name: str) -> list[str]:
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
        # Safely access the single service
        service = safe_get_array_item(services, 0, "services")
        typer.secho(f"Using service: {service}", fg=typer.colors.BLUE)
        return [service]
    else:
        typer.secho(
            "Please select one or more services from the following list:",
            fg=typer.colors.YELLOW,
        )

        # Display services in a Rich table
        table = Table(title="ECS Services")
        table.add_column("Number", justify="right")
        table.add_column("Service", style="cyan")
        table.add_column("ARN", style="dim")

        for i, service in enumerate(services, 1):
            service_name = _extract_name_from_arn(service)
            table.add_row(str(i), service_name, service)

        console.print(table)

        service_choices = typer.prompt("Enter the numbers of the services (comma separated)")
        # Validate user input and safely access services
        try:
            # Parse and validate each choice
            parsed_choices = []
            for choice_str in service_choices.split(","):
                choice_str = choice_str.strip()
                if not choice_str:
                    continue
                choice_num = validate_positive_integer(choice_str, "service choice")
                choice_index = validate_array_index(choice_num, len(services), "services")
                parsed_choices.append(choice_index)

            if not parsed_choices:
                typer.secho("Error: No valid service choices provided", fg=typer.colors.RED)
                raise typer.Exit(1)

            # Safely access selected services
            selected_services = []
            for choice_index in parsed_choices:
                service = safe_get_array_item(services, choice_index, "services")
                selected_services.append(service)

        except ValidationError as e:
            typer.secho(f"Error: {e}", fg=typer.colors.RED)
            raise typer.Exit(1)
        except ValueError as e:
            typer.secho(f"Error: Invalid number format - {e}", fg=typer.colors.RED)
            raise typer.Exit(1)

        return selected_services


@app.command(name="list-clusters")
def list_clusters() -> None:
    """
    List all ECS clusters.

    Displays cluster ARNs for all clusters in the current region.
    """
    clusters = get_all_clusters()

    for cluster in clusters:
        typer.secho(cluster, fg=typer.colors.BLUE)


@app.command(name="list-services")
def list_services(cluster_name: str = typer.Argument(None, help="Cluster name")) -> None:
    """
    List ECS services in a cluster.

    If no cluster is specified, prompts for selection.
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
    desired_count: int = typer.Option(None, "-n", "--count", help="Desired count of tasks"),
) -> None:
    """
    Scale ECS service task count.

    If no cluster or service is specified, prompts for selection.
    Prompts for confirmation before scaling.
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
            typer.secho(f"Scaled {service} to {desired_count} tasks", fg=typer.colors.GREEN)
