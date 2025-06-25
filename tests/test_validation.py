"""Tests for input validation functions in remotepy.validation module."""

import pytest

from remotepy.validation import (
    validate_instance_id,
    validate_instance_name,
    validate_volume_id,
    validate_snapshot_id,
    validate_array_index,
    safe_get_nested_value,
    safe_get_array_item,
    validate_aws_response_structure,
)
from remotepy.exceptions import InvalidInputError, ValidationError


class TestValidateInstanceId:
    """Test instance ID validation function."""

    def test_valid_instance_ids(self):
        """Should accept valid instance ID formats."""
        valid_ids = [
            "i-12345678",  # 8 characters
            "i-1234567890abcdef0",  # 17 characters
            "i-abcdef1234567890",  # Mixed alphanumeric
            "i-ABCDEF1234567890",  # Uppercase (should work with case insensitive)
        ]
        
        for instance_id in valid_ids:
            result = validate_instance_id(instance_id)
            assert result == instance_id

    def test_empty_instance_id(self):
        """Should raise InvalidInputError for empty instance ID."""
        with pytest.raises(InvalidInputError) as exc_info:
            validate_instance_id("")
        
        assert exc_info.value.parameter_name == "instance_id"
        assert exc_info.value.expected_format == "i-xxxxxxxxx"

    def test_none_instance_id(self):
        """Should raise InvalidInputError for None instance ID."""
        with pytest.raises(InvalidInputError) as exc_info:
            validate_instance_id(None)
        
        assert exc_info.value.parameter_name == "instance_id"

    def test_invalid_format_no_prefix(self):
        """Should raise InvalidInputError for IDs without 'i-' prefix."""
        with pytest.raises(InvalidInputError) as exc_info:
            validate_instance_id("12345678")
        
        assert exc_info.value.parameter_name == "instance_id"
        assert exc_info.value.value == "12345678"
        assert "i-xxxxxxxxx" in exc_info.value.expected_format

    def test_invalid_format_too_short(self):
        """Should raise InvalidInputError for IDs that are too short."""
        with pytest.raises(InvalidInputError) as exc_info:
            validate_instance_id("i-1234567")  # 7 characters, need 8+
        
        assert exc_info.value.parameter_name == "instance_id"

    def test_invalid_format_too_long(self):
        """Should raise InvalidInputError for IDs that are too long."""
        with pytest.raises(InvalidInputError) as exc_info:
            validate_instance_id("i-123456789012345678")  # 18 characters, max 17
        
        assert exc_info.value.parameter_name == "instance_id"

    def test_invalid_characters(self):
        """Should raise InvalidInputError for IDs with invalid characters."""
        with pytest.raises(InvalidInputError) as exc_info:
            validate_instance_id("i-12345678@#")
        
        assert exc_info.value.parameter_name == "instance_id"


class TestValidateInstanceName:
    """Test instance name validation function."""

    def test_valid_instance_names(self):
        """Should accept valid instance name formats."""
        valid_names = [
            "web-server",
            "my_instance",
            "WebServer123",
            "test instance",  # With space
            "a",  # Single character
            "A" * 255,  # Maximum length
        ]
        
        for name in valid_names:
            result = validate_instance_name(name)
            assert result == name

    def test_empty_instance_name(self):
        """Should raise InvalidInputError for empty name."""
        with pytest.raises(InvalidInputError) as exc_info:
            validate_instance_name("")
        
        assert exc_info.value.parameter_name == "instance_name"

    def test_whitespace_only_name(self):
        """Should accept whitespace-only name (current behavior)."""
        # Note: Current implementation allows whitespace-only names
        result = validate_instance_name("   ")
        assert result == "   "

    def test_none_instance_name(self):
        """Should raise InvalidInputError for None name."""
        with pytest.raises(InvalidInputError) as exc_info:
            validate_instance_name(None)
        
        assert exc_info.value.parameter_name == "instance_name"

    def test_name_too_long(self):
        """Should raise InvalidInputError for names longer than 255 characters."""
        long_name = "A" * 256
        with pytest.raises(InvalidInputError) as exc_info:
            validate_instance_name(long_name)
        
        assert exc_info.value.parameter_name == "instance_name"
        assert "256 characters long" in exc_info.value.details

    def test_invalid_characters(self):
        """Should raise InvalidInputError for names with invalid characters."""
        invalid_names = [
            "name@domain.com",  # @ symbol
            "name$value",  # $ symbol
            "name%value",  # % symbol
            "name&value",  # & symbol
        ]
        
        for name in invalid_names:
            with pytest.raises(InvalidInputError) as exc_info:
                validate_instance_name(name)
            
            assert exc_info.value.parameter_name == "instance_name"
            assert exc_info.value.value == name


class TestValidateVolumeId:
    """Test volume ID validation function."""

    def test_valid_volume_ids(self):
        """Should accept valid volume ID formats."""
        valid_ids = [
            "vol-12345678",
            "vol-1234567890abcdef0",
            "vol-abcdef1234567890",
        ]
        
        for volume_id in valid_ids:
            result = validate_volume_id(volume_id)
            assert result == volume_id

    def test_empty_volume_id(self):
        """Should raise InvalidInputError for empty volume ID."""
        with pytest.raises(InvalidInputError) as exc_info:
            validate_volume_id("")
        
        assert exc_info.value.parameter_name == "volume_id"
        assert exc_info.value.expected_format == "vol-xxxxxxxxx"

    def test_invalid_volume_id_format(self):
        """Should raise InvalidInputError for invalid volume ID format."""
        with pytest.raises(InvalidInputError) as exc_info:
            validate_volume_id("invalid-volume-id")
        
        assert exc_info.value.parameter_name == "volume_id"


class TestValidateSnapshotId:
    """Test snapshot ID validation function."""

    def test_valid_snapshot_ids(self):
        """Should accept valid snapshot ID formats."""
        valid_ids = [
            "snap-12345678",
            "snap-1234567890abcdef0",
            "snap-abcdef1234567890",
        ]
        
        for snapshot_id in valid_ids:
            result = validate_snapshot_id(snapshot_id)
            assert result == snapshot_id

    def test_empty_snapshot_id(self):
        """Should raise InvalidInputError for empty snapshot ID."""
        with pytest.raises(InvalidInputError) as exc_info:
            validate_snapshot_id("")
        
        assert exc_info.value.parameter_name == "snapshot_id"
        assert exc_info.value.expected_format == "snap-xxxxxxxxx"

    def test_invalid_snapshot_id_format(self):
        """Should raise InvalidInputError for invalid snapshot ID format."""
        with pytest.raises(InvalidInputError) as exc_info:
            validate_snapshot_id("invalid-snapshot-id")
        
        assert exc_info.value.parameter_name == "snapshot_id"


class TestValidateArrayIndex:
    """Test array index validation function."""

    def test_valid_string_indices(self):
        """Should accept valid string indices and convert to zero-based."""
        assert validate_array_index("1", 5, "test") == 0
        assert validate_array_index("3", 5, "test") == 2
        assert validate_array_index("5", 5, "test") == 4

    def test_valid_integer_indices(self):
        """Should accept valid integer indices and convert to zero-based."""
        assert validate_array_index(1, 5, "test") == 0
        assert validate_array_index(3, 5, "test") == 2
        assert validate_array_index(5, 5, "test") == 4

    def test_zero_index(self):
        """Should raise ValidationError for zero index (1-based expected)."""
        with pytest.raises(ValidationError) as exc_info:
            validate_array_index(0, 5, "test items")
        
        assert "must be positive" in str(exc_info.value)

    def test_negative_index(self):
        """Should raise ValidationError for negative index."""
        with pytest.raises(ValidationError) as exc_info:
            validate_array_index(-1, 5, "test items")
        
        assert "must be positive" in str(exc_info.value)

    def test_index_out_of_range(self):
        """Should raise ValidationError for index out of range."""
        with pytest.raises(ValidationError) as exc_info:
            validate_array_index(6, 5, "test items")
        
        assert "out of range" in str(exc_info.value)
        assert "Valid range: 1-5" in str(exc_info.value)

    def test_invalid_string_index(self):
        """Should raise ValidationError for non-numeric string."""
        with pytest.raises(ValidationError) as exc_info:
            validate_array_index("abc", 5, "test items")
        
        assert "Selection must be a valid integer" in str(exc_info.value)

    def test_float_index(self):
        """Should raise ValidationError for float index."""
        with pytest.raises(ValidationError) as exc_info:
            validate_array_index(2.5, 5, "test items")
        
        assert "Selection must be a valid integer" in str(exc_info.value)


class TestSafeGetNestedValue:
    """Test safe nested value extraction function."""

    def test_successful_nested_access(self):
        """Should extract nested values successfully."""
        data = {
            "level1": {
                "level2": {
                    "target": "found_value"
                }
            }
        }
        
        result = safe_get_nested_value(data, ["level1", "level2", "target"], "default")
        assert result == "found_value"

    def test_missing_intermediate_key(self):
        """Should return default when intermediate key is missing."""
        data = {
            "level1": {
                "wrong_key": "value"
            }
        }
        
        result = safe_get_nested_value(data, ["level1", "level2", "target"], "default")
        assert result == "default"

    def test_missing_final_key(self):
        """Should return default when final key is missing."""
        data = {
            "level1": {
                "level2": {
                    "other_key": "value"
                }
            }
        }
        
        result = safe_get_nested_value(data, ["level1", "level2", "target"], "default")
        assert result == "default"

    def test_none_intermediate_value(self):
        """Should return default when intermediate value is None."""
        data = {
            "level1": None
        }
        
        result = safe_get_nested_value(data, ["level1", "level2"], "default")
        assert result == "default"

    def test_empty_path(self):
        """Should return the data itself for empty path."""
        data = {"key": "value"}
        
        result = safe_get_nested_value(data, [], "default")
        assert result == data

    def test_single_level_access(self):
        """Should work for single-level access."""
        data = {"key": "value"}
        
        result = safe_get_nested_value(data, ["key"], "default")
        assert result == "value"


class TestSafeGetArrayItem:
    """Test safe array item access function."""

    def test_successful_array_access(self):
        """Should access array items successfully."""
        array = ["item0", "item1", "item2"]
        
        assert safe_get_array_item(array, 0, "test items") == "item0"
        assert safe_get_array_item(array, 1, "test items") == "item1"
        assert safe_get_array_item(array, 2, "test items") == "item2"

    def test_empty_array_no_default(self):
        """Should raise ValidationError for empty array without default."""
        with pytest.raises(ValidationError) as exc_info:
            safe_get_array_item([], 0, "test items")
        
        assert "No items found in test items" in str(exc_info.value)

    def test_empty_array_with_default(self):
        """Should return default for empty array."""
        result = safe_get_array_item([], 0, "test items", "default")
        assert result == "default"

    def test_index_out_of_range_no_default(self):
        """Should raise ValidationError for out of range index without default."""
        array = ["item0", "item1"]
        
        with pytest.raises(ValidationError) as exc_info:
            safe_get_array_item(array, 5, "test items")
        
        assert "Index 5 out of range" in str(exc_info.value)
        assert "length: 2" in str(exc_info.value)

    def test_index_out_of_range_with_default(self):
        """Should return default for out of range index."""
        array = ["item0", "item1"]
        
        result = safe_get_array_item(array, 5, "test items", "default")
        assert result == "default"

    def test_negative_index_no_default(self):
        """Should raise ValidationError for negative index without default."""
        array = ["item0", "item1"]
        
        with pytest.raises(ValidationError) as exc_info:
            safe_get_array_item(array, -1, "test items")
        
        assert "Index -1 out of range" in str(exc_info.value)

    def test_negative_index_with_default(self):
        """Should return default for negative index."""
        array = ["item0", "item1"]
        
        result = safe_get_array_item(array, -1, "test items", "default")
        assert result == "default"


class TestValidateAwsResponseStructure:
    """Test AWS response structure validation function."""

    def test_valid_response_structure(self):
        """Should pass validation for correct response structure."""
        response = {
            "Instances": [],
            "NextToken": "abc123",
            "Metadata": {}
        }
        
        # Should not raise any exception
        validate_aws_response_structure(response, ["Instances", "NextToken"], "test_operation")

    def test_missing_required_key(self):
        """Should raise ValidationError for missing required key."""
        response = {
            "Instances": [],
            # Missing "NextToken"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_aws_response_structure(response, ["Instances", "NextToken"], "test_operation")
        
        assert "missing required key 'NextToken'" in str(exc_info.value)
        assert "test_operation" in str(exc_info.value)

    def test_non_dict_response(self):
        """Should raise ValidationError for non-dictionary response."""
        response = ["not", "a", "dict"]
        
        with pytest.raises(ValidationError) as exc_info:
            validate_aws_response_structure(response, ["key"], "test_operation")
        
        assert "expected dictionary" in str(exc_info.value)
        assert "test_operation" in str(exc_info.value)

    def test_none_response(self):
        """Should raise ValidationError for None response."""
        with pytest.raises(ValidationError) as exc_info:
            validate_aws_response_structure(None, ["key"], "test_operation")
        
        assert "expected dictionary" in str(exc_info.value)

    def test_empty_expected_keys(self):
        """Should pass validation when no keys are required."""
        response = {"any": "data"}
        
        # Should not raise any exception
        validate_aws_response_structure(response, [], "test_operation")

    def test_partial_missing_keys(self):
        """Should raise ValidationError for first missing key."""
        response = {
            "Key1": "present",
            # Missing "Key2" and "Key3"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_aws_response_structure(response, ["Key1", "Key2", "Key3"], "test_operation")
        
        assert "missing required key 'Key2'" in str(exc_info.value)