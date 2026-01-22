from functools import lru_cache
from typing import TYPE_CHECKING

import boto3
import typer

from remote.utils import (
    confirm_action,
    console,
    create_table,
    extract_resource_name_from_arn,
    handle_aws_errors,
    handle_cli_errors,
    print_success,
    print_warning,
    prompt_for_selection,
    styled_column,
)
from remote.validation import sanitize_input, validate_positive_integer

if TYPE_CHECKING:
    from mypy_boto3_ecs.client import ECSClient


@lru_cache(maxsize=1)
def get_ecs_client() -> "ECSClient":
    """Get or create the ECS client.

    Uses lazy initialization and caches the client for reuse.

    Returns:
        boto3 ECS client instance
    """
    return boto3.client("ecs")


def clear_ecs_client_cache() -> None:
    """Clear the ECS client cache.

    Useful for testing or when you need to reset the client state.
    """
    get_ecs_client.cache_clear()


app = typer.Typer()


def get_all_clusters() -> list[str]:
    """Get all ECS clusters.

    Uses pagination to handle large numbers of clusters (>100).

    Returns:
        A list of all ECS clusters

    Raises:
        AWSServiceError: If AWS API call fails
    """
    with handle_aws_errors("ECS", "list_clusters"):
        paginator = get_ecs_client().get_paginator("list_clusters")
        clusters: list[str] = []

        for page in paginator.paginate():
            clusters.extend(page.get("clusterArns", []))

        return clusters


def get_all_services(cluster_name: str) -> list[str]:
    """Get all ECS services.

    Uses pagination to handle large numbers of services (>100).

    Args:
        cluster_name: The name of the cluster

    Returns:
        A list of all ECS services

    Raises:
        AWSServiceError: If AWS API call fails
    """
    with handle_aws_errors("ECS", "list_services"):
        paginator = get_ecs_client().get_paginator("list_services")
        services: list[str] = []

        for page in paginator.paginate(cluster=cluster_name):
            services.extend(page.get("serviceArns", []))

        return services


def scale_service(cluster_name: str, service_name: str, desired_count: int) -> None:
    """Scale an ECS service.

    Args:
        cluster_name: The name of the cluster
        service_name: The name of the service
        desired_count: The desired count of tasks

    Raises:
        AWSServiceError: If AWS API call fails
    """
    with handle_aws_errors("ECS", "update_service"):
        get_ecs_client().update_service(
            cluster=cluster_name, service=service_name, desiredCount=desired_count
        )


def prompt_for_cluster_name() -> str:
    """Prompt the user to select a cluster.

    Returns:
        The name of the selected cluster
    """
    clusters = get_all_clusters()

    columns = [
        styled_column("Number", "numeric", justify="right"),
        styled_column("Cluster", "name"),
        styled_column("ARN", "arn"),
    ]

    def build_row(i: int, cluster: str) -> list[str]:
        return [str(i), extract_resource_name_from_arn(cluster), cluster]

    selected = prompt_for_selection(
        items=clusters,
        item_type="cluster",
        columns=columns,
        row_builder=build_row,
        table_title="ECS Clusters",
    )
    return selected[0]


def prompt_for_services_name(cluster_name: str) -> list[str]:
    """Prompt the user to select one or more services.

    Args:
        cluster_name: The name of the cluster

    Returns:
        The names of the selected services
    """
    services = get_all_services(cluster_name)

    columns = [
        styled_column("Number", "numeric", justify="right"),
        styled_column("Service", "name"),
        styled_column("ARN", "arn"),
    ]

    def build_row(i: int, service: str) -> list[str]:
        return [str(i), extract_resource_name_from_arn(service), service]

    return prompt_for_selection(
        items=services,
        item_type="service",
        columns=columns,
        row_builder=build_row,
        table_title="ECS Services",
        allow_multiple=True,
    )


@app.command("ls-clusters")
@app.command("list-clusters")
@handle_cli_errors
def list_clusters() -> None:
    """List all ECS clusters.

    Displays cluster ARNs for all clusters in the current region.

    Examples:
        remote ecs ls-clusters      # Short form
        remote ecs list-clusters    # Verbose form
    """
    clusters = get_all_clusters()

    if not clusters:
        print_warning("No clusters found")
        return

    columns = [
        styled_column("Cluster", "name"),
        styled_column("ARN", "arn"),
    ]
    rows = [[extract_resource_name_from_arn(cluster), cluster] for cluster in clusters]
    console.print(create_table("ECS Clusters", columns, rows))


@app.command("ls-services")
@app.command("list-services")
@handle_cli_errors
def list_services(cluster_name: str | None = typer.Argument(None, help="Cluster name")) -> None:
    """List ECS services in a cluster.

    If no cluster is specified, prompts for selection.

    Examples:
        remote ecs ls-services                # List services (prompts for cluster)
        remote ecs ls-services my-cluster     # List services in specific cluster
        remote ecs list-services              # Verbose form
    """
    if not cluster_name:
        cluster_name = prompt_for_cluster_name()

    services = get_all_services(cluster_name)

    if not services:
        print_warning("No services found")
        return

    columns = [
        styled_column("Service", "name"),
        styled_column("ARN", "arn"),
    ]
    rows = [[extract_resource_name_from_arn(service), service] for service in services]
    console.print(create_table("ECS Services", columns, rows))


@app.command()
@handle_cli_errors
def scale(
    cluster_name: str | None = typer.Argument(None, help="Cluster name"),
    service_name: str | None = typer.Argument(None, help="Service name"),
    desired_count: int | None = typer.Option(None, "-n", "--count", help="Desired count of tasks"),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt (for scripting)",
    ),
) -> None:
    """Scale ECS service task count.

    If no cluster or service is specified, prompts for selection.
    Prompts for confirmation before scaling.

    Examples:
        remote ecs scale                              # Interactive mode (prompts for cluster/service)
        remote ecs scale my-cluster my-service -n 3  # Scale to 3 tasks
        remote ecs scale my-cluster my-service -n 0  # Scale down to 0 tasks
        remote ecs scale my-cluster my-service -n 5 -y  # Skip confirmation prompt
    """
    if not cluster_name:
        cluster_name = prompt_for_cluster_name()

    if not service_name:
        services = prompt_for_services_name(cluster_name)
    else:
        services = [service_name]

    if desired_count is None:
        count_str = typer.prompt("Desired count of tasks", default="1")
        # Sanitize input to handle whitespace-only values
        sanitized_count = sanitize_input(count_str) or "1"  # Fallback to default if empty
        desired_count = validate_positive_integer(sanitized_count, "desired count")
    else:
        # Validate the CLI-provided value
        desired_count = validate_positive_integer(desired_count, "desired count")

    for service in services:
        if not yes:
            if not confirm_action("scale", "service", service, details=f"to {desired_count} tasks"):
                continue

        scale_service(cluster_name, service, desired_count)
        print_success(f"Scaled {service} to {desired_count} tasks")
