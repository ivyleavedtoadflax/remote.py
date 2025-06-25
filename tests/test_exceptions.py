"""Tests for custom exception classes in remotepy.exceptions module."""

import pytest

from remotepy.exceptions import (
    RemotePyError,
    InstanceNotFoundError,
    MultipleInstancesFoundError,
    InvalidInstanceStateError,
    InvalidInputError,
    AWSServiceError,
    ResourceNotFoundError,
    ValidationError,
)


class TestRemotePyError:
    """Test the base RemotePyError exception class."""

    def test_init_with_message_only(self):
        """Should initialize with message only."""
        error = RemotePyError("Test error message")
        
        assert str(error) == "Test error message"
        assert error.message == "Test error message"
        assert error.details is None

    def test_init_with_message_and_details(self):
        """Should initialize with both message and details."""
        error = RemotePyError("Test error", "Additional details")
        
        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.details == "Additional details"

    def test_inheritance(self):
        """Should inherit from Exception."""
        error = RemotePyError("Test")
        assert isinstance(error, Exception)


class TestInstanceNotFoundError:
    """Test InstanceNotFoundError exception class."""

    def test_init_with_instance_name_only(self):
        """Should create error with default troubleshooting details."""
        error = InstanceNotFoundError("my-instance")
        
        assert "Instance 'my-instance' not found" in str(error)
        assert error.instance_name == "my-instance"
        assert "Possible causes:" in error.details
        assert "Instance name is incorrect" in error.details
        assert "different region" in error.details
        assert "Insufficient permissions" in error.details
        assert "may have been terminated" in error.details

    def test_init_with_custom_details(self):
        """Should use custom details when provided."""
        custom_details = "Custom troubleshooting info"
        error = InstanceNotFoundError("test-instance", custom_details)
        
        assert "Instance 'test-instance' not found" in str(error)
        assert error.instance_name == "test-instance"
        assert error.details == custom_details

    def test_inheritance(self):
        """Should inherit from RemotePyError."""
        error = InstanceNotFoundError("test")
        assert isinstance(error, RemotePyError)
        assert isinstance(error, Exception)


class TestMultipleInstancesFoundError:
    """Test MultipleInstancesFoundError exception class."""

    def test_init_with_count(self):
        """Should create error with instance count information."""
        error = MultipleInstancesFoundError("web-server", 3)
        
        assert "Multiple instances found for 'web-server'" in str(error)
        assert error.instance_name == "web-server"
        assert error.count == 3
        assert "Found 3 instances" in error.details
        assert "Use more specific criteria" in error.details

    def test_inheritance(self):
        """Should inherit from RemotePyError."""
        error = MultipleInstancesFoundError("test", 2)
        assert isinstance(error, RemotePyError)
        assert isinstance(error, Exception)


class TestInvalidInstanceStateError:
    """Test InvalidInstanceStateError exception class."""

    def test_init_with_states(self):
        """Should create error with state information."""
        error = InvalidInstanceStateError("my-instance", "running", "stopped")
        
        assert "Invalid state for instance 'my-instance'" in str(error)
        assert error.instance_name == "my-instance"
        assert error.current_state == "running"
        assert error.required_state == "stopped"
        assert "Currently: running" in error.details
        assert "Required: stopped" in error.details

    def test_init_with_custom_details(self):
        """Should use custom details when provided."""
        custom_details = "Custom state error info"
        error = InvalidInstanceStateError("test", "pending", "running", custom_details)
        
        assert "Invalid state for instance 'test'" in str(error)
        assert error.current_state == "pending"
        assert error.required_state == "running"
        assert error.details == custom_details

    def test_inheritance(self):
        """Should inherit from RemotePyError."""
        error = InvalidInstanceStateError("test", "state1", "state2")
        assert isinstance(error, RemotePyError)
        assert isinstance(error, Exception)


class TestInvalidInputError:
    """Test InvalidInputError exception class."""

    def test_init_with_parameters(self):
        """Should create error with input validation information."""
        error = InvalidInputError("instance_id", "invalid-id", "i-xxxxxxxxx")
        
        assert "Invalid instance_id: 'invalid-id'" in str(error)
        assert "Expected format: i-xxxxxxxxx" in str(error)
        assert error.parameter_name == "instance_id"
        assert error.value == "invalid-id"
        assert error.expected_format == "i-xxxxxxxxx"

    def test_init_with_custom_details(self):
        """Should use custom details when provided."""
        custom_details = "Custom validation error info"
        error = InvalidInputError("param", "value", "format", custom_details)
        
        assert "Invalid param: 'value'" in str(error)
        assert "Expected format: format" in str(error)
        assert error.parameter_name == "param"
        assert error.value == "value"
        assert error.expected_format == "format"
        assert error.details == custom_details

    def test_inheritance(self):
        """Should inherit from RemotePyError."""
        error = InvalidInputError("param", "value", "format")
        assert isinstance(error, RemotePyError)
        assert isinstance(error, Exception)


class TestAWSServiceError:
    """Test AWSServiceError exception class."""

    def test_init_with_aws_error_info(self):
        """Should create error with AWS service information."""
        error = AWSServiceError("EC2", "describe_instances", "UnauthorizedOperation", "Access denied")
        
        assert error.service == "EC2"
        assert error.operation == "describe_instances"
        assert error.aws_error_code == "UnauthorizedOperation"
        assert "Permission denied" in str(error)  # User-friendly message
        assert "AWS EC2 describe_instances failed" in error.details

    def test_init_with_custom_details(self):
        """Should use custom details when provided."""
        custom_details = "Custom AWS error details"
        error = AWSServiceError("S3", "get_object", "NoSuchKey", "Not found", custom_details)
        
        assert error.service == "S3"
        assert error.operation == "get_object"
        assert error.aws_error_code == "NoSuchKey"
        assert error.details == custom_details

    def test_user_friendly_error_mappings(self):
        """Should map known AWS error codes to user-friendly messages."""
        # Test various error code mappings
        test_cases = [
            ("UnauthorizedOperation", "Permission denied"),
            ("InvalidInstanceID.NotFound", "instance ID was not found"),
            ("InvalidInstanceID.Malformed", "instance ID format is invalid"),
            ("DryRunOperation", "dry run operation"),
            ("RequestLimitExceeded", "rate limit exceeded"),
            ("InsufficientInstanceCapacity", "enough capacity"),
            ("InvalidParameterValue", "invalid value"),
            ("InvalidUserID.NotFound", "user ID was not found"),
        ]
        
        for error_code, expected_text in test_cases:
            error = AWSServiceError("EC2", "test_op", error_code, "Original message")
            assert expected_text.lower() in str(error).lower()

    def test_unknown_error_code(self):
        """Should handle unknown error codes gracefully."""
        error = AWSServiceError("EC2", "test_op", "UnknownErrorCode", "Some error")
        
        # Should fall back to original message when no mapping exists
        assert "Some error" in str(error)

    def test_inheritance(self):
        """Should inherit from RemotePyError."""
        error = AWSServiceError("EC2", "test", "TestError", "Test message")
        assert isinstance(error, RemotePyError)
        assert isinstance(error, Exception)


class TestResourceNotFoundError:
    """Test ResourceNotFoundError exception class."""

    def test_init_with_resource_info(self):
        """Should create error with resource information."""
        error = ResourceNotFoundError("Volume", "vol-12345")
        
        assert "Volume 'vol-12345' not found" in str(error)
        assert error.resource_type == "Volume"
        assert error.resource_id == "vol-12345"

    def test_inheritance(self):
        """Should inherit from RemotePyError."""
        error = ResourceNotFoundError("Snapshot", "snap-12345")
        assert isinstance(error, RemotePyError)
        assert isinstance(error, Exception)


class TestValidationError:
    """Test ValidationError exception class."""

    def test_init_with_message(self):
        """Should create validation error with message."""
        error = ValidationError("Invalid array index")
        
        assert "Invalid array index" in str(error)

    def test_inheritance(self):
        """Should inherit from RemotePyError."""
        error = ValidationError("Test validation error")
        assert isinstance(error, RemotePyError)
        assert isinstance(error, Exception)