import re
from collections.abc import Callable
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import lru_cache, wraps
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar, cast

import boto3
import typer
from botocore.exceptions import ClientError, NoCredentialsError
from rich.console import Console
from rich.table import Table

from .exceptions import (
    AWSServiceError,
    InstanceNotFoundError,
    InvalidInputError,
    MultipleInstancesFoundError,
    ResourceNotFoundError,
    ValidationError,
)
from .settings import TABLE_COLUMN_STYLES
from .validation import (
    ensure_non_empty_array,
    safe_get_array_item,
    sanitize_input,
    validate_array_index,
    validate_aws_response_structure,
    validate_instance_id,
    validate_instance_name,
    validate_positive_integer,
    validate_volume_id,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from mypy_boto3_ec2.client import EC2Client
    from mypy_boto3_sts.client import STSClient

# Type variables for the decorator
P = ParamSpec("P")
R = TypeVar("R")

console = Console(force_terminal=True)


def print_error(message: str) -> None:
    """Print an error message in red.

    Use this for error conditions that indicate something went wrong.
    For AWS-specific errors, prefix with "AWS Error:" instead of "Error:".

    Args:
        message: The error message to display

    Examples:
        >>> print_error("Instance not found")
        Error: Instance not found

        >>> print_error("AWS Error: Access denied")
        AWS Error: Access denied
    """
    typer.secho(message, fg=typer.colors.RED)


def print_success(message: str) -> None:
    """Print a success message in green.

    Use this to confirm successful completion of operations.

    Args:
        message: The success message to display

    Examples:
        >>> print_success("Instance started")
        Instance started

        >>> print_success("Config saved to ~/.config/remote.py/config.ini")
        Config saved to ~/.config/remote.py/config.ini
    """
    typer.secho(message, fg=typer.colors.GREEN)


def print_warning(message: str) -> None:
    """Print a warning message in yellow.

    Use this for non-critical issues, cancellation notices, or informational
    warnings that don't prevent operation completion.

    Args:
        message: The warning message to display

    Examples:
        >>> print_warning("Instance is already running")
        Instance is already running

        >>> print_warning("Cancelled.")
        Cancelled.
    """
    typer.secho(message, fg=typer.colors.YELLOW)


def print_info(message: str) -> None:
    """Print an informational message in blue.

    Use this for status updates, progress information, or neutral notifications.

    Args:
        message: The informational message to display

    Examples:
        >>> print_info("Using instance: my-server")
        Using instance: my-server

        >>> print_info("Waiting for SSH to be ready...")
        Waiting for SSH to be ready...
    """
    typer.secho(message, fg=typer.colors.BLUE)


def handle_cli_errors(func: Callable[P, R]) -> Callable[P, R]:
    """Decorator to standardize CLI error handling.

    Catches common RemotePy exceptions and converts them to user-friendly
    error messages with consistent formatting, then exits with code 1.

    This decorator consolidates the repeated try-except pattern:
        try:
            # command logic
        except (InstanceNotFoundError, InvalidInputError, MultipleInstancesFoundError, ResourceNotFoundError) as e:
            print_error(f"Error: {e}")
            raise typer.Exit(1)
        except AWSServiceError as e:
            print_error(f"AWS Error: {e}")
            raise typer.Exit(1)
        except ValidationError as e:
            print_error(f"Error: {e}")
            raise typer.Exit(1)

    Use this decorator on CLI command functions:
        @app.command()
        @handle_cli_errors
        def my_command():
            # command logic - exceptions are handled automatically

    Args:
        func: The CLI command function to wrap

    Returns:
        Wrapped function with standardized error handling

    Note:
        The decorator should be placed BELOW the @app.command() decorator
        so it wraps the actual function, not the Typer command registration.
    """

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return func(*args, **kwargs)
        except (
            InstanceNotFoundError,
            InvalidInputError,
            MultipleInstancesFoundError,
            ResourceNotFoundError,
        ) as e:
            print_error(f"Error: {e}")
            raise typer.Exit(1) from e
        except AWSServiceError as e:
            print_error(f"AWS Error: {e}")
            raise typer.Exit(1) from e
        except ValidationError as e:
            print_error(f"Error: {e}")
            raise typer.Exit(1) from e

    return wrapper


def confirm_action(
    action: str,
    resource_type: str,
    resource_id: str,
    *,
    default: bool = False,
    details: str | None = None,
) -> bool:
    """Standardized confirmation prompt for destructive or important actions.

    Provides a consistent confirmation experience across all commands.
    All destructive actions should default to False for safety.

    Args:
        action: The action verb (e.g., "terminate", "stop", "create", "scale")
        resource_type: The type of resource (e.g., "instance", "AMI", "snapshot")
        resource_id: The identifier of the resource (name or ID)
        default: Default response if user just presses Enter. Should be False
            for destructive actions (terminate, stop, delete) and can be True
            for non-destructive actions (start, create).
        details: Optional additional details to include in the message
            (e.g., "from t3.micro to t3.large")

    Returns:
        True if user confirmed, False otherwise

    Examples:
        >>> confirm_action("terminate", "instance", "my-server")
        Are you sure you want to terminate instance 'my-server'? [y/N]:

        >>> confirm_action("change type of", "instance", "my-server",
        ...                details="from t3.micro to t3.large")
        Are you sure you want to change type of instance 'my-server' from t3.micro to t3.large? [y/N]:

        >>> confirm_action("start", "instance", "my-server", default=True)
        Are you sure you want to start instance 'my-server'? [Y/n]:
    """
    message = f"Are you sure you want to {action} {resource_type} '{resource_id}'"
    if details:
        message += f" {details}"
    message += "?"

    return typer.confirm(message, default=default)


def prompt_for_selection(
    items: list[str],
    item_type: str,
    columns: list[dict[str, Any]],
    row_builder: Callable[[int, str], list[str]],
    table_title: str,
    *,
    allow_multiple: bool = False,
) -> list[str]:
    """Generic prompt for selecting items from a list.

    Handles the common pattern of:
    1. Display a numbered table of items
    2. Handle empty list (error and exit)
    3. Handle single item (auto-select)
    4. Handle multiple items (prompt for user selection)
    5. Validate user input
    6. Return selected item(s)

    Args:
        items: List of items to select from
        item_type: Human-readable name for the item type (e.g., "cluster", "service")
        columns: Column definitions for create_table()
        row_builder: Function that takes (1-based index, item) and returns row data
        table_title: Title for the table
        allow_multiple: If True, allows comma-separated selection of multiple items

    Returns:
        List of selected items (single-element list if allow_multiple=False)

    Raises:
        typer.Exit: If no items found or user provides invalid input
    """
    if not items:
        print_error(f"No {item_type}s found")
        raise typer.Exit(1)

    if len(items) == 1:
        item = safe_get_array_item(items, 0, f"{item_type}s")
        print_info(f"Using {item_type}: {item}")
        return [item]

    if allow_multiple:
        prompt_text = f"Please select one or more {item_type}s from the following list:"  # nosec B608
    else:
        prompt_text = f"Please select a {item_type} from the following list:"  # nosec B608
    print_warning(prompt_text)

    rows = [row_builder(i, item) for i, item in enumerate(items, 1)]
    console.print(create_table(table_title, columns, rows))

    if allow_multiple:
        choice_input = typer.prompt(f"Enter the numbers of the {item_type}s (comma separated)")
        # Sanitize entire input first
        sanitized_input = sanitize_input(choice_input)
        if not sanitized_input:
            print_error(f"Error: {item_type} selection cannot be empty")
            raise typer.Exit(1)
        try:
            parsed_indices = []
            for choice_str in sanitized_input.split(","):
                choice_str = choice_str.strip()
                if not choice_str:
                    continue
                choice_num = validate_positive_integer(choice_str, f"{item_type} choice")
                choice_index = validate_array_index(choice_num, len(items), f"{item_type}s")
                parsed_indices.append(choice_index)

            if not parsed_indices:
                print_error(f"Error: No valid {item_type} choices provided")
                raise typer.Exit(1)

            selected = [safe_get_array_item(items, idx, f"{item_type}s") for idx in parsed_indices]
            return selected

        except ValidationError as e:
            print_error(f"Error: {e}")
            raise typer.Exit(1)
        except ValueError as e:
            print_error(f"Error: Invalid number format - {e}")
            raise typer.Exit(1)
    else:
        choice_input = typer.prompt(f"Enter the number of the {item_type}")
        # Sanitize input to handle whitespace-only values
        sanitized_choice = sanitize_input(choice_input)
        if not sanitized_choice:
            print_error(f"Error: {item_type} selection cannot be empty")
            raise typer.Exit(1)
        try:
            choice_index = validate_array_index(sanitized_choice, len(items), f"{item_type}s")
            return [items[choice_index]]
        except ValidationError as e:
            print_error(f"Error: {e}")
            raise typer.Exit(1)


@lru_cache(maxsize=1)
def get_ec2_client() -> "EC2Client":
    """Get or create the EC2 client.

    Uses lazy initialization and caches the client for reuse.

    Returns:
        boto3 EC2 client instance
    """
    return boto3.client("ec2")


@lru_cache(maxsize=1)
def get_sts_client() -> "STSClient":
    """Get or create the STS client.

    Uses lazy initialization and caches the client for reuse.

    Returns:
        boto3 STS client instance
    """
    return boto3.client("sts")


def clear_ec2_client_cache() -> None:
    """Clear the EC2 client cache.

    Useful for testing or when you need to reset the client state.
    """
    get_ec2_client.cache_clear()


def clear_sts_client_cache() -> None:
    """Clear the STS client cache.

    Useful for testing or when you need to reset the client state.
    """
    get_sts_client.cache_clear()


def clear_aws_client_caches() -> None:
    """Clear all AWS client caches in utils.py.

    Convenience function that clears both EC2 and STS client caches.
    Useful for test isolation and resetting state between tests.
    """
    clear_ec2_client_cache()
    clear_sts_client_cache()


@contextmanager
def handle_aws_errors(service: str, operation: str) -> "Generator[None, None, None]":
    """Context manager for consistent AWS error handling.

    Catches botocore ClientError and NoCredentialsError exceptions and converts
    them to AWSServiceError with consistent formatting.

    Args:
        service: AWS service name (e.g., "EC2", "STS")
        operation: AWS operation name (e.g., "describe_instances")

    Yields:
        None

    Raises:
        AWSServiceError: When a ClientError or NoCredentialsError is caught
    """
    try:
        yield
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        raise AWSServiceError(service, operation, error_code, error_message)
    except NoCredentialsError:
        raise AWSServiceError(
            service, operation, "NoCredentials", "AWS credentials not found or invalid"
        )


def get_status_style(status: str) -> str:
    """Get the rich style (color) for an AWS resource status value.

    Provides consistent color coding for AWS resource states across the CLI:
    - Green: healthy/available/active states (running, available, completed, in-use)
    - Red: stopped/failed/error states (stopped, failed, error, deleted)
    - Yellow: transitioning states (pending, stopping, shutting-down, creating, deleting)
    - White: unknown states (default)

    Args:
        status: The status/state string from AWS (case-insensitive)

    Returns:
        Rich style string (color name) for use with rich markup
    """
    status_lower = status.lower()

    # Green states - resource is healthy/available/active
    green_states = {"running", "available", "completed", "in-use", "active"}

    # Red states - resource is stopped/failed/error
    red_states = {"stopped", "failed", "error", "deleted"}

    # Yellow states - resource is transitioning
    yellow_states = {"pending", "stopping", "shutting-down", "creating", "deleting"}

    if status_lower in green_states:
        return "green"
    elif status_lower in red_states:
        return "red"
    elif status_lower in yellow_states:
        return "yellow"
    return "white"


def styled_column(
    name: str,
    column_type: str | None = None,
    *,
    justify: str = "left",
    no_wrap: bool = False,
) -> dict[str, Any]:
    """Create a column definition with consistent styling based on column type.

    This helper function ensures consistent table styling across the CLI by
    applying predefined styles from TABLE_COLUMN_STYLES based on the column type.

    Args:
        name: Column header text displayed in the table
        column_type: Semantic type of column data. Supported types:
            - "name": Resource names (instance name, cluster name) -> cyan
            - "id": AWS resource IDs (instance ID, volume ID) -> green
            - "arn": AWS ARNs -> dim
            - "numeric": Numeric values (counts, sizes, row numbers) -> yellow
            - None or other: No style applied (default for timestamps, descriptions)
        justify: Text alignment ("left", "right", "center"). Default: "left"
        no_wrap: If True, prevents text wrapping in this column. Default: False

    Returns:
        Dictionary suitable for use in create_table() columns parameter

    Examples:
        >>> columns = [
        ...     styled_column("Name", "name"),
        ...     styled_column("InstanceId", "id"),
        ...     styled_column("Count", "numeric", justify="right"),
        ...     styled_column("Description"),  # No style
        ... ]
        >>> table = create_table("Resources", columns, rows)
    """
    col: dict[str, Any] = {"name": name}

    if column_type and column_type in TABLE_COLUMN_STYLES:
        col["style"] = TABLE_COLUMN_STYLES[column_type]

    if justify != "left":
        col["justify"] = justify

    if no_wrap:
        col["no_wrap"] = True

    return col


def create_table(
    title: str,
    columns: list[dict[str, Any]],
    rows: list[list[str]],
) -> Table:
    """Build a Rich table with consistent styling.

    Provides a standardized way to create tables across all CLI commands,
    reducing code duplication and ensuring consistent formatting.

    Args:
        title: The table title displayed above the table
        columns: List of column definitions, each a dict with keys:
            - name (str, required): Column header text
            - style (str, optional): Rich style for the column (e.g., "cyan", "green")
            - justify (str, optional): Text alignment ("left", "right", "center")
            - no_wrap (bool, optional): If True, prevents text wrapping in this column
        rows: List of row data, each row is a list of strings matching column order

    Returns:
        A configured Rich Table ready to be printed with console.print()

    Examples:
        >>> columns = [
        ...     {"name": "ID", "style": "green"},
        ...     {"name": "Name", "style": "cyan"},
        ...     {"name": "Count", "justify": "right"},
        ... ]
        >>> rows = [["i-123", "my-server", "5"]]
        >>> table = create_table("Resources", columns, rows)
        >>> console.print(table)

    Note:
        Consider using styled_column() helper to create column definitions
        with consistent styling based on column type.
    """
    table = Table(title=title)
    for col in columns:
        table.add_column(
            col["name"],
            style=col.get("style"),
            justify=col.get("justify", "left"),
            no_wrap=col.get("no_wrap", False),
        )
    for row in rows:
        table.add_row(*row)
    return table


def extract_tags_dict(tags_list: list[dict[str, str]] | None) -> dict[str, str]:
    """Convert AWS Tags list format to a dictionary.

    AWS resources return tags in the format [{"Key": "k", "Value": "v"}, ...].
    This function converts that to a simple {"k": "v", ...} dictionary.

    Args:
        tags_list: AWS Tags in [{"Key": "k", "Value": "v"}, ...] format,
                   or None if no tags are present

    Returns:
        Dictionary mapping tag keys to values, e.g., {"Name": "my-instance"}
    """
    if not tags_list:
        return {}
    return {tag["Key"]: tag["Value"] for tag in tags_list}


def get_account_id() -> str:
    """Returns the caller id, this is the AWS account id not the AWS user id.

    Returns:
        The AWS account ID

    Raises:
        AWSServiceError: If AWS API call fails
    """
    with handle_aws_errors("STS", "get_caller_identity"):
        response = get_sts_client().get_caller_identity()

        # Validate response structure
        validate_aws_response_structure(response, ["Account"], "get_caller_identity")

        return response["Account"]


def get_instance_id(instance_name: str) -> str:
    """Returns the id of the instance.

    Args:
        instance_name: The name of the instance to find

    Returns:
        The instance ID

    Raises:
        InstanceNotFoundError: If no instance found with the given name
        MultipleInstancesFoundError: If multiple instances found with the same name
        AWSServiceError: If AWS API call fails
    """
    # Validate input
    instance_name = validate_instance_name(instance_name)

    with handle_aws_errors("EC2", "describe_instances"):
        response = get_ec2_client().describe_instances(
            Filters=[
                {"Name": "tag:Name", "Values": [instance_name]},
                {
                    "Name": "instance-state-name",
                    "Values": ["pending", "stopping", "stopped", "running"],
                },
            ]
        )

        # Validate response structure
        validate_aws_response_structure(response, ["Reservations"], "describe_instances")

        reservations = response["Reservations"]
        if not reservations:
            raise InstanceNotFoundError(instance_name)

        if len(reservations) > 1:
            raise MultipleInstancesFoundError(instance_name, len(reservations))

        # Safely access the instance ID
        instances = reservations[0].get("Instances", [])
        if not instances:
            raise InstanceNotFoundError(
                instance_name, "Instance reservation found but no instances in reservation"
            )

        return instances[0]["InstanceId"]


def get_instance_status(instance_id: str | None = None) -> dict[str, Any]:
    """Returns the status of the instance.

    Args:
        instance_id: Optional instance ID to get status for. If None, gets all instance statuses

    Returns:
        The instance status response from AWS

    Raises:
        AWSServiceError: If AWS API call fails
    """
    with handle_aws_errors("EC2", "describe_instance_status"):
        if instance_id:
            # Validate input if provided
            instance_id = validate_instance_id(instance_id)
            response = get_ec2_client().describe_instance_status(InstanceIds=[instance_id])
        else:
            response = get_ec2_client().describe_instance_status()
        return dict(response)


def get_instances(exclude_terminated: bool = False) -> list[dict[str, Any]]:
    """
    Get all instances, optionally excluding those in a 'terminated' state.

    Uses pagination to handle large numbers of instances (>100).

    Args:
        exclude_terminated: Whether to exclude terminated instances

    Returns:
        List of reservation dictionaries

    Raises:
        AWSServiceError: If AWS API call fails
    """
    with handle_aws_errors("EC2", "describe_instances"):
        filters: list[dict[str, Any]] = []
        if exclude_terminated:
            filters.append(
                {
                    "Name": "instance-state-name",
                    "Values": ["pending", "running", "shutting-down", "stopping", "stopped"],
                }
            )

        # Use paginator to handle >100 instances
        paginator = get_ec2_client().get_paginator("describe_instances")
        reservations: list[dict[str, Any]] = []

        if filters:
            page_iterator = paginator.paginate(Filters=filters)  # type: ignore[arg-type]
        else:
            page_iterator = paginator.paginate()

        for page in page_iterator:
            reservations.extend(cast(list[dict[str, Any]], page.get("Reservations", [])))

        return reservations


def get_instance_dns(instance_id: str) -> str:
    """Returns the public DNS name of the instance.

    Args:
        instance_id: The instance ID to get DNS for

    Returns:
        The public DNS name of the instance

    Raises:
        ResourceNotFoundError: If instance not found
        AWSServiceError: If AWS API call fails
    """
    # Validate input
    instance_id = validate_instance_id(instance_id)

    try:
        with handle_aws_errors("EC2", "describe_instances"):
            response = get_ec2_client().describe_instances(InstanceIds=[instance_id])

            # Validate response structure
            validate_aws_response_structure(response, ["Reservations"], "describe_instances")

            reservations = ensure_non_empty_array(
                list(response["Reservations"]), "instance reservations"
            )
            instances = ensure_non_empty_array(
                list(reservations[0].get("Instances", [])), "instances"
            )

            return str(instances[0].get("PublicDnsName", ""))
    except AWSServiceError as e:
        if e.aws_error_code == "InvalidInstanceID.NotFound":
            raise ResourceNotFoundError("Instance", instance_id)
        raise


def get_instance_info(
    instances: list[dict[str, Any]], name_filter: str | None = None
) -> tuple[list[str], list[str], list[str], list[str], list[str | None]]:
    """
    Get all instance names for the given account from aws cli.

    Args:
        instances: List of instances returned by get_instances()
        name_filter: Filter to apply to the instance names. If not found in the
            instance name, it will be excluded from the list.

    Returns:
        Tuple of (names, public_dnss, statuses, instance_types, launch_times)

    Note:
        Instances without a Name tag are automatically excluded.

    Raises:
        ValidationError: If instances data is malformed
    """
    names = []
    public_dnss = []
    statuses = []
    instance_types = []
    launch_times = []

    for reservation in instances:
        # Safely access Instances array
        reservation_instances = reservation.get("Instances", [])

        for instance in reservation_instances:
            try:
                # Check whether there is a Name tag
                tags = extract_tags_dict(instance.get("Tags"))

                if not tags or "Name" not in tags:
                    # Skip instances without a Name tag and continue to next instance
                    continue

                instance_name = tags["Name"]

                # Apply name filter if provided
                if name_filter and name_filter not in instance_name:
                    continue

                names.append(instance_name)
                public_dnss.append(instance.get("PublicDnsName", ""))

                # Safely access state information
                state_info = instance.get("State", {})
                status = state_info.get("Name", "unknown")
                statuses.append(status)

                # Handle launch time for running instances
                if status == "running" and "LaunchTime" in instance:
                    try:
                        launch_time = instance["LaunchTime"].timestamp()
                        launch_time = datetime.fromtimestamp(launch_time, tz=timezone.utc)
                        launch_time = launch_time.strftime("%Y-%m-%d %H:%M:%S UTC")
                    except (AttributeError, ValueError):
                        launch_time = None
                else:
                    launch_time = None

                launch_times.append(launch_time)
                instance_types.append(instance.get("InstanceType", "unknown"))

            except (KeyError, TypeError) as e:
                # Skip malformed instance data but continue processing others
                print_warning(f"Warning: Skipping malformed instance data: {e}")
                continue

    return names, public_dnss, statuses, instance_types, launch_times


def get_instance_ids(instances: list[dict[str, Any]]) -> list[str]:
    """Returns a list of instance ids extracted from the output of get_instances().

    Only includes instances that have a Name tag, to match the filtering behavior
    of get_instance_info().

    Args:
        instances: List of reservation dictionaries from describe_instances()

    Returns:
        List of instance IDs (only for instances with Name tags)
    """
    instance_ids = []

    for reservation in instances:
        instances_list = reservation.get("Instances", [])

        for instance in instances_list:
            # Only include instances with a Name tag (matches get_instance_info filtering)
            tags = extract_tags_dict(instance.get("Tags"))
            if tags and "Name" in tags:
                instance_ids.append(instance["InstanceId"])

    return instance_ids


def is_instance_running(instance_id: str) -> bool:
    """Returns True if the instance is running, False otherwise.

    Args:
        instance_id: The instance ID to check

    Returns:
        True if running, False if not running

    Raises:
        AWSServiceError: If AWS API call fails or response has unexpected structure
        ResourceNotFoundError: If instance is not found
        ValidationError: If instance ID is invalid
    """
    # Validate input
    instance_id = validate_instance_id(instance_id)

    try:
        status = get_instance_status(instance_id)

        # Handle case where InstanceStatuses is empty (instance not running)
        instance_statuses = status.get("InstanceStatuses", [])
        if not instance_statuses:
            return False

        # Safely access the state information
        first_status = safe_get_array_item(instance_statuses, 0, "instance statuses")
        instance_state = first_status.get("InstanceState", {})
        state_name = instance_state.get("Name", "unknown")

        return bool(state_name == "running")

    except (AWSServiceError, ResourceNotFoundError, ValidationError):
        # Re-raise specific errors
        raise
    except (KeyError, TypeError, AttributeError) as e:
        # For data structure errors, raise an AWSServiceError
        raise AWSServiceError(
            service="EC2",
            operation="describe_instance_status",
            aws_error_code="UnexpectedResponse",
            message=f"Unexpected instance status structure: {e}",
            details="The AWS API response had an unexpected format. This may indicate an API change or a transient error.",
        ) from e


def get_instance_type(instance_id: str) -> str:
    """Returns the instance type of the instance.

    Args:
        instance_id: The instance ID to get type for

    Returns:
        The instance type (e.g., 't2.micro')

    Raises:
        ResourceNotFoundError: If instance not found
        AWSServiceError: If AWS API call fails
    """
    # Validate input
    instance_id = validate_instance_id(instance_id)

    try:
        with handle_aws_errors("EC2", "describe_instances"):
            response = get_ec2_client().describe_instances(InstanceIds=[instance_id])

            # Validate response structure
            validate_aws_response_structure(response, ["Reservations"], "describe_instances")

            reservations = ensure_non_empty_array(
                list(response["Reservations"]), "instance reservations"
            )
            instances = ensure_non_empty_array(
                list(reservations[0].get("Instances", [])), "instances"
            )

            return str(instances[0]["InstanceType"])
    except AWSServiceError as e:
        if e.aws_error_code == "InvalidInstanceID.NotFound":
            raise ResourceNotFoundError("Instance", instance_id)
        raise


def get_volume_ids(instance_id: str) -> list[str]:
    """Returns a list of volume ids attached to the instance.

    Args:
        instance_id: The instance ID to get volumes for

    Returns:
        List of volume IDs attached to the instance

    Raises:
        AWSServiceError: If AWS API call fails
    """
    # Validate input
    instance_id = validate_instance_id(instance_id)

    with handle_aws_errors("EC2", "describe_volumes"):
        response = get_ec2_client().describe_volumes(
            Filters=[{"Name": "attachment.instance-id", "Values": [instance_id]}]
        )

        # Validate response structure
        validate_aws_response_structure(response, ["Volumes"], "describe_volumes")

        # Safely extract volume IDs
        volume_ids = []
        for volume in response["Volumes"]:
            if "VolumeId" in volume:
                volume_ids.append(volume["VolumeId"])

        return volume_ids


def get_volume_name(volume_id: str) -> str:
    """Returns the name of the volume.

    Args:
        volume_id: The volume ID to get name for

    Returns:
        The volume name from tags, or empty string if no name tag

    Raises:
        ResourceNotFoundError: If volume not found
        AWSServiceError: If AWS API call fails
    """
    # Validate input
    volume_id = validate_volume_id(volume_id)

    try:
        with handle_aws_errors("EC2", "describe_volumes"):
            response = get_ec2_client().describe_volumes(VolumeIds=[volume_id])

            # Validate response structure
            validate_aws_response_structure(response, ["Volumes"], "describe_volumes")

            volumes = ensure_non_empty_array(list(response["Volumes"]), "volumes")
            volume = volumes[0]

            # Look for Name tag
            for tag in volume.get("Tags", []):
                if tag["Key"] == "Name":
                    return str(tag["Value"])

            return ""  # No name tag found
    except AWSServiceError as e:
        if e.aws_error_code == "InvalidVolumeID.NotFound":
            raise ResourceNotFoundError("Volume", volume_id)
        raise


def get_launch_templates(name_filter: str | None = None) -> list[dict[str, Any]]:
    """Get launch templates, optionally filtered by name pattern.

    Args:
        name_filter: Optional string to filter templates by name (case-insensitive)

    Returns:
        List of launch template dictionaries

    Raises:
        AWSServiceError: If AWS API call fails
    """
    with handle_aws_errors("EC2", "describe_launch_templates"):
        response = get_ec2_client().describe_launch_templates()
        validate_aws_response_structure(response, ["LaunchTemplates"], "describe_launch_templates")

        templates = response["LaunchTemplates"]

        if name_filter:
            templates = [
                t for t in templates if name_filter.lower() in t["LaunchTemplateName"].lower()
            ]

        return cast(list[dict[str, Any]], templates)


def get_launch_template_versions(template_name: str) -> list[dict[str, Any]]:
    """Get all versions of a launch template.

    Args:
        template_name: Name of the launch template

    Returns:
        List of launch template version dictionaries

    Raises:
        ResourceNotFoundError: If template not found
        AWSServiceError: If AWS API call fails
    """
    try:
        with handle_aws_errors("EC2", "describe_launch_template_versions"):
            response = get_ec2_client().describe_launch_template_versions(
                LaunchTemplateName=template_name
            )
            validate_aws_response_structure(
                response, ["LaunchTemplateVersions"], "describe_launch_template_versions"
            )
            return cast(list[dict[str, Any]], response["LaunchTemplateVersions"])
    except AWSServiceError as e:
        if e.aws_error_code == "InvalidLaunchTemplateName.NotFoundException":
            raise ResourceNotFoundError("Launch Template", template_name)
        raise


def get_launch_template_id(launch_template_name: str) -> str:
    """Get the launch template ID corresponding to a given launch template name.

    This function queries AWS EC2 to get details of all launch templates with the specified name.
    It then retrieves and returns the ID of the first matching launch template.

    Args:
        launch_template_name: The name of the launch template

    Returns:
        The ID of the launch template

    Raises:
        ResourceNotFoundError: If no launch template found with the given name
        AWSServiceError: If AWS API call fails

    Example usage:
        template_id = get_launch_template_id("my-template-name")
    """
    # Validate input - sanitize and check for empty/whitespace-only
    sanitized_name = sanitize_input(launch_template_name)
    if not sanitized_name:
        raise ValidationError("Launch template name cannot be empty")

    with handle_aws_errors("EC2", "describe_launch_templates"):
        response = get_ec2_client().describe_launch_templates(
            Filters=[{"Name": "tag:Name", "Values": [sanitized_name]}]
        )

        # Validate response structure
        validate_aws_response_structure(response, ["LaunchTemplates"], "describe_launch_templates")

        launch_templates = response["LaunchTemplates"]
        if not launch_templates:
            raise ResourceNotFoundError("Launch Template", sanitized_name)

        return launch_templates[0]["LaunchTemplateId"]


def parse_duration_to_minutes(duration_str: str) -> int:
    """Parse duration string like '3h', '30m', '1h30m' into minutes.

    Args:
        duration_str: A duration string in format like '3h', '30m', '1h30m', '2h15m'

    Returns:
        Total duration in minutes

    Raises:
        ValidationError: If the duration format is invalid or results in 0 minutes
    """
    # Sanitize input - check for empty/whitespace-only
    sanitized = sanitize_input(duration_str)
    if not sanitized:
        raise ValidationError("Duration cannot be empty")

    sanitized = sanitized.lower()

    # Pattern matches: optional hours (Nh) followed by optional minutes (Nm)
    pattern = r"^(?:(\d+)h)?(?:(\d+)m)?$"
    match = re.fullmatch(pattern, sanitized)

    if not match or not any(match.groups()):
        raise ValidationError(
            f"Invalid duration format: '{sanitized}'. Use formats like '3h', '30m', or '1h30m'"
        )

    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)

    total_minutes = hours * 60 + minutes

    if total_minutes <= 0:
        raise ValidationError("Duration must be greater than 0 minutes")

    return total_minutes


def extract_resource_name_from_arn(arn: str) -> str:
    """Extract the resource name from an AWS ARN.

    Handles both forward-slash and colon-delimited ARN formats.
    ARN format: arn:partition:service:region:account-id:resource-type/resource-id
    Or: arn:partition:service:region:account-id:resource-type:resource-id

    Args:
        arn: Full AWS ARN (e.g., arn:aws:ecs:us-east-1:123456789:cluster/prod)

    Returns:
        The resource name (e.g., prod)
    """
    if "/" in arn:
        return arn.split("/")[-1]
    # Some ARNs use : for the resource portion
    parts = arn.split(":")
    if len(parts) >= 6:
        return parts[-1]
    return arn


def format_duration(
    minutes: int | None = None,
    *,
    seconds: float | None = None,
) -> str:
    """Format a duration into a human-readable string.

    Accepts either minutes or seconds (via keyword argument).
    If both are provided, seconds takes precedence.

    Args:
        minutes: Total duration in minutes (positional or keyword)
        seconds: Total duration in seconds (keyword only)

    Returns:
        Human-readable string like '2h 30m', '45m', or '3d 5h 30m'.
        Returns '-' if input is None, '0m' if duration is 0 or negative.
    """
    # Handle seconds input
    if seconds is not None:
        if seconds < 0:
            return "-"
        total_minutes = int(seconds // 60)
    elif minutes is not None:
        if minutes <= 0:
            return "0m"
        total_minutes = minutes
    else:
        return "-"

    if total_minutes <= 0:
        return "0m"

    days = total_minutes // (24 * 60)
    remaining = total_minutes % (24 * 60)
    hours = remaining // 60
    mins = remaining % 60

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if mins > 0 or not parts:
        parts.append(f"{mins}m")

    return " ".join(parts)
