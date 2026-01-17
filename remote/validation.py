"""Input validation utilities for RemotePy application.

This module provides functions for validating user inputs and AWS resource
identifiers to prevent errors and improve security.
"""

import re
from typing import Any

from .exceptions import InvalidInputError, ValidationError


def validate_instance_id(instance_id: str) -> str:
    """Validate EC2 instance ID format.

    Args:
        instance_id: The instance ID to validate

    Returns:
        The validated instance ID

    Raises:
        InvalidInputError: If instance ID format is invalid
    """
    if not instance_id:
        raise InvalidInputError("instance_id", "", "i-xxxxxxxxx")

    # EC2 instance IDs should match pattern: i-[0-9a-f]{8,17}
    pattern = r"^i-[0-9a-f]{8,17}$"
    if not re.match(pattern, instance_id, re.IGNORECASE):
        raise InvalidInputError(
            "instance_id",
            instance_id,
            "i-xxxxxxxxx (where x is alphanumeric)",
            "Instance IDs start with 'i-' followed by 8-17 alphanumeric characters",
        )

    return instance_id


def validate_instance_name(instance_name: str) -> str:
    """Validate instance name format.

    Args:
        instance_name: The instance name to validate

    Returns:
        The validated instance name

    Raises:
        InvalidInputError: If instance name is invalid
    """
    if not instance_name:
        raise InvalidInputError("instance_name", "", "non-empty string")

    if len(instance_name) > 255:
        raise InvalidInputError(
            "instance_name",
            instance_name,
            "string with maximum 255 characters",
            f"Instance name is {len(instance_name)} characters long",
        )

    # Allow alphanumeric, hyphens, underscores, and spaces
    if not re.match(r"^[a-zA-Z0-9_\-\s]+$", instance_name):
        raise InvalidInputError(
            "instance_name",
            instance_name,
            "alphanumeric characters, hyphens, underscores, and spaces only",
            "Special characters except hyphens and underscores are not allowed",
        )

    return instance_name


def validate_volume_id(volume_id: str) -> str:
    """Validate EBS volume ID format.

    Args:
        volume_id: The volume ID to validate

    Returns:
        The validated volume ID

    Raises:
        InvalidInputError: If volume ID format is invalid
    """
    if not volume_id:
        raise InvalidInputError("volume_id", "", "vol-xxxxxxxxx")

    # Volume IDs should match pattern: vol-[0-9a-f]{8,17}
    pattern = r"^vol-[0-9a-f]{8,17}$"
    if not re.match(pattern, volume_id, re.IGNORECASE):
        raise InvalidInputError(
            "volume_id",
            volume_id,
            "vol-xxxxxxxxx (where x is alphanumeric)",
            "Volume IDs start with 'vol-' followed by 8-17 alphanumeric characters",
        )

    return volume_id


def validate_snapshot_id(snapshot_id: str) -> str:
    """Validate EBS snapshot ID format.

    Args:
        snapshot_id: The snapshot ID to validate

    Returns:
        The validated snapshot ID

    Raises:
        InvalidInputError: If snapshot ID format is invalid
    """
    if not snapshot_id:
        raise InvalidInputError("snapshot_id", "", "snap-xxxxxxxxx")

    # Snapshot IDs should match pattern: snap-[0-9a-f]{8,17}
    pattern = r"^snap-[0-9a-f]{8,17}$"
    if not re.match(pattern, snapshot_id, re.IGNORECASE):
        raise InvalidInputError(
            "snapshot_id",
            snapshot_id,
            "snap-xxxxxxxxx (where x is alphanumeric)",
            "Snapshot IDs start with 'snap-' followed by 8-17 alphanumeric characters",
        )

    return snapshot_id


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

    if int_value < 0:
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


def safe_get_array_item(array: list[Any], index: int, context: str, default: Any = None) -> Any:
    """Safely get an item from an array with bounds checking.

    Args:
        array: The array to access
        index: The index to access
        context: Description for error messages
        default: Default value if index is out of bounds

    Returns:
        The array item or default value

    Raises:
        ValidationError: If array is None or empty when default is None
    """
    if not array:
        if default is not None:
            return default
        raise ValidationError(f"No items found in {context}")

    if index < 0 or index >= len(array):
        if default is not None:
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
