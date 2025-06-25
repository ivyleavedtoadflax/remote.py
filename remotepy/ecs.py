import boto3
import typer
from botocore.exceptions import ClientError, NoCredentialsError

from remotepy.exceptions import AWSServiceError, ValidationError
from remotepy.validation import safe_get_array_item, validate_array_index, validate_positive_integer

ecs_client = boto3.client("ecs")

app = typer.Typer()


def get_all_clusters() -> list[str]:
    """
    Get all ECS clusters.

    Returns:
        list: A list of all ECS clusters

    Raises:
        AWSServiceError: If AWS API call fails
    """
    try:
        response = ecs_client.list_clusters()
        return response.get("clusterArns", [])
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

    Args:
        cluster_name: The name of the cluster

    Returns:
        list: A list of all ECS services

    Raises:
        AWSServiceError: If AWS API call fails
    """
    try:
        response = ecs_client.list_services(cluster=cluster_name)
        return response.get("serviceArns", [])
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
        # Safely access the single cluster
        cluster = safe_get_array_item(clusters, 0, "clusters")
        typer.secho(f"Using cluster: {cluster}", fg=typer.colors.BLUE)
        return cluster
    else:
        typer.echo("Please select a cluster from the following list:")

        for i, cluster in enumerate(clusters):
            typer.secho(f"{i + 1}. {cluster}", fg=typer.colors.BLUE)
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

        for i, service in enumerate(services):
            typer.secho(f"{i + 1}. {service}", fg=typer.colors.BLUE)
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
    List ECS clusters
    """
    clusters = get_all_clusters()

    for cluster in clusters:
        typer.secho(cluster, fg=typer.colors.BLUE)


@app.command(name="list-services")
def list_services(cluster_name: str = typer.Argument(None, help="Cluster name")) -> None:
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
    desired_count: int = typer.Option(None, "-n", "--count", help="Desired count of tasks"),
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
            typer.secho(f"Scaled {service} to {desired_count} tasks", fg=typer.colors.GREEN)
