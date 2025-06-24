"""Custom exceptions for RemotePy application.

This module defines custom exception classes for better error handling
and more informative error messages throughout the application.
"""



class RemotePyError(Exception):
    """Base exception for all RemotePy errors."""

    def __init__(self, message: str, details: str | None = None):
        self.message = message
        self.details = details
        super().__init__(self.message)

    def __str__(self):
        if self.details:
            return f"{self.message}\nDetails: {self.details}"
        return self.message


class InstanceNotFoundError(RemotePyError):
    """Raised when a requested EC2 instance cannot be found."""

    def __init__(self, instance_name: str, details: str | None = None):
        self.instance_name = instance_name
        message = f"Instance '{instance_name}' not found"
        if not details:
            details = (
                "Possible causes:\n"
                "- Instance name is incorrect\n"
                "- Instance is in a different region\n"
                "- Insufficient permissions to describe instances\n"
                "- Instance may have been terminated"
            )
        super().__init__(message, details)


class MultipleInstancesFoundError(RemotePyError):
    """Raised when multiple instances match a single instance query."""

    def __init__(self, instance_name: str, count: int, details: str | None = None):
        self.instance_name = instance_name
        self.count = count
        message = f"Multiple instances ({count}) found with name '{instance_name}'"
        if not details:
            details = "Use a more specific instance name or manage instances individually"
        super().__init__(message, details)


class InvalidInstanceStateError(RemotePyError):
    """Raised when an operation is attempted on an instance in the wrong state."""

    def __init__(self, instance_name: str, current_state: str, required_state: str, details: str | None = None):
        self.instance_name = instance_name
        self.current_state = current_state
        self.required_state = required_state
        message = f"Instance '{instance_name}' is in state '{current_state}', but '{required_state}' is required"
        super().__init__(message, details)


class InvalidInputError(RemotePyError):
    """Raised when user input is invalid or malformed."""

    def __init__(self, parameter_name: str, value: str, expected_format: str, details: str | None = None):
        self.parameter_name = parameter_name
        self.value = value
        self.expected_format = expected_format
        message = f"Invalid {parameter_name}: '{value}'. Expected format: {expected_format}"
        super().__init__(message, details)


class AWSServiceError(RemotePyError):
    """Raised when AWS service calls fail with actionable error information."""

    def __init__(self, service: str, operation: str, aws_error_code: str, message: str, details: str | None = None):
        self.service = service
        self.operation = operation
        self.aws_error_code = aws_error_code

        # Provide user-friendly error messages for common AWS errors
        user_message = self._get_user_friendly_message(aws_error_code, message)

        if not details:
            details = f"AWS {service} {operation} failed with error code: {aws_error_code}"

        super().__init__(user_message, details)

    def _get_user_friendly_message(self, error_code: str, original_message: str) -> str:
        """Convert AWS error codes to user-friendly messages."""
        error_mappings = {
            'UnauthorizedOperation': (
                "Permission denied. Your AWS credentials don't have the required permissions for this operation."
            ),
            'InvalidInstanceID.NotFound': (
                "The specified instance ID was not found. It may have been terminated or you may be looking in the wrong region."
            ),
            'InvalidInstanceID.Malformed': (
                "The instance ID format is invalid. Instance IDs should start with 'i-' followed by alphanumeric characters."
            ),
            'DryRunOperation': (
                "This was a dry run operation. No actual changes were made."
            ),
            'RequestLimitExceeded': (
                "AWS API rate limit exceeded. Please wait a moment and try again."
            ),
            'InsufficientInstanceCapacity': (
                "AWS doesn't have enough capacity for this instance type in the current availability zone."
            ),
            'InvalidParameterValue': (
                "One of the provided parameters has an invalid value."
            ),
            'InvalidUserID.NotFound': (
                "The specified user ID was not found or you don't have permission to access it."
            ),
        }

        return error_mappings.get(error_code, f"AWS Error: {original_message}")


class ConfigurationError(RemotePyError):
    """Raised when there are configuration-related errors."""

    def __init__(self, config_issue: str, details: str | None = None):
        message = f"Configuration error: {config_issue}"
        if not details:
            details = (
                "Check your configuration file at ~/.config/remote.py/config.ini\n"
                "Run 'remote config show' to view current configuration"
            )
        super().__init__(message, details)


class ResourceNotFoundError(RemotePyError):
    """Raised when a requested AWS resource (volume, snapshot, etc.) is not found."""

    def __init__(self, resource_type: str, resource_id: str, details: str | None = None):
        self.resource_type = resource_type
        self.resource_id = resource_id
        message = f"{resource_type} '{resource_id}' not found"
        super().__init__(message, details)


class ValidationError(RemotePyError):
    """Raised when input validation fails."""

    def __init__(self, validation_message: str, details: str | None = None):
        super().__init__(f"Validation error: {validation_message}", details)
