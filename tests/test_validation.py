"""Tests for input validation functions in remote.validation module."""

import pytest
import typer
from hypothesis import given
from hypothesis import strategies as st

from remote.exceptions import InvalidInputError, ValidationError
from remote.validation import (
    safe_get_array_item,
    safe_get_nested_value,
    sanitize_input,
    validate_array_index,
    validate_aws_response_structure,
    validate_instance_id,
    validate_instance_name,
    validate_instance_type,
    validate_positive_integer,
    validate_ssh_key_path,
    validate_volume_id,
)


class TestSanitizeInput:
    """Test the sanitize_input utility function."""

    def test_none_input(self):
        """Should return None for None input."""
        assert sanitize_input(None) is None

    def test_empty_string(self):
        """Should return None for empty string."""
        assert sanitize_input("") is None

    def test_whitespace_only(self):
        """Should return None for whitespace-only strings."""
        assert sanitize_input("   ") is None
        assert sanitize_input("\t") is None
        assert sanitize_input("\n") is None
        assert sanitize_input("  \t\n  ") is None

    def test_valid_string(self):
        """Should return stripped string for valid input."""
        assert sanitize_input("hello") == "hello"
        assert sanitize_input("  hello  ") == "hello"
        assert sanitize_input("\thello\n") == "hello"

    def test_preserves_internal_whitespace(self):
        """Should preserve internal whitespace while stripping edges."""
        assert sanitize_input("  hello world  ") == "hello world"
        assert sanitize_input("hello\tworld") == "hello\tworld"


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

    def test_whitespace_only_instance_id(self):
        """Should raise InvalidInputError for whitespace-only instance ID."""
        with pytest.raises(InvalidInputError) as exc_info:
            validate_instance_id("   ")

        assert exc_info.value.parameter_name == "instance_id"

    def test_strips_whitespace_from_valid_id(self):
        """Should strip leading/trailing whitespace from valid instance ID."""
        result = validate_instance_id("  i-12345678  ")
        assert result == "i-12345678"

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

    @given(st.text(alphabet="0123456789abcdef", min_size=8, max_size=17))
    def test_should_accept_valid_instance_id_formats(self, suffix: str):
        """Property-based test: valid instance ID format should be accepted."""
        instance_id = f"i-{suffix}"
        result = validate_instance_id(instance_id)
        assert result == instance_id

    @given(st.text().filter(lambda x: not x.startswith("i-") and len(x) > 0))
    def test_should_reject_instance_ids_without_prefix(self, invalid_id: str):
        """Property-based test: any non-empty string not starting with 'i-' should be invalid."""
        with pytest.raises(InvalidInputError):
            validate_instance_id(invalid_id)


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
        """Should reject whitespace-only names."""
        with pytest.raises(InvalidInputError) as exc_info:
            validate_instance_name("   ")

        assert exc_info.value.parameter_name == "instance_name"

    def test_none_instance_name(self):
        """Should raise InvalidInputError for None name."""
        with pytest.raises(InvalidInputError) as exc_info:
            validate_instance_name(None)

        assert exc_info.value.parameter_name == "instance_name"

    def test_strips_whitespace_from_valid_name(self):
        """Should strip leading/trailing whitespace from valid instance name."""
        result = validate_instance_name("  my-instance  ")
        assert result == "my-instance"

    def test_name_too_long(self):
        """Should raise InvalidInputError for names longer than 255 characters."""
        long_name = "A" * 256
        with pytest.raises(InvalidInputError) as exc_info:
            validate_instance_name(long_name)

        assert exc_info.value.parameter_name == "instance_name"
        assert "255" in exc_info.value.details  # Maximum length
        assert "256" in exc_info.value.details  # Actual length

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


class TestValidateInstanceType:
    """Test instance type validation function."""

    def test_valid_instance_types(self):
        """Should accept valid instance type formats."""
        valid_types = [
            "t3.micro",
            "t3.small",
            "t3.medium",
            "t3.large",
            "t3.xlarge",
            "t3.2xlarge",
            "m5.large",
            "m5.xlarge",
            "m5.2xlarge",
            "m5.4xlarge",
            "r6g.medium",
            "c5.large",
            "g4dn.xlarge",
            "p3.2xlarge",
            "x1e.xlarge",
            "i3en.large",
            "z1d.large",
            "inf1.xlarge",
            "trn1.2xlarge",
        ]

        for instance_type in valid_types:
            result = validate_instance_type(instance_type)
            assert result == instance_type

    def test_empty_instance_type(self):
        """Should raise InvalidInputError for empty instance type."""
        with pytest.raises(InvalidInputError) as exc_info:
            validate_instance_type("")

        assert exc_info.value.parameter_name == "instance_type"
        assert "t3.micro" in exc_info.value.expected_format

    def test_none_instance_type(self):
        """Should raise InvalidInputError for None instance type."""
        with pytest.raises(InvalidInputError) as exc_info:
            validate_instance_type(None)

        assert exc_info.value.parameter_name == "instance_type"

    def test_whitespace_only_instance_type(self):
        """Should raise InvalidInputError for whitespace-only instance type."""
        with pytest.raises(InvalidInputError) as exc_info:
            validate_instance_type("   ")

        assert exc_info.value.parameter_name == "instance_type"

    def test_strips_whitespace_from_valid_input(self):
        """Should strip leading/trailing whitespace from valid instance type."""
        result = validate_instance_type("  t3.micro  ")
        assert result == "t3.micro"

    def test_invalid_format_no_dot(self):
        """Should raise InvalidInputError for instance type without dot separator."""
        with pytest.raises(InvalidInputError) as exc_info:
            validate_instance_type("t3micro")

        assert exc_info.value.parameter_name == "instance_type"
        assert exc_info.value.value == "t3micro"
        assert "t3.micro" in exc_info.value.expected_format

    def test_invalid_format_only_family(self):
        """Should raise InvalidInputError for instance type with only family."""
        with pytest.raises(InvalidInputError) as exc_info:
            validate_instance_type("t3.")

        assert exc_info.value.parameter_name == "instance_type"

    def test_invalid_format_only_size(self):
        """Should raise InvalidInputError for instance type with only size."""
        with pytest.raises(InvalidInputError) as exc_info:
            validate_instance_type(".micro")

        assert exc_info.value.parameter_name == "instance_type"

    def test_invalid_format_special_characters(self):
        """Should raise InvalidInputError for instance types with invalid special chars."""
        invalid_types = [
            "t3@.micro",
            "t3$.micro",
            "t3.micro!",
            "t3.micro#",
        ]

        for instance_type in invalid_types:
            with pytest.raises(InvalidInputError) as exc_info:
                validate_instance_type(instance_type)

            assert exc_info.value.parameter_name == "instance_type"

    def test_invalid_format_spaces(self):
        """Should raise InvalidInputError for instance types with spaces."""
        with pytest.raises(InvalidInputError) as exc_info:
            validate_instance_type("t3 .micro")

        assert exc_info.value.parameter_name == "instance_type"

    def test_case_insensitive(self):
        """Should accept uppercase instance types."""
        result = validate_instance_type("T3.MICRO")
        assert result == "T3.MICRO"

    @given(
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-", min_size=1, max_size=10).filter(
            lambda x: x and x[0].isalpha()
        ),
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-", min_size=1, max_size=10),
    )
    def test_should_accept_valid_instance_type_formats(self, family: str, size: str):
        """Property-based test: valid instance type format should be accepted."""
        instance_type = f"{family}.{size}"
        result = validate_instance_type(instance_type)
        assert result == instance_type


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

    def test_whitespace_only_volume_id(self):
        """Should raise InvalidInputError for whitespace-only volume ID."""
        with pytest.raises(InvalidInputError) as exc_info:
            validate_volume_id("   ")

        assert exc_info.value.parameter_name == "volume_id"

    def test_strips_whitespace_from_valid_id(self):
        """Should strip leading/trailing whitespace from valid volume ID."""
        result = validate_volume_id("  vol-12345678  ")
        assert result == "vol-12345678"


class TestValidatePositiveInteger:
    """Test positive integer validation function."""

    def test_valid_positive_integers(self):
        """Should accept valid positive integers."""
        assert validate_positive_integer(1, "test") == 1
        assert validate_positive_integer(42, "test") == 42
        assert validate_positive_integer(100, "test") == 100

    def test_valid_string_positive_integers(self):
        """Should accept valid positive integer strings."""
        assert validate_positive_integer("1", "test") == 1
        assert validate_positive_integer("42", "test") == 42
        assert validate_positive_integer("100", "test") == 100

    def test_zero_rejected(self):
        """Should reject zero as it is not positive."""
        with pytest.raises(ValidationError) as exc_info:
            validate_positive_integer(0, "test value")

        assert "must be positive" in str(exc_info.value)
        assert "got: 0" in str(exc_info.value)

    def test_zero_string_rejected(self):
        """Should reject zero string as it is not positive."""
        with pytest.raises(ValidationError) as exc_info:
            validate_positive_integer("0", "test value")

        assert "must be positive" in str(exc_info.value)

    def test_negative_integers_rejected(self):
        """Should reject negative integers."""
        with pytest.raises(ValidationError) as exc_info:
            validate_positive_integer(-1, "test value")

        assert "must be positive" in str(exc_info.value)
        assert "got: -1" in str(exc_info.value)

    def test_negative_string_rejected(self):
        """Should reject negative integer strings."""
        with pytest.raises(ValidationError) as exc_info:
            validate_positive_integer("-5", "test value")

        assert "must be positive" in str(exc_info.value)

    def test_invalid_string_rejected(self):
        """Should reject non-numeric strings."""
        with pytest.raises(ValidationError) as exc_info:
            validate_positive_integer("abc", "test value")

        assert "must be a valid integer" in str(exc_info.value)
        assert "got: abc" in str(exc_info.value)

    def test_max_value_constraint(self):
        """Should respect max_value constraint."""
        assert validate_positive_integer(5, "test", max_value=10) == 5

        with pytest.raises(ValidationError) as exc_info:
            validate_positive_integer(15, "test", max_value=10)

        assert "must be <= 10" in str(exc_info.value)
        assert "got: 15" in str(exc_info.value)

    @given(st.integers(min_value=1, max_value=10000))
    def test_should_accept_all_positive_integers(self, value: int):
        """Property-based test: all positive integers should be accepted."""
        result = validate_positive_integer(value, "test")
        assert result == value

    @given(st.integers(max_value=0))
    def test_should_reject_non_positive_integers(self, value: int):
        """Property-based test: all non-positive integers should be rejected."""
        with pytest.raises(ValidationError):
            validate_positive_integer(value, "test")


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

        assert "Selection must be a valid number for test items, got: abc" in str(exc_info.value)

    def test_float_index(self):
        """Should accept float index and convert to integer."""
        # Python int() truncates floats, so 2.5 becomes 2, then adjusted to 1-based gives index 1
        result = validate_array_index(2.5, 5, "test items")
        assert result == 1  # 2.5 -> 2 -> 2-1 = 1 (zero-based index)

    @given(st.integers(min_value=1, max_value=100), st.integers(min_value=1, max_value=100))
    def test_should_convert_valid_indices_correctly(self, index: int, array_size: int):
        """Property-based test: valid 1-based indices should convert to correct 0-based indices."""
        # Only test when index is within valid range
        if 1 <= index <= array_size:
            result = validate_array_index(index, array_size, "test items")
            assert result == index - 1  # Should convert to 0-based index

    @given(st.integers(max_value=0))
    def test_should_reject_non_positive_indices(self, invalid_index: int):
        """Property-based test: any non-positive integer should be rejected."""
        with pytest.raises(ValidationError):
            validate_array_index(invalid_index, 5, "test items")


class TestSafeGetNestedValue:
    """Test safe nested value extraction function."""

    def test_successful_nested_access(self):
        """Should extract nested values successfully."""
        data = {"level1": {"level2": {"target": "found_value"}}}

        result = safe_get_nested_value(data, ["level1", "level2", "target"], "default")
        assert result == "found_value"

    def test_missing_intermediate_key(self):
        """Should return default when intermediate key is missing."""
        data = {"level1": {"wrong_key": "value"}}

        result = safe_get_nested_value(data, ["level1", "level2", "target"], "default")
        assert result == "default"

    def test_missing_final_key(self):
        """Should return default when final key is missing."""
        data = {"level1": {"level2": {"other_key": "value"}}}

        result = safe_get_nested_value(data, ["level1", "level2", "target"], "default")
        assert result == "default"

    def test_none_intermediate_value(self):
        """Should return default when intermediate value is None."""
        data = {"level1": None}

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

    def test_none_as_explicit_default(self):
        """Should return None when explicitly passed as default value."""
        # Empty array with None as explicit default should return None (not raise)
        result = safe_get_array_item([], 0, "test items", default=None)
        assert result is None

        # Out of bounds with None as explicit default should return None (not raise)
        result = safe_get_array_item(["item0"], 5, "test items", default=None)
        assert result is None

    def test_successful_access_ignores_default(self):
        """Should return array item when access succeeds, ignoring default."""
        array = ["item0", "item1"]

        # When access succeeds, default is ignored
        result = safe_get_array_item(array, 0, "test items", default="fallback")
        assert result == "item0"

        result = safe_get_array_item(array, 1, "test items", default=None)
        assert result == "item1"


class TestValidateAwsResponseStructure:
    """Test AWS response structure validation function."""

    def test_valid_response_structure(self):
        """Should pass validation for correct response structure."""
        response = {"Instances": [], "NextToken": "abc123", "Metadata": {}}

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


class TestValidateSshKeyPath:
    """Test SSH key path validation function."""

    def test_none_returns_none(self):
        """Should return None when key is None."""
        result = validate_ssh_key_path(None)
        assert result is None

    def test_valid_key_path(self, tmp_path):
        """Should return expanded path when key file exists."""
        key_file = tmp_path / "test_key.pem"
        key_file.touch()

        result = validate_ssh_key_path(str(key_file))
        assert result == str(key_file)

    def test_expands_home_directory(self, tmp_path, monkeypatch):
        """Should expand ~ in key path."""
        # Create a temporary directory to act as home
        fake_home = tmp_path / "fake_home"
        fake_home.mkdir()
        key_file = fake_home / ".ssh" / "id_rsa"
        key_file.parent.mkdir(parents=True)
        key_file.touch()

        # Monkeypatch expanduser to use our fake home
        monkeypatch.setattr("pathlib.Path.expanduser", lambda self: fake_home / ".ssh" / "id_rsa")

        result = validate_ssh_key_path("~/.ssh/id_rsa")
        assert result == str(key_file)

    def test_nonexistent_file_raises_bad_parameter(self, tmp_path):
        """Should raise BadParameter when key file does not exist."""
        nonexistent_path = str(tmp_path / "nonexistent_key.pem")

        with pytest.raises(typer.BadParameter) as exc_info:
            validate_ssh_key_path(nonexistent_path)

        assert "SSH key file not found" in str(exc_info.value)
        assert nonexistent_path in str(exc_info.value)

    def test_directory_raises_bad_parameter(self, tmp_path):
        """Should raise BadParameter when key path is a directory."""
        # tmp_path is a directory
        with pytest.raises(typer.BadParameter) as exc_info:
            validate_ssh_key_path(str(tmp_path))

        assert "SSH key path is not a file" in str(exc_info.value)
        assert str(tmp_path) in str(exc_info.value)

    def test_empty_string_raises_bad_parameter(self, tmp_path):
        """Should raise BadParameter for empty string."""
        with pytest.raises(typer.BadParameter) as exc_info:
            validate_ssh_key_path("")

        assert "SSH key path cannot be empty" in str(exc_info.value)

    def test_whitespace_only_raises_bad_parameter(self, tmp_path):
        """Should raise BadParameter for whitespace-only string."""
        with pytest.raises(typer.BadParameter) as exc_info:
            validate_ssh_key_path("   ")

        assert "SSH key path cannot be empty" in str(exc_info.value)
