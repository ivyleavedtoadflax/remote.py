"""Input validation utilities for RemotePy application.

This module provides functions for validating user inputs and AWS resource
identifiers to prevent errors and improve security.
"""

import re
from pathlib import Path
from typing import Any

import typer

from .exceptions import InvalidInputError, ValidationError


def sanitize_input(value: str | None) -> str | None:
    """Sanitize user input by stripping whitespace and normalizing empty values.

    This function provides consistent input sanitization across the application:
    - Returns None for None input
    - Returns None for whitespace-only strings
    - Returns the stripped value otherwise

    Use this function early in input processing pipelines to ensure consistent
    handling of whitespace-only values across all commands.

    Args:
        value: The input string to sanitize, or None

    Returns:
        The stripped string if non-empty after stripping, None otherwise

    Examples:
        >>> sanitize_input(None)
        None
        >>> sanitize_input("")
        None
        >>> sanitize_input("   ")
        None
        >>> sanitize_input("  hello  ")
        "hello"
    """
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


class _Unset:
    """Sentinel class to distinguish between 'no default provided' and 'None as default'.

    This allows safe_get_array_item() to accept None as a valid default value while
    still being able to detect when no default was provided at all.
    """

    def __repr__(self) -> str:
        return "<UNSET>"


_UNSET = _Unset()


def validate_instance_type(instance_type: str) -> str:
    """Validate EC2 instance type format.

    Instance types follow the pattern: family[generation][size_modifier].size
    Examples: t3.micro, m5.large, g4dn.xlarge, r6g.medium

    Args:
        instance_type: The instance type to validate

    Returns:
        The validated instance type (stripped of leading/trailing whitespace)

    Raises:
        InvalidInputError: If instance type format is invalid
    """
    sanitized = sanitize_input(instance_type)
    if not sanitized:
        raise InvalidInputError("instance_type", "", "t3.micro or m5.large")

    # Pattern: family.size (e.g., t3.micro, m5.large, g4dn.xlarge)
    # Family: lowercase letters followed by optional numbers and modifiers (like 'dn', 'g')
    # Size: lowercase letters, numbers, and hyphens (micro, small, large, xlarge, 2xlarge, etc.)
    pattern = r"^[a-z][a-z0-9-]*\.[a-z0-9-]+$"
    if not re.match(pattern, sanitized, re.IGNORECASE):
        raise InvalidInputError(
            "instance_type",
            sanitized,
            "format like 't3.micro' or 'm5.large'",
            "Instance types consist of a family and size separated by a dot",
        )

    return sanitized


def validate_instance_id(instance_id: str) -> str:
    """Validate EC2 instance ID format.

    Args:
        instance_id: The instance ID to validate

    Returns:
        The validated instance ID (stripped of leading/trailing whitespace)

    Raises:
        InvalidInputError: If instance ID format is invalid
    """
    sanitized = sanitize_input(instance_id)
    if not sanitized:
        raise InvalidInputError("instance_id", "", "i-xxxxxxxxx")

    # EC2 instance IDs should match pattern: i-[0-9a-f]{8,17}
    pattern = r"^i-[0-9a-f]{8,17}$"
    if not re.match(pattern, sanitized, re.IGNORECASE):
        raise InvalidInputError(
            "instance_id",
            sanitized,
            "i-xxxxxxxxx (where x is alphanumeric)",
            "Instance IDs start with 'i-' followed by 8-17 alphanumeric characters",
        )

    return sanitized


# Constants for instance name validation
INSTANCE_NAME_MAX_LENGTH = 255
INSTANCE_NAME_PATTERN = r"^[a-zA-Z0-9_\-\.\s]+$"
INSTANCE_NAME_PATTERN_DESC = "alphanumeric characters, hyphens, underscores, dots, and spaces only"


def check_instance_name_pattern(instance_name: str) -> str | None:
    """Check if instance name matches the allowed pattern.

    This is the core validation logic shared between Pydantic validators
    and standalone validation functions.

    Args:
        instance_name: The instance name to check

    Returns:
        None if valid, or an error message string if invalid
    """
    if len(instance_name) > INSTANCE_NAME_MAX_LENGTH:
        return (
            f"Instance name exceeds maximum length of {INSTANCE_NAME_MAX_LENGTH} characters "
            f"(got {len(instance_name)})"
        )

    if not re.match(INSTANCE_NAME_PATTERN, instance_name):
        return (
            f"Invalid instance name '{instance_name}': "
            f"must contain only {INSTANCE_NAME_PATTERN_DESC}"
        )

    return None


def validate_instance_name(instance_name: str) -> str:
    """Validate instance name format.

    Args:
        instance_name: The instance name to validate

    Returns:
        The validated instance name (stripped of leading/trailing whitespace)

    Raises:
        InvalidInputError: If instance name is invalid
    """
    sanitized = sanitize_input(instance_name)
    if not sanitized:
        raise InvalidInputError("instance_name", "", "non-empty string")

    error = check_instance_name_pattern(sanitized)
    if error:
        raise InvalidInputError(
            "instance_name",
            sanitized,
            INSTANCE_NAME_PATTERN_DESC,
            error,
        )

    return sanitized


def validate_volume_id(volume_id: str) -> str:
    """Validate EBS volume ID format.

    Args:
        volume_id: The volume ID to validate

    Returns:
        The validated volume ID (stripped of leading/trailing whitespace)

    Raises:
        InvalidInputError: If volume ID format is invalid
    """
    sanitized = sanitize_input(volume_id)
    if not sanitized:
        raise InvalidInputError("volume_id", "", "vol-xxxxxxxxx")

    # Volume IDs should match pattern: vol-[0-9a-f]{8,17}
    pattern = r"^vol-[0-9a-f]{8,17}$"
    if not re.match(pattern, sanitized, re.IGNORECASE):
        raise InvalidInputError(
            "volume_id",
            sanitized,
            "vol-xxxxxxxxx (where x is alphanumeric)",
            "Volume IDs start with 'vol-' followed by 8-17 alphanumeric characters",
        )

    return sanitized


def validate_positive_integer(value: Any, parameter_name: str, max_value: int | None = None) -> int:
    """Validate that a value is a positive integer.

    Args:
        value: The value to validate
        parameter_name: Name of the parameter for error messages
        max_value: Optional maximum allowed value

    Returns:
        The validated integer value

    Raises:
        ValidationError: If value is not a positive integer
    """
    try:
        int_value = int(value)
    except (ValueError, TypeError):
        raise ValidationError(f"{parameter_name} must be a valid integer, got: {value}")

    if int_value <= 0:
        raise ValidationError(f"{parameter_name} must be positive, got: {int_value}")

    if max_value is not None and int_value > max_value:
        raise ValidationError(f"{parameter_name} must be <= {max_value}, got: {int_value}")

    return int_value


def validate_array_index(index: Any, array_length: int, context: str) -> int:
    """Validate that an index is valid for accessing an array.

    Args:
        index: The index to validate (usually user input)
        array_length: Length of the array to be accessed
        context: Description of what's being accessed for error messages

    Returns:
        The validated zero-based index

    Raises:
        ValidationError: If index is invalid
    """
    try:
        # Convert to int and adjust from 1-based to 0-based indexing
        zero_based_index = int(index) - 1
    except (ValueError, TypeError):
        raise ValidationError(f"Selection must be a valid number for {context}, got: {index}")

    if zero_based_index < 0:
        raise ValidationError(f"Selection must be positive for {context}, got: {index}")

    if zero_based_index >= array_length:
        raise ValidationError(
            f"Selection {index} is out of range for {context}. Valid range: 1-{array_length}"
        )

    return zero_based_index


def safe_get_nested_value(data: dict[str, Any], keys: list[str], default: Any = None) -> Any:
    """Safely retrieve a nested value from a dictionary structure.

    Args:
        data: The dictionary to search
        keys: List of keys representing the path to the desired value
        default: Default value to return if path doesn't exist

    Returns:
        The nested value or default if not found
    """
    current = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def safe_get_array_item(array: list[Any], index: int, context: str, default: Any = _UNSET) -> Any:
    """Safely get an item from an array with bounds checking.

    This function has dual behavior based on whether a default is provided:

    - **With default**: Returns the default value on any failure (empty array or
      out-of-bounds index). This makes the function "safe" in that it never raises.
    - **Without default**: Raises ValidationError on failure. Use this when the
      absence of data indicates a programming error or unexpected state.

    Args:
        array: The array to access. Can be None or empty.
        index: The zero-based index to access.
        context: Description of what's being accessed, used in error messages
            (e.g., "instance reservations", "launched instances").
        default: Optional default value to return if the array is empty or the
            index is out of bounds. Pass any value (including None) to enable
            "safe" mode that never raises. Omit entirely to enable "strict" mode
            that raises ValidationError on failure.

    Returns:
        The array item at the specified index, or the default value if provided
        and access fails.

    Raises:
        ValidationError: If array is empty or index is out of bounds AND no
            default was provided. Never raises if default is provided.

    Examples:
        Strict mode (raises on failure)::

            >>> safe_get_array_item([], 0, "items")
            ValidationError: No items found in items

            >>> safe_get_array_item(["a"], 5, "items")
            ValidationError: Index 5 out of range for items (length: 1)

        Safe mode (returns default on failure)::

            >>> safe_get_array_item([], 0, "items", default="fallback")
            "fallback"

            >>> safe_get_array_item([], 0, "items", default=None)
            None

            >>> safe_get_array_item(["a", "b"], 1, "items", default="fallback")
            "b"
    """
    if not array:
        if default is not _UNSET:
            return default
        raise ValidationError(f"No items found in {context}")

    if index < 0 or index >= len(array):
        if default is not _UNSET:
            return default
        raise ValidationError(f"Index {index} out of range for {context} (length: {len(array)})")

    return array[index]


def validate_aws_response_structure(response: Any, expected_keys: list[str], context: str) -> None:
    """Validate that an AWS API response has the expected structure.

    Args:
        response: The AWS API response to validate
        expected_keys: List of required keys
        context: Description for error messages

    Raises:
        ValidationError: If response structure is invalid
    """
    if not isinstance(response, dict):
        raise ValidationError(
            f"Invalid {context} response: expected dictionary, got {type(response)}"
        )

    for key in expected_keys:
        if key not in response:
            raise ValidationError(f"Invalid {context} response: missing required key '{key}'")


def ensure_non_empty_array(array: list[Any], context: str) -> list[Any]:
    """Ensure an array is not empty and return it.

    Args:
        array: The array to check
        context: Description for error messages

    Returns:
        The non-empty array

    Raises:
        ValidationError: If array is None or empty
    """
    if not array:
        raise ValidationError(f"No items found in {context}")

    return array


def validate_ssh_key_path(key: str | None) -> str | None:
    """Validate SSH key file path at option parse time.

    This is a Typer callback for validating the --key option. It ensures the
    SSH key file exists and is a regular file before attempting any operations.

    Args:
        key: SSH key path provided by user, or None if not specified

    Returns:
        The expanded key path as a string if valid, None if not provided

    Raises:
        typer.BadParameter: If the key file does not exist or is not a file
    """
    sanitized = sanitize_input(key)
    if sanitized is None:
        # Treat None and empty/whitespace-only strings as "not provided"
        if key is not None:
            # Original was non-None but empty/whitespace-only
            raise typer.BadParameter("SSH key path cannot be empty")
        return None

    path = Path(sanitized).expanduser()

    if not path.exists():
        raise typer.BadParameter(f"SSH key file not found: {sanitized}")

    if not path.is_file():
        raise typer.BadParameter(f"SSH key path is not a file: {sanitized}")

    return str(path)


# Username validation constants (shared with config.py Pydantic validator)
USERNAME_PATTERN = r"^[a-zA-Z0-9_\-]+$"
USERNAME_PATTERN_DESC = "alphanumeric characters, hyphens, and underscores only"
USERNAME_MAX_LENGTH = 32  # Linux username limit


def validate_ssh_username(username: str) -> str:
    """Validate SSH/SSM username at option parse time.

    This is a Typer callback for validating the --user option. It ensures the
    username contains only safe characters to prevent command injection when
    the username is used in shell commands (e.g., `sudo su - {username}`).

    Args:
        username: Username provided by user

    Returns:
        The validated username

    Raises:
        typer.BadParameter: If the username contains invalid characters
    """
    sanitized = sanitize_input(username)
    if sanitized is None:
        raise typer.BadParameter("Username cannot be empty")

    if len(sanitized) > USERNAME_MAX_LENGTH:
        raise typer.BadParameter(
            f"Username exceeds maximum length of {USERNAME_MAX_LENGTH} characters"
        )

    if not re.match(USERNAME_PATTERN, sanitized):
        raise typer.BadParameter(
            f"Invalid username '{sanitized}': must contain only {USERNAME_PATTERN_DESC}"
        )

    return sanitized
