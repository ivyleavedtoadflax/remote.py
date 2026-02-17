import datetime

import pytest
from botocore.exceptions import ClientError, NoCredentialsError
from click.exceptions import Exit

from remote.exceptions import (
    AWSServiceError,
    InstanceNotFoundError,
    InvalidInputError,
    MultipleInstancesFoundError,
    ResourceNotFoundError,
    ValidationError,
)
from remote.instance_resolver import get_instance_name
from remote.utils import (
    create_table,
    extract_resource_name_from_arn,
    extract_tags_dict,
    format_duration,
    get_account_id,
    get_instance_dns,
    get_instance_id,
    get_instance_ids,
    get_instance_info,
    get_instance_status,
    get_instance_type,
    get_instances,
    get_launch_template_id,
    get_status_style,
    get_volume_ids,
    get_volume_name,
    handle_cli_errors,
    is_instance_running,
    parse_duration_to_minutes,
)

# Remove duplicate fixtures - use centralized ones from conftest.py


def test_get_account_id(mocker):
    mock_boto3_client = mocker.patch("remote.utils.boto3.client")
    mock_sts_client = mock_boto3_client.return_value
    mock_sts_client.get_caller_identity.return_value = {"Account": "123456789012"}

    result = get_account_id()

    assert result == "123456789012"
    mock_boto3_client.assert_called_once_with("sts")
    mock_sts_client.get_caller_identity.assert_called_once()


class TestExtractTagsDict:
    """Tests for extract_tags_dict utility function."""

    def test_extract_tags_from_valid_list(self):
        """Should convert AWS tag list format to dictionary."""
        tags_list = [
            {"Key": "Name", "Value": "my-instance"},
            {"Key": "Environment", "Value": "production"},
        ]
        result = extract_tags_dict(tags_list)
        assert result == {"Name": "my-instance", "Environment": "production"}

    def test_extract_tags_from_empty_list(self):
        """Should return empty dict for empty list."""
        result = extract_tags_dict([])
        assert result == {}

    def test_extract_tags_from_none(self):
        """Should return empty dict for None input."""
        result = extract_tags_dict(None)
        assert result == {}

    def test_extract_single_tag(self):
        """Should work with single tag."""
        tags_list = [{"Key": "Name", "Value": "test"}]
        result = extract_tags_dict(tags_list)
        assert result == {"Name": "test"}


class TestExtractResourceNameFromArn:
    """Tests for extract_resource_name_from_arn utility function."""

    def test_extract_from_slash_delimited_arn(self):
        """Should extract resource name from ARNs using forward-slash delimiter."""
        # ECS cluster ARN
        arn = "arn:aws:ecs:us-east-1:123456789012:cluster/my-cluster"
        assert extract_resource_name_from_arn(arn) == "my-cluster"

        # ECS service ARN
        arn = "arn:aws:ecs:us-east-1:123456789012:service/my-cluster/my-service"
        assert extract_resource_name_from_arn(arn) == "my-service"

        # Lambda function ARN
        arn = "arn:aws:lambda:us-east-1:123456789012:function/my-function"
        assert extract_resource_name_from_arn(arn) == "my-function"

    def test_extract_from_colon_delimited_arn(self):
        """Should extract resource name from ARNs using colon delimiter."""
        # SNS topic ARN
        arn = "arn:aws:sns:us-east-1:123456789012:my-topic"
        assert extract_resource_name_from_arn(arn) == "my-topic"

        # SQS queue ARN
        arn = "arn:aws:sqs:us-east-1:123456789012:my-queue"
        assert extract_resource_name_from_arn(arn) == "my-queue"

        # IAM user ARN
        arn = "arn:aws:iam::123456789012:user:my-user"
        assert extract_resource_name_from_arn(arn) == "my-user"

    def test_extract_handles_nested_slashes(self):
        """Should return last segment for ARNs with multiple slashes."""
        # ECS task ARN with nested path
        arn = "arn:aws:ecs:us-east-1:123456789012:task/my-cluster/abc123def456"
        assert extract_resource_name_from_arn(arn) == "abc123def456"

    def test_extract_returns_arn_for_short_arn(self):
        """Should return original ARN if it has fewer than 6 colon-separated parts."""
        short_arn = "arn:aws:s3"
        assert extract_resource_name_from_arn(short_arn) == "arn:aws:s3"

    def test_extract_simple_string_without_delimiters(self):
        """Should return original string if no delimiters present and short."""
        simple = "my-resource"
        assert extract_resource_name_from_arn(simple) == "my-resource"

    def test_extract_empty_string(self):
        """Should return empty string for empty input."""
        assert extract_resource_name_from_arn("") == ""

    def test_extract_slash_takes_precedence_over_colon(self):
        """Should use slash delimiter when both are present."""
        # ARN with both / and : in resource part
        arn = "arn:aws:ecs:us-east-1:123456789012:service/cluster-name/service-name"
        assert extract_resource_name_from_arn(arn) == "service-name"


def test_get_instance_id_single_instance(mocker):
    mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

    mock_ec2_client.return_value.describe_instances.return_value = {
        "Reservations": [{"Instances": [{"InstanceId": "i-0123456789abcdef0"}]}]
    }

    result = get_instance_id("test-instance")

    assert result == "i-0123456789abcdef0"
    mock_ec2_client.return_value.describe_instances.assert_called_once_with(
        Filters=[
            {"Name": "tag:Name", "Values": ["test-instance"]},
            {
                "Name": "instance-state-name",
                "Values": ["pending", "stopping", "stopped", "running"],
            },
        ]
    )


def test_get_instance_id_multiple_instances(mocker):
    mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

    mock_ec2_client.return_value.describe_instances.return_value = {
        "Reservations": [
            {"Instances": [{"InstanceId": "i-0123456789abcdef0"}]},
            {"Instances": [{"InstanceId": "i-0123456789abcdef1"}]},
        ]
    }

    with pytest.raises(MultipleInstancesFoundError) as exc_info:
        get_instance_id("test-instance")
    assert "Multiple instances (2) found" in str(exc_info.value)


def test_get_instance_id_not_found(mocker):
    mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

    mock_ec2_client.return_value.describe_instances.return_value = {"Reservations": []}

    with pytest.raises(InstanceNotFoundError) as exc_info:
        get_instance_id("nonexistent-instance")
    assert "not found" in str(exc_info.value)


def test_get_instance_status_with_id(mocker):
    mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

    expected_response = {
        "InstanceStatuses": [
            {
                "InstanceId": "i-0123456789abcdef0",
                "InstanceState": {"Name": "running"},
            }
        ]
    }
    mock_ec2_client.return_value.describe_instance_status.return_value = expected_response

    result = get_instance_status("i-0123456789abcdef0")

    assert result == expected_response
    mock_ec2_client.return_value.describe_instance_status.assert_called_once_with(
        InstanceIds=["i-0123456789abcdef0"]
    )


def test_get_instance_status_without_id(mocker):
    mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

    expected_response = {"InstanceStatuses": []}
    mock_ec2_client.return_value.describe_instance_status.return_value = expected_response

    result = get_instance_status()

    assert result == expected_response
    mock_ec2_client.return_value.describe_instance_status.assert_called_once_with()


def test_get_instances(mocker, mock_ec2_instances):
    mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

    # Mock the paginator
    mock_paginator = mocker.MagicMock()
    mock_paginator.paginate.return_value = [mock_ec2_instances]
    mock_ec2_client.return_value.get_paginator.return_value = mock_paginator

    result = get_instances()

    assert result == mock_ec2_instances["Reservations"]
    mock_ec2_client.return_value.get_paginator.assert_called_once_with("describe_instances")
    mock_paginator.paginate.assert_called_once()


def test_get_instance_dns(mocker):
    mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

    mock_ec2_client.return_value.describe_instances.return_value = {
        "Reservations": [
            {"Instances": [{"PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com"}]}
        ]
    }

    result = get_instance_dns("i-0123456789abcdef0")

    assert result == "ec2-123-45-67-89.compute-1.amazonaws.com"
    mock_ec2_client.return_value.describe_instances.assert_called_once_with(
        InstanceIds=["i-0123456789abcdef0"]
    )


def test_get_instance_name_success(mocker):
    mock_config_manager = mocker.patch("remote.instance_resolver.config_manager")
    mock_config_manager.get_instance_name.return_value = "test-instance"

    result = get_instance_name()

    assert result == "test-instance"
    mock_config_manager.get_instance_name.assert_called_once()


def test_get_instance_name_no_config(mocker):
    mock_config_manager = mocker.patch("remote.instance_resolver.config_manager")
    mock_config_manager.get_instance_name.return_value = None

    with pytest.raises(Exit) as exc_info:
        get_instance_name()
    assert exc_info.value.exit_code == 1


def test_get_instance_info_with_running_instances(mocker, mock_ec2_instances):
    instances = mock_ec2_instances["Reservations"]

    names, public_dnss, statuses, instance_types, launch_times = get_instance_info(instances)

    assert names == ["test-instance-1", "test-instance-2"]
    assert public_dnss == ["ec2-123-45-67-89.compute-1.amazonaws.com", ""]
    assert statuses == ["running", "stopped"]
    assert instance_types == ["t2.micro", "t2.small"]
    assert launch_times[0] == "2023-07-15 00:00:00 UTC"
    assert launch_times[1] is None  # stopped instance has no launch time


def test_get_instance_info_with_no_tags():
    instances = [
        {
            "Instances": [
                {
                    "InstanceId": "i-0123456789abcdef0",
                    "InstanceType": "t2.micro",
                    "State": {"Name": "running"},
                    "LaunchTime": datetime.datetime.now(),
                    "PublicDnsName": "example.com",
                    # No Tags field
                }
            ]
        }
    ]

    names, public_dnss, statuses, instance_types, launch_times = get_instance_info(instances)

    # Should return empty lists since no instances have Name tags
    assert names == []
    assert public_dnss == []
    assert statuses == []
    assert instance_types == []
    assert launch_times == []


def test_get_instance_info_nameless_instance_does_not_block_others():
    """Test that nameless instances don't block finding valid instances in the same reservation.

    This is a regression test for the bug where a 'break' was used instead of 'continue',
    causing the loop to exit early when encountering an instance without a Name tag.
    """
    instances = [
        {
            "Instances": [
                {
                    # First instance has no Name tag
                    "InstanceId": "i-nameless",
                    "InstanceType": "t2.micro",
                    "State": {"Name": "running"},
                    "LaunchTime": datetime.datetime.now(),
                    "PublicDnsName": "nameless.example.com",
                    "Tags": [],  # Empty tags - no Name
                },
                {
                    # Second instance has a Name tag - should still be found
                    "InstanceId": "i-named",
                    "InstanceType": "t2.small",
                    "State": {"Name": "running"},
                    "LaunchTime": datetime.datetime.now(),
                    "PublicDnsName": "named.example.com",
                    "Tags": [{"Key": "Name", "Value": "my-named-instance"}],
                },
            ]
        }
    ]

    names, public_dnss, statuses, instance_types, launch_times = get_instance_info(instances)

    # The named instance should be found even though it comes after a nameless one
    assert names == ["my-named-instance"]
    assert public_dnss == ["named.example.com"]
    assert statuses == ["running"]
    assert instance_types == ["t2.small"]
    assert len(launch_times) == 1


def test_get_instance_ids(mock_ec2_instances):
    instances = mock_ec2_instances["Reservations"]

    result = get_instance_ids(instances)

    assert result == ["i-0123456789abcdef0", "i-0123456789abcdef1"]


def test_get_instance_ids_filters_instances_without_name_tag():
    """Instances without a Name tag should be excluded (matches get_instance_info behavior)."""
    instances = [
        {
            "Instances": [
                {
                    "InstanceId": "i-with-name",
                    "Tags": [{"Key": "Name", "Value": "named-instance"}],
                },
                {
                    "InstanceId": "i-no-name-tag",
                    "Tags": [{"Key": "Environment", "Value": "test"}],
                },
                {
                    "InstanceId": "i-no-tags",
                    # No Tags key at all
                },
            ]
        }
    ]

    result = get_instance_ids(instances)

    assert result == ["i-with-name"]


def test_is_instance_running_true(mocker):
    mock_get_instance_status = mocker.patch("remote.utils.get_instance_status")
    mock_get_instance_status.return_value = {
        "InstanceStatuses": [{"InstanceState": {"Name": "running"}}]
    }

    result = is_instance_running("i-0123456789abcdef0")

    assert result is True
    mock_get_instance_status.assert_called_once_with("i-0123456789abcdef0")


def test_is_instance_running_false(mocker):
    mock_get_instance_status = mocker.patch("remote.utils.get_instance_status")
    mock_get_instance_status.return_value = {
        "InstanceStatuses": [{"InstanceState": {"Name": "stopped"}}]
    }

    result = is_instance_running("i-0123456789abcdef0")

    assert result is False


def test_is_instance_running_no_status(mocker):
    mock_get_instance_status = mocker.patch("remote.utils.get_instance_status")
    mock_get_instance_status.return_value = {"InstanceStatuses": []}

    result = is_instance_running("i-0123456789abcdef0")

    assert result is False


def test_is_instance_running_unexpected_structure_raises_error(mocker):
    """Test that unexpected response structure raises AWSServiceError."""
    mock_get_instance_status = mocker.patch("remote.utils.get_instance_status")
    # Return a structure that will cause a TypeError when accessing .get()
    mock_get_instance_status.return_value = {"InstanceStatuses": [None]}

    with pytest.raises(AWSServiceError) as exc_info:
        is_instance_running("i-0123456789abcdef0")

    assert exc_info.value.aws_error_code == "UnexpectedResponse"
    assert "unexpected" in exc_info.value.message.lower()


def test_get_instance_type(mocker):
    mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

    mock_ec2_client.return_value.describe_instances.return_value = {
        "Reservations": [{"Instances": [{"InstanceType": "t2.micro"}]}]
    }

    result = get_instance_type("i-0123456789abcdef0")

    assert result == "t2.micro"
    mock_ec2_client.return_value.describe_instances.assert_called_once_with(
        InstanceIds=["i-0123456789abcdef0"]
    )


def test_get_volume_ids(mocker):
    mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

    mock_ec2_client.return_value.describe_volumes.return_value = {
        "Volumes": [
            {"VolumeId": "vol-0123456789abcdef0"},
            {"VolumeId": "vol-0123456789abcdef1"},
        ]
    }

    result = get_volume_ids("i-0123456789abcdef0")

    assert result == ["vol-0123456789abcdef0", "vol-0123456789abcdef1"]
    mock_ec2_client.return_value.describe_volumes.assert_called_once_with(
        Filters=[{"Name": "attachment.instance-id", "Values": ["i-0123456789abcdef0"]}]
    )


def test_get_volume_name_with_name_tag(mocker):
    mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

    mock_ec2_client.return_value.describe_volumes.return_value = {
        "Volumes": [
            {
                "Tags": [
                    {"Key": "Name", "Value": "test-volume"},
                    {"Key": "Environment", "Value": "test"},
                ]
            }
        ]
    }

    result = get_volume_name("vol-0123456789abcdef0")

    assert result == "test-volume"
    mock_ec2_client.return_value.describe_volumes.assert_called_once_with(
        VolumeIds=["vol-0123456789abcdef0"]
    )


def test_get_volume_name_without_name_tag(mocker):
    mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

    mock_ec2_client.return_value.describe_volumes.return_value = {
        "Volumes": [
            {
                "Tags": [
                    {"Key": "Environment", "Value": "test"},
                ]
            }
        ]
    }

    result = get_volume_name("vol-0123456789abcdef0")

    assert result == ""


def test_get_volume_name_no_tags(mocker):
    mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

    mock_ec2_client.return_value.describe_volumes.return_value = {
        "Volumes": [{}]  # No Tags field
    }

    result = get_volume_name("vol-0123456789abcdef0")

    assert result == ""


def test_get_launch_template_id(mocker):
    mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

    mock_ec2_client.return_value.describe_launch_templates.return_value = {
        "LaunchTemplates": [{"LaunchTemplateId": "lt-0123456789abcdef0"}]
    }

    result = get_launch_template_id("test-template")

    assert result == "lt-0123456789abcdef0"
    mock_ec2_client.return_value.describe_launch_templates.assert_called_once_with(
        Filters=[{"Name": "tag:Name", "Values": ["test-template"]}]
    )


# ============================================================================
# Consolidated Error Handling Tests
# ============================================================================
# These tests verify AWS error handling across multiple functions using
# parametrization to reduce duplication while maintaining coverage.


class TestAWSErrorHandling:
    """Consolidated tests for AWS ClientError and NoCredentialsError handling.

    This class uses parametrization to test error handling patterns that are
    repeated across multiple AWS utility functions, reducing test duplication.
    """

    @pytest.mark.parametrize(
        "error_type,error_code,expected_aws_code",
        [
            ("client_error", "AccessDenied", "AccessDenied"),
            ("no_credentials", None, "NoCredentials"),
        ],
        ids=["client_error", "no_credentials"],
    )
    def test_get_account_id_aws_errors(self, mocker, error_type, error_code, expected_aws_code):
        """Test get_account_id handles AWS errors correctly."""
        mock_sts_client = mocker.patch("remote.utils.get_sts_client")

        if error_type == "client_error":
            error_response = {"Error": {"Code": error_code, "Message": "Error"}}
            mock_sts_client.return_value.get_caller_identity.side_effect = ClientError(
                error_response, "get_caller_identity"
            )
        else:
            mock_sts_client.return_value.get_caller_identity.side_effect = NoCredentialsError()

        with pytest.raises(AWSServiceError) as exc_info:
            get_account_id()

        assert exc_info.value.service == "STS"
        assert exc_info.value.operation == "get_caller_identity"
        assert exc_info.value.aws_error_code == expected_aws_code

    @pytest.mark.parametrize(
        "error_type,error_code,expected_aws_code",
        [
            ("client_error", "UnauthorizedOperation", "UnauthorizedOperation"),
            ("no_credentials", None, "NoCredentials"),
        ],
        ids=["client_error", "no_credentials"],
    )
    def test_get_instance_id_aws_errors(self, mocker, error_type, error_code, expected_aws_code):
        """Test get_instance_id handles AWS errors correctly."""
        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

        if error_type == "client_error":
            error_response = {"Error": {"Code": error_code, "Message": "Error"}}
            mock_ec2_client.return_value.describe_instances.side_effect = ClientError(
                error_response, "describe_instances"
            )
        else:
            mock_ec2_client.return_value.describe_instances.side_effect = NoCredentialsError()

        with pytest.raises(AWSServiceError) as exc_info:
            get_instance_id("test-instance")

        assert exc_info.value.service == "EC2"
        assert exc_info.value.operation == "describe_instances"
        assert exc_info.value.aws_error_code == expected_aws_code

    @pytest.mark.parametrize(
        "error_type,error_code",
        [
            ("client_error", "InvalidInstanceID.NotFound"),
            ("no_credentials", None),
        ],
        ids=["client_error", "no_credentials"],
    )
    def test_get_instance_status_aws_errors(self, mocker, error_type, error_code):
        """Test get_instance_status handles AWS errors correctly."""
        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

        if error_type == "client_error":
            error_response = {"Error": {"Code": error_code, "Message": "Error"}}
            mock_ec2_client.return_value.describe_instance_status.side_effect = ClientError(
                error_response, "describe_instance_status"
            )
            with pytest.raises(AWSServiceError) as exc_info:
                get_instance_status("i-12345678")
            assert exc_info.value.service == "EC2"
            assert exc_info.value.operation == "describe_instance_status"
        else:
            mock_ec2_client.return_value.describe_instance_status.side_effect = NoCredentialsError()
            with pytest.raises(AWSServiceError) as exc_info:
                get_instance_status()
            assert exc_info.value.aws_error_code == "NoCredentials"

    @pytest.mark.parametrize(
        "error_type,error_code,expected_aws_code",
        [
            ("client_error", "RequestLimitExceeded", "RequestLimitExceeded"),
            ("no_credentials", None, "NoCredentials"),
        ],
        ids=["client_error", "no_credentials"],
    )
    def test_get_instances_aws_errors(self, mocker, error_type, error_code, expected_aws_code):
        """Test get_instances handles AWS errors correctly (via paginator)."""
        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")
        mock_paginator = mocker.MagicMock()
        mock_ec2_client.return_value.get_paginator.return_value = mock_paginator

        if error_type == "client_error":
            error_response = {"Error": {"Code": error_code, "Message": "Error"}}
            mock_paginator.paginate.side_effect = ClientError(error_response, "describe_instances")
        else:
            mock_paginator.paginate.side_effect = NoCredentialsError()

        with pytest.raises(AWSServiceError) as exc_info:
            get_instances()

        assert exc_info.value.aws_error_code == expected_aws_code

    @pytest.mark.parametrize(
        "error_type,error_code",
        [
            ("client_error", "InvalidInstanceID.NotFound"),
            ("no_credentials", None),
        ],
        ids=["client_error", "no_credentials"],
    )
    def test_get_volume_ids_aws_errors(self, mocker, error_type, error_code):
        """Test get_volume_ids handles AWS errors correctly."""
        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

        if error_type == "client_error":
            error_response = {"Error": {"Code": error_code, "Message": "Error"}}
            mock_ec2_client.return_value.describe_volumes.side_effect = ClientError(
                error_response, "describe_volumes"
            )
            with pytest.raises(AWSServiceError) as exc_info:
                get_volume_ids("i-12345678")
            assert exc_info.value.service == "EC2"
            assert exc_info.value.operation == "describe_volumes"
        else:
            mock_ec2_client.return_value.describe_volumes.side_effect = NoCredentialsError()
            with pytest.raises(AWSServiceError) as exc_info:
                get_volume_ids("i-12345678")
            assert exc_info.value.aws_error_code == "NoCredentials"

    def test_get_launch_template_id_client_error(self, mocker):
        """Test get_launch_template_id handles ClientError correctly."""
        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")
        error_response = {"Error": {"Code": "UnauthorizedOperation", "Message": "Unauthorized"}}
        mock_ec2_client.return_value.describe_launch_templates.side_effect = ClientError(
            error_response, "describe_launch_templates"
        )

        with pytest.raises(AWSServiceError) as exc_info:
            get_launch_template_id("test-template")

        assert exc_info.value.service == "EC2"
        assert exc_info.value.operation == "describe_launch_templates"
        assert exc_info.value.aws_error_code == "UnauthorizedOperation"


class TestResourceNotFoundErrors:
    """Tests for functions that convert specific AWS errors to ResourceNotFoundError."""

    @pytest.mark.parametrize(
        "func,func_args,resource_type,resource_id",
        [
            (get_instance_dns, ("i-1234567890abcdef0",), "Instance", "i-1234567890abcdef0"),
            (get_instance_type, ("i-1234567890abcdef0",), "Instance", "i-1234567890abcdef0"),
        ],
        ids=["get_instance_dns", "get_instance_type"],
    )
    def test_instance_not_found_error(self, mocker, func, func_args, resource_type, resource_id):
        """Test functions raise ResourceNotFoundError for InvalidInstanceID.NotFound."""
        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")
        error_response = {
            "Error": {"Code": "InvalidInstanceID.NotFound", "Message": "Instance not found"}
        }
        mock_ec2_client.return_value.describe_instances.side_effect = ClientError(
            error_response, "describe_instances"
        )

        with pytest.raises(ResourceNotFoundError) as exc_info:
            func(*func_args)

        assert exc_info.value.resource_type == resource_type
        assert exc_info.value.resource_id == resource_id

    @pytest.mark.parametrize(
        "func,func_args",
        [
            (get_instance_dns, ("i-12345678",)),
            (get_instance_type, ("i-12345678",)),
        ],
        ids=["get_instance_dns", "get_instance_type"],
    )
    def test_other_client_error_raises_aws_service_error(self, mocker, func, func_args):
        """Test functions raise AWSServiceError for other ClientErrors."""
        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")
        error_response = {"Error": {"Code": "UnauthorizedOperation", "Message": "Unauthorized"}}
        mock_ec2_client.return_value.describe_instances.side_effect = ClientError(
            error_response, "describe_instances"
        )

        with pytest.raises(AWSServiceError) as exc_info:
            func(*func_args)

        assert exc_info.value.aws_error_code == "UnauthorizedOperation"

    def test_get_volume_name_volume_not_found_error(self, mocker):
        """Test get_volume_name raises ResourceNotFoundError for InvalidVolumeID.NotFound."""
        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")
        error_response = {
            "Error": {"Code": "InvalidVolumeID.NotFound", "Message": "Volume not found"}
        }
        mock_ec2_client.return_value.describe_volumes.side_effect = ClientError(
            error_response, "describe_volumes"
        )

        with pytest.raises(ResourceNotFoundError) as exc_info:
            get_volume_name("vol-1234567890abcdef0")

        assert exc_info.value.resource_type == "Volume"
        assert exc_info.value.resource_id == "vol-1234567890abcdef0"

    def test_get_volume_name_other_client_error(self, mocker):
        """Test get_volume_name raises AWSServiceError for other ClientErrors."""
        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")
        error_response = {"Error": {"Code": "UnauthorizedOperation", "Message": "Unauthorized"}}
        mock_ec2_client.return_value.describe_volumes.side_effect = ClientError(
            error_response, "describe_volumes"
        )

        with pytest.raises(AWSServiceError) as exc_info:
            get_volume_name("vol-12345678")

        assert exc_info.value.aws_error_code == "UnauthorizedOperation"

    def test_get_launch_template_id_no_templates_found(self, mocker):
        """Test get_launch_template_id raises ResourceNotFoundError when no templates found."""
        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")
        mock_ec2_client.return_value.describe_launch_templates.return_value = {
            "LaunchTemplates": []
        }

        with pytest.raises(ResourceNotFoundError) as exc_info:
            get_launch_template_id("nonexistent-template")

        assert exc_info.value.resource_type == "Launch Template"
        assert exc_info.value.resource_id == "nonexistent-template"


# Special case tests that don't fit the parametrized patterns above


def test_get_instance_id_no_instances_in_reservation(mocker):
    """Test get_instance_id when reservation has no instances."""
    mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

    mock_ec2_client.return_value.describe_instances.return_value = {
        "Reservations": [
            {
                "Instances": []  # Empty instances list
            }
        ]
    }

    with pytest.raises(InstanceNotFoundError) as exc_info:
        get_instance_id("test-instance")

    assert exc_info.value.instance_name == "test-instance"
    assert "no instances in reservation" in exc_info.value.details


def test_get_launch_template_id_validation_error(mocker):
    """Test get_launch_template_id with empty template name."""
    with pytest.raises(ValidationError) as exc_info:
        get_launch_template_id("")

    assert "Launch template name cannot be empty" in str(exc_info.value)


# ============================================================================
# Issue 20: Edge Case Tests for Pagination and Caching
# ============================================================================


class TestPaginationEdgeCases:
    """Tests for pagination edge cases in get_instances."""

    def test_get_instances_empty_pagination_response(self, mocker):
        """Test get_instances with empty pagination response (no instances)."""
        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

        # Mock paginator that returns a single empty page
        mock_paginator = mocker.MagicMock()
        mock_paginator.paginate.return_value = [{"Reservations": []}]
        mock_ec2_client.return_value.get_paginator.return_value = mock_paginator

        result = get_instances()

        assert result == []
        mock_ec2_client.return_value.get_paginator.assert_called_once_with("describe_instances")
        mock_paginator.paginate.assert_called_once()

    def test_get_instances_multiple_pages(self, mocker):
        """Test get_instances handles multiple pages correctly."""
        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

        # Create mock data for multiple pages
        page1_reservations = [
            {"Instances": [{"InstanceId": "i-page1instance1", "State": {"Name": "running"}}]},
            {"Instances": [{"InstanceId": "i-page1instance2", "State": {"Name": "stopped"}}]},
        ]
        page2_reservations = [
            {"Instances": [{"InstanceId": "i-page2instance1", "State": {"Name": "running"}}]},
        ]
        page3_reservations = [
            {"Instances": [{"InstanceId": "i-page3instance1", "State": {"Name": "pending"}}]},
            {"Instances": [{"InstanceId": "i-page3instance2", "State": {"Name": "running"}}]},
        ]

        # Mock paginator that returns multiple pages
        mock_paginator = mocker.MagicMock()
        mock_paginator.paginate.return_value = [
            {"Reservations": page1_reservations},
            {"Reservations": page2_reservations},
            {"Reservations": page3_reservations},
        ]
        mock_ec2_client.return_value.get_paginator.return_value = mock_paginator

        result = get_instances()

        # Should contain all reservations from all pages
        assert len(result) == 5
        assert result[0]["Instances"][0]["InstanceId"] == "i-page1instance1"
        assert result[1]["Instances"][0]["InstanceId"] == "i-page1instance2"
        assert result[2]["Instances"][0]["InstanceId"] == "i-page2instance1"
        assert result[3]["Instances"][0]["InstanceId"] == "i-page3instance1"
        assert result[4]["Instances"][0]["InstanceId"] == "i-page3instance2"

    def test_get_instances_multiple_empty_pages(self, mocker):
        """Test get_instances with multiple empty pages."""
        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

        # Mock paginator returning multiple empty pages
        mock_paginator = mocker.MagicMock()
        mock_paginator.paginate.return_value = [
            {"Reservations": []},
            {"Reservations": []},
            {"Reservations": []},
        ]
        mock_ec2_client.return_value.get_paginator.return_value = mock_paginator

        result = get_instances()

        assert result == []

    def test_get_instances_pages_with_mixed_content(self, mocker):
        """Test get_instances with mix of empty and populated pages."""
        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

        # Mock paginator with mix of empty and populated pages
        mock_paginator = mocker.MagicMock()
        mock_paginator.paginate.return_value = [
            {"Reservations": []},  # Empty page
            {
                "Reservations": [
                    {"Instances": [{"InstanceId": "i-only-one", "State": {"Name": "running"}}]}
                ]
            },  # Populated page
            {"Reservations": []},  # Empty page
        ]
        mock_ec2_client.return_value.get_paginator.return_value = mock_paginator

        result = get_instances()

        assert len(result) == 1
        assert result[0]["Instances"][0]["InstanceId"] == "i-only-one"

    def test_get_instances_with_exclude_terminated_filter(self, mocker):
        """Test get_instances pagination with exclude_terminated filter."""
        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

        # Mock paginator
        mock_paginator = mocker.MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "Reservations": [
                    {"Instances": [{"InstanceId": "i-running", "State": {"Name": "running"}}]}
                ]
            }
        ]
        mock_ec2_client.return_value.get_paginator.return_value = mock_paginator

        result = get_instances(exclude_terminated=True)

        # Verify the filter was passed correctly
        mock_paginator.paginate.assert_called_once_with(
            Filters=[
                {
                    "Name": "instance-state-name",
                    "Values": ["pending", "running", "shutting-down", "stopping", "stopped"],
                }
            ]
        )
        assert len(result) == 1


class TestClientCaching:
    """Tests for AWS client caching behavior."""

    def test_get_ec2_client_caching(self, mocker):
        """Test that get_ec2_client returns cached client on subsequent calls."""
        from remote.utils import get_ec2_client

        # Clear the cache before testing
        get_ec2_client.cache_clear()

        mock_boto3_client = mocker.patch("remote.utils.boto3.client")
        mock_client_instance = mocker.MagicMock()
        mock_boto3_client.return_value = mock_client_instance

        # First call should create the client
        client1 = get_ec2_client()

        # Second call should return the same cached client
        client2 = get_ec2_client()

        # Third call should still return the same cached client
        client3 = get_ec2_client()

        # boto3.client should only be called once due to caching
        mock_boto3_client.assert_called_once_with("ec2")

        # All calls should return the same instance
        assert client1 is client2
        assert client2 is client3

        # Clean up cache for other tests
        get_ec2_client.cache_clear()

    def test_get_sts_client_caching(self, mocker):
        """Test that get_sts_client returns cached client on subsequent calls."""
        from remote.utils import get_sts_client

        # Clear the cache before testing
        get_sts_client.cache_clear()

        mock_boto3_client = mocker.patch("remote.utils.boto3.client")
        mock_client_instance = mocker.MagicMock()
        mock_boto3_client.return_value = mock_client_instance

        # First call should create the client
        client1 = get_sts_client()

        # Second call should return the same cached client
        client2 = get_sts_client()

        # boto3.client should only be called once due to caching
        mock_boto3_client.assert_called_once_with("sts")

        # All calls should return the same instance
        assert client1 is client2

        # Clean up cache for other tests
        get_sts_client.cache_clear()

    def test_get_ec2_client_cache_clear_creates_new_client(self, mocker):
        """Test that clearing cache causes a new client to be created."""
        from remote.utils import get_ec2_client

        # Clear the cache before testing
        get_ec2_client.cache_clear()

        mock_boto3_client = mocker.patch("remote.utils.boto3.client")
        mock_client_1 = mocker.MagicMock()
        mock_client_2 = mocker.MagicMock()
        mock_boto3_client.side_effect = [mock_client_1, mock_client_2]

        # First call creates first client
        client1 = get_ec2_client()
        assert client1 is mock_client_1

        # Clear the cache
        get_ec2_client.cache_clear()

        # Next call should create a new client
        client2 = get_ec2_client()
        assert client2 is mock_client_2

        # boto3.client should be called twice
        assert mock_boto3_client.call_count == 2

        # Clean up
        get_ec2_client.cache_clear()


# ============================================================================
# Issue 39: Duration Parsing Tests
# ============================================================================


class TestParseDurationToMinutes:
    """Tests for parse_duration_to_minutes function."""

    def test_parse_hours_only(self):
        """Test parsing hours-only duration."""
        assert parse_duration_to_minutes("1h") == 60
        assert parse_duration_to_minutes("2h") == 120
        assert parse_duration_to_minutes("10h") == 600
        assert parse_duration_to_minutes("24h") == 1440

    def test_parse_minutes_only(self):
        """Test parsing minutes-only duration."""
        assert parse_duration_to_minutes("1m") == 1
        assert parse_duration_to_minutes("30m") == 30
        assert parse_duration_to_minutes("45m") == 45
        assert parse_duration_to_minutes("120m") == 120

    def test_parse_hours_and_minutes(self):
        """Test parsing combined hours and minutes."""
        assert parse_duration_to_minutes("1h30m") == 90
        assert parse_duration_to_minutes("2h15m") == 135
        assert parse_duration_to_minutes("0h30m") == 30
        assert parse_duration_to_minutes("1h0m") == 60

    def test_parse_case_insensitive(self):
        """Test that parsing is case-insensitive."""
        assert parse_duration_to_minutes("1H") == 60
        assert parse_duration_to_minutes("30M") == 30
        assert parse_duration_to_minutes("1H30M") == 90
        assert parse_duration_to_minutes("2H15m") == 135

    def test_parse_with_whitespace(self):
        """Test that parsing handles whitespace."""
        assert parse_duration_to_minutes(" 1h ") == 60
        assert parse_duration_to_minutes("  30m  ") == 30
        assert parse_duration_to_minutes(" 1h30m ") == 90

    def test_parse_empty_string_raises_error(self):
        """Test that empty string raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            parse_duration_to_minutes("")
        assert "Duration cannot be empty" in str(exc_info.value)

    def test_parse_whitespace_only_raises_error(self):
        """Test that whitespace-only string raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            parse_duration_to_minutes("   ")
        assert "Duration cannot be empty" in str(exc_info.value)

    def test_parse_invalid_format_raises_error(self):
        """Test that invalid formats raise ValidationError."""
        invalid_inputs = ["3", "abc", "1x", "1 hour", "1:30", "1.5h", "h30m", "hm"]
        for invalid_input in invalid_inputs:
            with pytest.raises(ValidationError) as exc_info:
                parse_duration_to_minutes(invalid_input)
            assert "Invalid duration format" in str(exc_info.value)

    def test_parse_zero_duration_raises_error(self):
        """Test that zero duration raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            parse_duration_to_minutes("0h")
        assert "greater than 0 minutes" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            parse_duration_to_minutes("0m")
        assert "greater than 0 minutes" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            parse_duration_to_minutes("0h0m")
        assert "greater than 0 minutes" in str(exc_info.value)


class TestFormatDuration:
    """Tests for format_duration function."""

    def test_format_hours_only(self):
        """Test formatting full hours."""
        assert format_duration(60) == "1h"
        assert format_duration(120) == "2h"
        assert format_duration(180) == "3h"

    def test_format_minutes_only(self):
        """Test formatting minutes less than an hour."""
        assert format_duration(1) == "1m"
        assert format_duration(30) == "30m"
        assert format_duration(59) == "59m"

    def test_format_hours_and_minutes(self):
        """Test formatting combined hours and minutes."""
        assert format_duration(90) == "1h 30m"
        assert format_duration(135) == "2h 15m"
        assert format_duration(61) == "1h 1m"

    def test_format_zero_or_negative(self):
        """Test formatting zero or negative values."""
        assert format_duration(0) == "0m"
        assert format_duration(-1) == "0m"
        assert format_duration(-60) == "0m"


class TestGetStatusStyle:
    """Tests for the get_status_style utility function."""

    def test_green_states(self):
        """Test that healthy/available states return green."""
        green_states = ["running", "available", "completed", "in-use", "active"]
        for state in green_states:
            assert get_status_style(state) == "green", f"Expected green for '{state}'"

    def test_green_states_case_insensitive(self):
        """Test that status matching is case-insensitive."""
        assert get_status_style("RUNNING") == "green"
        assert get_status_style("Running") == "green"
        assert get_status_style("AVAILABLE") == "green"
        assert get_status_style("Completed") == "green"

    def test_red_states(self):
        """Test that stopped/failed states return red."""
        red_states = ["stopped", "failed", "error", "deleted"]
        for state in red_states:
            assert get_status_style(state) == "red", f"Expected red for '{state}'"

    def test_red_states_case_insensitive(self):
        """Test that red state matching is case-insensitive."""
        assert get_status_style("STOPPED") == "red"
        assert get_status_style("Failed") == "red"
        assert get_status_style("ERROR") == "red"

    def test_yellow_states(self):
        """Test that transitioning states return yellow."""
        yellow_states = ["pending", "stopping", "shutting-down", "creating", "deleting"]
        for state in yellow_states:
            assert get_status_style(state) == "yellow", f"Expected yellow for '{state}'"

    def test_yellow_states_case_insensitive(self):
        """Test that yellow state matching is case-insensitive."""
        assert get_status_style("PENDING") == "yellow"
        assert get_status_style("Stopping") == "yellow"
        assert get_status_style("SHUTTING-DOWN") == "yellow"

    def test_unknown_states_return_white(self):
        """Test that unknown states return white as default."""
        unknown_states = ["unknown", "custom-state", "foo", ""]
        for state in unknown_states:
            assert get_status_style(state) == "white", f"Expected white for '{state}'"


# ============================================================================
# Tests for handle_cli_errors decorator
# ============================================================================


class TestHandleCliErrorsDecorator:
    """Tests for the handle_cli_errors decorator."""

    def test_decorator_passes_through_successful_return(self):
        """Test that decorator passes through return values for successful calls."""

        @handle_cli_errors
        def successful_function() -> str:
            return "success"

        result = successful_function()
        assert result == "success"

    def test_decorator_passes_through_arguments(self):
        """Test that decorator correctly passes positional and keyword arguments."""

        @handle_cli_errors
        def function_with_args(a: int, b: str, *, c: bool = False) -> tuple:
            return (a, b, c)

        result = function_with_args(1, "test", c=True)
        assert result == (1, "test", True)

    def test_decorator_handles_instance_not_found_error(self, capsys):
        """Test that InstanceNotFoundError is caught and formatted correctly."""

        @handle_cli_errors
        def raise_instance_not_found():
            raise InstanceNotFoundError("test-instance")

        with pytest.raises(Exit) as exc_info:
            raise_instance_not_found()

        assert exc_info.value.exit_code == 1
        captured = capsys.readouterr()
        assert "Error:" in captured.out
        assert "test-instance" in captured.out

    def test_decorator_handles_multiple_instances_found_error(self, capsys):
        """Test that MultipleInstancesFoundError is caught and formatted correctly."""

        @handle_cli_errors
        def raise_multiple_instances():
            raise MultipleInstancesFoundError("test-instance", 3)

        with pytest.raises(Exit) as exc_info:
            raise_multiple_instances()

        assert exc_info.value.exit_code == 1
        captured = capsys.readouterr()
        assert "Error:" in captured.out
        assert "test-instance" in captured.out

    def test_decorator_handles_resource_not_found_error(self, capsys):
        """Test that ResourceNotFoundError is caught and formatted correctly."""

        @handle_cli_errors
        def raise_resource_not_found():
            raise ResourceNotFoundError("Volume", "vol-12345")

        with pytest.raises(Exit) as exc_info:
            raise_resource_not_found()

        assert exc_info.value.exit_code == 1
        captured = capsys.readouterr()
        assert "Error:" in captured.out
        assert "vol-12345" in captured.out

    def test_decorator_handles_aws_service_error(self, capsys):
        """Test that AWSServiceError is caught and formatted with AWS Error prefix."""

        @handle_cli_errors
        def raise_aws_error():
            raise AWSServiceError("EC2", "describe_instances", "UnauthorizedOperation", "msg")

        with pytest.raises(Exit) as exc_info:
            raise_aws_error()

        assert exc_info.value.exit_code == 1
        captured = capsys.readouterr()
        assert "AWS Error:" in captured.out

    def test_decorator_handles_validation_error(self, capsys):
        """Test that ValidationError is caught and formatted correctly."""

        @handle_cli_errors
        def raise_validation_error():
            raise ValidationError("Invalid input format")

        with pytest.raises(Exit) as exc_info:
            raise_validation_error()

        assert exc_info.value.exit_code == 1
        captured = capsys.readouterr()
        assert "Error:" in captured.out
        assert "Invalid input format" in captured.out

    def test_decorator_handles_invalid_input_error(self, capsys):
        """Test that InvalidInputError is caught and formatted correctly."""

        @handle_cli_errors
        def raise_invalid_input_error():
            raise InvalidInputError("volume_id", "bad-id", "vol-xxxxxxxxx")

        with pytest.raises(Exit) as exc_info:
            raise_invalid_input_error()

        assert exc_info.value.exit_code == 1
        captured = capsys.readouterr()
        assert "Error:" in captured.out
        assert "volume_id" in captured.out
        assert "bad-id" in captured.out

    def test_decorator_does_not_catch_other_exceptions(self):
        """Test that other exceptions are not caught by the decorator."""

        @handle_cli_errors
        def raise_value_error():
            raise ValueError("some other error")

        with pytest.raises(ValueError) as exc_info:
            raise_value_error()

        assert str(exc_info.value) == "some other error"

    def test_decorator_preserves_function_metadata(self):
        """Test that the decorator preserves the original function's metadata."""

        @handle_cli_errors
        def documented_function():
            """This is the docstring."""
            pass

        assert documented_function.__name__ == "documented_function"
        assert documented_function.__doc__ == "This is the docstring."


class TestCreateTable:
    """Tests for create_table utility function."""

    def test_create_table_basic(self):
        """Should create a table with columns and rows."""
        columns = [
            {"name": "ID"},
            {"name": "Name"},
        ]
        rows = [
            ["1", "Alice"],
            ["2", "Bob"],
        ]
        table = create_table("Test Table", columns, rows)

        assert table.title == "Test Table"
        assert len(table.columns) == 2
        assert table.columns[0].header == "ID"
        assert table.columns[1].header == "Name"
        assert table.row_count == 2

    def test_create_table_with_styles(self):
        """Should create a table with styled columns."""
        columns = [
            {"name": "ID", "style": "green"},
            {"name": "Name", "style": "cyan"},
        ]
        rows = [["1", "Test"]]
        table = create_table("Styled Table", columns, rows)

        assert table.columns[0].style == "green"
        assert table.columns[1].style == "cyan"

    def test_create_table_with_justify(self):
        """Should create a table with justified columns."""
        columns = [
            {"name": "Left"},
            {"name": "Right", "justify": "right"},
            {"name": "Center", "justify": "center"},
        ]
        rows = [["a", "b", "c"]]
        table = create_table("Justified Table", columns, rows)

        assert table.columns[0].justify == "left"  # default
        assert table.columns[1].justify == "right"
        assert table.columns[2].justify == "center"

    def test_create_table_with_no_wrap(self):
        """Should create a table with no_wrap columns."""
        columns = [
            {"name": "Wrap", "no_wrap": False},
            {"name": "NoWrap", "no_wrap": True},
        ]
        rows = [["text", "text"]]
        table = create_table("NoWrap Table", columns, rows)

        assert table.columns[0].no_wrap is False
        assert table.columns[1].no_wrap is True

    def test_create_table_empty_rows(self):
        """Should create a table with no rows."""
        columns = [{"name": "Column1"}]
        rows = []
        table = create_table("Empty Table", columns, rows)

        assert table.row_count == 0

    def test_create_table_empty_columns(self):
        """Should create a table with no columns."""
        columns = []
        rows = []
        table = create_table("No Columns", columns, rows)

        assert len(table.columns) == 0

    def test_create_table_all_options(self):
        """Should create a table with all column options."""
        columns = [
            {
                "name": "Full",
                "style": "bold red",
                "justify": "center",
                "no_wrap": True,
            },
        ]
        rows = [["value"]]
        table = create_table("Full Options", columns, rows)

        col = table.columns[0]
        assert col.header == "Full"
        assert col.style == "bold red"
        assert col.justify == "center"
        assert col.no_wrap is True


class TestConfirmAction:
    """Tests for confirm_action utility function."""

    def test_confirm_action_basic_confirmed(self, mocker):
        """Should return True when user confirms."""
        from remote.utils import confirm_action

        mock_confirm = mocker.patch("remote.utils.typer.confirm", return_value=True)

        result = confirm_action("terminate", "instance", "my-server")

        assert result is True
        mock_confirm.assert_called_once_with(
            "Are you sure you want to terminate instance 'my-server'?", default=False
        )

    def test_confirm_action_basic_declined(self, mocker):
        """Should return False when user declines."""
        from remote.utils import confirm_action

        mock_confirm = mocker.patch("remote.utils.typer.confirm", return_value=False)

        result = confirm_action("stop", "instance", "web-server")

        assert result is False
        mock_confirm.assert_called_once_with(
            "Are you sure you want to stop instance 'web-server'?", default=False
        )

    def test_confirm_action_with_details(self, mocker):
        """Should include details in confirmation message."""
        from remote.utils import confirm_action

        mock_confirm = mocker.patch("remote.utils.typer.confirm", return_value=True)

        result = confirm_action(
            "change type of",
            "instance",
            "my-server",
            details="from t3.micro to t3.large",
        )

        assert result is True
        mock_confirm.assert_called_once_with(
            "Are you sure you want to change type of instance 'my-server' "
            "from t3.micro to t3.large?",
            default=False,
        )

    def test_confirm_action_with_default_true(self, mocker):
        """Should pass default=True for non-destructive actions."""
        from remote.utils import confirm_action

        mock_confirm = mocker.patch("remote.utils.typer.confirm", return_value=True)

        result = confirm_action("start", "instance", "my-server", default=True)

        assert result is True
        mock_confirm.assert_called_once_with(
            "Are you sure you want to start instance 'my-server'?", default=True
        )

    def test_confirm_action_various_resource_types(self, mocker):
        """Should work with different resource types."""
        from remote.utils import confirm_action

        mock_confirm = mocker.patch("remote.utils.typer.confirm", return_value=True)

        # Test with AMI
        confirm_action("create", "AMI", "my-ami")
        assert "create AMI 'my-ami'" in mock_confirm.call_args[0][0]

        # Test with snapshot
        confirm_action("create", "snapshot", "backup-snap")
        assert "create snapshot 'backup-snap'" in mock_confirm.call_args[0][0]

        # Test with service
        confirm_action("scale", "service", "api-service")
        assert "scale service 'api-service'" in mock_confirm.call_args[0][0]

    def test_confirm_action_with_complex_details(self, mocker):
        """Should handle complex details strings."""
        from remote.utils import confirm_action

        mock_confirm = mocker.patch("remote.utils.typer.confirm", return_value=True)

        confirm_action(
            "create",
            "AMI",
            "production-ami",
            details="from instance web-server (i-1234567890abcdef0)",
        )

        assert (
            "Are you sure you want to create AMI 'production-ami' "
            "from instance web-server (i-1234567890abcdef0)?"
        ) == mock_confirm.call_args[0][0]


# ============================================================================
# Issue 213: Additional Edge Case Tests
# ============================================================================


class TestExtractResourceNameFromArnEdgeCases:
    """Additional edge case tests for extract_resource_name_from_arn function.

    These tests cover malformed ARNs and unusual edge cases.
    """

    def test_arn_with_trailing_slash(self):
        """Should handle ARN with trailing slash."""
        arn = "arn:aws:ecs:us-east-1:123456789012:cluster/my-cluster/"
        assert extract_resource_name_from_arn(arn) == ""

    def test_arn_with_multiple_consecutive_slashes(self):
        """Should handle ARN with multiple consecutive slashes."""
        arn = "arn:aws:ecs:us-east-1:123456789012:cluster//my-cluster"
        assert extract_resource_name_from_arn(arn) == "my-cluster"

    def test_arn_with_only_colons(self):
        """Should handle ARN-like string with many colons."""
        arn = "arn:aws:service:region:account:resource:name:extra"
        assert extract_resource_name_from_arn(arn) == "extra"

    def test_arn_with_special_characters_in_resource(self):
        """Should handle resource names with special characters."""
        arn = "arn:aws:lambda:us-east-1:123456789012:function/my-func-v1.2.3"
        assert extract_resource_name_from_arn(arn) == "my-func-v1.2.3"

    def test_arn_with_unicode_characters(self):
        """Should handle resource names with unicode characters."""
        arn = "arn:aws:s3:us-east-1:123456789012:bucket/données-test"
        assert extract_resource_name_from_arn(arn) == "données-test"

    def test_whitespace_only_string(self):
        """Should handle whitespace-only input."""
        assert extract_resource_name_from_arn("   ") == "   "

    def test_exactly_six_colon_parts(self):
        """Should handle ARN with exactly 6 colon-separated parts."""
        arn = "arn:aws:sqs:us-east-1:123456789012:my-queue"
        assert extract_resource_name_from_arn(arn) == "my-queue"

    def test_five_colon_parts_returns_original(self):
        """Should return original for ARN with 5 colon-separated parts."""
        arn = "arn:aws:s3:::my-bucket"
        # Has 6 parts: ['arn', 'aws', 's3', '', '', 'my-bucket']
        assert extract_resource_name_from_arn(arn) == "my-bucket"

    def test_arn_with_empty_resource_part(self):
        """Should handle ARN with empty resource part."""
        arn = "arn:aws:sqs:us-east-1:123456789012:"
        assert extract_resource_name_from_arn(arn) == ""


class TestHandleCliErrorsAdditionalCases:
    """Additional edge case tests for handle_cli_errors decorator.

    Tests for additional exception types and error scenarios.
    """

    def test_decorator_with_none_return_value(self):
        """Test that decorator handles functions returning None."""

        @handle_cli_errors
        def return_none() -> None:
            return None

        result = return_none()
        assert result is None

    def test_decorator_with_generator_function(self):
        """Test that decorator works with generator functions."""

        @handle_cli_errors
        def generator_func():
            yield 1
            yield 2
            yield 3

        result = list(generator_func())
        assert result == [1, 2, 3]

    def test_decorator_reraises_exit_exceptions(self):
        """Test that typer.Exit is re-raised, not caught."""
        from click.exceptions import Exit

        @handle_cli_errors
        def raise_exit():
            raise Exit(code=42)

        with pytest.raises(Exit) as exc_info:
            raise_exit()

        assert exc_info.value.exit_code == 42

    def test_decorator_handles_aws_service_error_with_details(self, capsys):
        """Test that AWSServiceError details are included in output."""

        @handle_cli_errors
        def raise_detailed_aws_error():
            raise AWSServiceError(
                service="EC2",
                operation="describe_instances",
                aws_error_code="UnauthorizedOperation",
                message="Detailed error message with context",
            )

        with pytest.raises(Exit):
            raise_detailed_aws_error()

        captured = capsys.readouterr()
        assert "AWS Error:" in captured.out
        assert "EC2" in captured.out

    def test_decorator_handles_resource_not_found_error_with_details(self, capsys):
        """Test that ResourceNotFoundError shows resource details."""

        @handle_cli_errors
        def raise_resource_not_found():
            raise ResourceNotFoundError("Launch Template", "lt-abc123", "Check template name")

        with pytest.raises(Exit):
            raise_resource_not_found()

        captured = capsys.readouterr()
        assert "Error:" in captured.out
        assert "lt-abc123" in captured.out


class TestParseDurationToMinutesEdgeCases:
    """Additional edge case tests for parse_duration_to_minutes."""

    def test_parse_large_values(self):
        """Test parsing very large duration values."""
        # 1000 hours
        assert parse_duration_to_minutes("1000h") == 60000
        # 10000 minutes
        assert parse_duration_to_minutes("10000m") == 10000

    def test_parse_mixed_case_variations(self):
        """Test various mixed case combinations."""
        assert parse_duration_to_minutes("1h30m") == 90
        assert parse_duration_to_minutes("1H30m") == 90
        assert parse_duration_to_minutes("1h30M") == 90
        assert parse_duration_to_minutes("1H30M") == 90

    def test_parse_leading_zeros(self):
        """Test parsing durations with leading zeros."""
        assert parse_duration_to_minutes("01h") == 60
        assert parse_duration_to_minutes("05m") == 5
        assert parse_duration_to_minutes("01h05m") == 65

    def test_parse_single_digit_values(self):
        """Test parsing single digit values."""
        assert parse_duration_to_minutes("1h") == 60
        assert parse_duration_to_minutes("1m") == 1
        assert parse_duration_to_minutes("1h1m") == 61

    def test_parse_negative_values_invalid(self):
        """Test that negative values raise ValidationError."""
        with pytest.raises(ValidationError):
            parse_duration_to_minutes("-1h")

        with pytest.raises(ValidationError):
            parse_duration_to_minutes("-30m")


class TestFormatDurationEdgeCases:
    """Additional edge case tests for format_duration."""

    def test_format_large_values(self):
        """Test formatting very large values including days."""
        # 100 hours = 4 days + 4 hours
        assert format_duration(6000) == "4d 4h"
        # 100 hours 30 minutes = 4 days + 4 hours + 30 minutes
        assert format_duration(6030) == "4d 4h 30m"

    def test_format_exactly_one_hour(self):
        """Test formatting exactly one hour."""
        assert format_duration(60) == "1h"

    def test_format_just_under_one_hour(self):
        """Test formatting 59 minutes."""
        assert format_duration(59) == "59m"

    def test_format_just_over_one_hour(self):
        """Test formatting 61 minutes."""
        assert format_duration(61) == "1h 1m"

    def test_format_float_truncation(self):
        """Test that float values are truncated correctly."""
        # format_duration expects int, but should handle gracefully
        assert format_duration(int(90.5)) == "1h 30m"
        assert format_duration(int(90.9)) == "1h 30m"


# ============================================================================
# Tests for Uncovered Code Paths (Issue #255)
# ============================================================================


class TestPromptForSelectionErrorPaths:
    """Test error paths in prompt_for_selection."""

    def test_should_error_on_empty_multi_select_input(self, mocker, capsys):
        """Should error when multi-select input is empty (lines 281-282)."""
        from remote.utils import prompt_for_selection

        mocker.patch("typer.prompt", return_value="   ")  # Whitespace-only

        items = ["item1", "item2"]
        with pytest.raises(Exit):
            prompt_for_selection(
                items,
                item_type="test",
                table_title="Test Items",
                columns=[{"name": "Item"}],
                row_builder=lambda i, item: [item],
                allow_multiple=True,
            )

        captured = capsys.readouterr()
        assert "selection cannot be empty" in captured.out

    def test_should_skip_empty_parts_in_comma_separated_input(self, mocker):
        """Should skip empty strings when splitting comma-separated input (line 288)."""
        from remote.utils import prompt_for_selection

        # "1,,2" should select items 1 and 2, skipping the empty middle part
        mocker.patch("typer.prompt", return_value="1,,2")

        items = ["item1", "item2", "item3"]
        result = prompt_for_selection(
            items,
            item_type="test",
            table_title="Test Items",
            columns=[{"name": "Item"}],
            row_builder=lambda i, item: [item],
            allow_multiple=True,
        )

        assert result == ["item1", "item2"]

    def test_should_error_on_no_valid_choices_provided(self, mocker, capsys):
        """Should error when all comma-separated parts are empty (lines 294-295)."""
        from remote.utils import prompt_for_selection

        mocker.patch("typer.prompt", return_value=",,")  # All empty

        items = ["item1", "item2"]
        with pytest.raises(Exit):
            prompt_for_selection(
                items,
                item_type="test",
                table_title="Test Items",
                columns=[{"name": "Item"}],
                row_builder=lambda i, item: [item],
                allow_multiple=True,
            )

        captured = capsys.readouterr()
        assert "No valid" in captured.out

    def test_should_handle_validation_error_in_multi_select(self, mocker, capsys):
        """Should catch ValidationError in multi-select (lines 300-302)."""
        from remote.utils import prompt_for_selection

        mocker.patch("typer.prompt", return_value="99")  # Out of range

        items = ["item1", "item2"]
        with pytest.raises(Exit):
            prompt_for_selection(
                items,
                item_type="test",
                table_title="Test Items",
                columns=[{"name": "Item"}],
                row_builder=lambda i, item: [item],
                allow_multiple=True,
            )

        captured = capsys.readouterr()
        assert "Error" in captured.out

    def test_should_handle_value_error_in_multi_select(self, mocker, capsys):
        """Should catch ValueError in multi-select (lines 303-305)."""
        from remote.utils import prompt_for_selection

        mocker.patch("typer.prompt", return_value="abc")  # Not a number

        items = ["item1", "item2"]
        with pytest.raises(Exit):
            prompt_for_selection(
                items,
                item_type="test",
                table_title="Test Items",
                columns=[{"name": "Item"}],
                row_builder=lambda i, item: [item],
                allow_multiple=True,
            )

        captured = capsys.readouterr()
        assert "Error" in captured.out

    def test_should_error_on_empty_single_select_input(self, mocker, capsys):
        """Should error when single-select input is empty (lines 311-312)."""
        from remote.utils import prompt_for_selection

        mocker.patch("typer.prompt", return_value="   ")  # Whitespace-only

        items = ["item1", "item2"]
        with pytest.raises(Exit):
            prompt_for_selection(
                items,
                item_type="test",
                table_title="Test Items",
                columns=[{"name": "Item"}],
                row_builder=lambda i, item: [item],
                allow_multiple=False,
            )

        captured = capsys.readouterr()
        assert "selection cannot be empty" in captured.out

    def test_should_handle_validation_error_in_single_select(self, mocker, capsys):
        """Should catch ValidationError in single-select (lines 316-318)."""
        from remote.utils import prompt_for_selection

        mocker.patch("typer.prompt", return_value="99")  # Out of range

        items = ["item1", "item2"]
        with pytest.raises(Exit):
            prompt_for_selection(
                items,
                item_type="test",
                table_title="Test Items",
                columns=[{"name": "Item"}],
                row_builder=lambda i, item: [item],
                allow_multiple=False,
            )

        captured = capsys.readouterr()
        assert "Error" in captured.out


class TestGetInstanceInfoErrorPaths:
    """Test error paths in get_instance_info."""

    def test_should_handle_malformed_launch_time(self, mocker, capsys):
        """Should handle AttributeError/ValueError in launch time parsing (lines 749-750)."""
        # Create instance with malformed LaunchTime (string instead of datetime)
        instances = [
            {
                "Instances": [
                    {
                        "InstanceId": "i-test123",
                        "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        "PublicDnsName": "test.amazonaws.com",
                        "State": {"Name": "running"},
                        "LaunchTime": "not-a-datetime",  # Invalid - will cause AttributeError
                        "InstanceType": "t2.micro",
                    }
                ]
            }
        ]

        result = get_instance_info(instances)
        names, dns_names, statuses, types, launch_times = result

        # Should still process the instance but launch_time should be None
        assert names == ["test-instance"]
        assert launch_times == [None]

    def test_should_skip_malformed_instance_data(self, mocker, capsys):
        """Should skip instances with malformed data (lines 757-760)."""
        # Create instance with missing required fields (causes KeyError/TypeError)
        instances = [
            {
                "Instances": [
                    {
                        "InstanceId": "i-test123",
                        # Missing Tags key - will cause TypeError when iterating
                        "Tags": None,
                        "PublicDnsName": "test.amazonaws.com",
                        "State": {"Name": "running"},
                        "InstanceType": "t2.micro",
                    },
                    {
                        "InstanceId": "i-test456",
                        "Tags": [{"Key": "Name", "Value": "valid-instance"}],
                        "PublicDnsName": "test2.amazonaws.com",
                        "State": {"Name": "running"},
                        "InstanceType": "t2.micro",
                    },
                ]
            }
        ]

        result = get_instance_info(instances)
        names, dns_names, statuses, types, launch_times = result

        # Should skip malformed instance and process valid one
        assert "valid-instance" in names

        # Note: The warning is printed via print_warning but tests capture may not capture it
        # The key assertion is that valid instances are processed correctly


class TestIsInstanceRunningReraise:
    """Test re-raise behavior in is_instance_running (line 825)."""

    def test_should_reraise_aws_service_error(self, mocker):
        """Should re-raise AWSServiceError (line 825)."""
        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

        error_response = {"Error": {"Code": "UnauthorizedOperation", "Message": "Access denied"}}
        mock_ec2_client.return_value.describe_instance_status.side_effect = ClientError(
            error_response, "describe_instance_status"
        )

        # Use a valid instance ID format
        with pytest.raises(AWSServiceError) as exc_info:
            is_instance_running("i-1234567890abcdef0")

        assert exc_info.value.aws_error_code == "UnauthorizedOperation"

    def test_should_reraise_invalid_input_error(self, mocker):
        """Should re-raise InvalidInputError for invalid instance ID format."""
        # Pass invalid instance ID - should raise InvalidInputError
        with pytest.raises(InvalidInputError):
            is_instance_running("invalid-id")  # Invalid format


class TestGetLaunchTemplatesWithFilter:
    """Test get_launch_templates with name filter (lines 956-967)."""

    def test_should_filter_templates_by_name(self, mocker):
        """Should filter templates by name pattern (lines 962-965)."""
        from remote.utils import get_launch_templates

        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")
        mock_ec2_client.return_value.describe_launch_templates.return_value = {
            "LaunchTemplates": [
                {"LaunchTemplateId": "lt-001", "LaunchTemplateName": "web-server"},
                {"LaunchTemplateId": "lt-002", "LaunchTemplateName": "db-server"},
                {"LaunchTemplateId": "lt-003", "LaunchTemplateName": "web-api"},
            ]
        }

        result = get_launch_templates(name_filter="web")

        assert len(result) == 2
        assert result[0]["LaunchTemplateName"] == "web-server"
        assert result[1]["LaunchTemplateName"] == "web-api"

    def test_should_return_all_templates_without_filter(self, mocker):
        """Should return all templates when no filter provided."""
        from remote.utils import get_launch_templates

        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")
        mock_ec2_client.return_value.describe_launch_templates.return_value = {
            "LaunchTemplates": [
                {"LaunchTemplateId": "lt-001", "LaunchTemplateName": "web-server"},
                {"LaunchTemplateId": "lt-002", "LaunchTemplateName": "db-server"},
            ]
        }

        result = get_launch_templates()

        assert len(result) == 2


class TestGetLaunchTemplateVersionsErrors:
    """Test error handling in get_launch_template_versions (lines 983-995)."""

    def test_should_raise_resource_not_found_for_missing_template(self, mocker):
        """Should raise ResourceNotFoundError for missing template (lines 992-994)."""
        from remote.utils import get_launch_template_versions

        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

        error_response = {
            "Error": {
                "Code": "InvalidLaunchTemplateName.NotFoundException",
                "Message": "Template not found",
            }
        }
        mock_ec2_client.return_value.describe_launch_template_versions.side_effect = ClientError(
            error_response, "describe_launch_template_versions"
        )

        with pytest.raises(ResourceNotFoundError) as exc_info:
            get_launch_template_versions("nonexistent-template")

        assert "Launch Template" in str(exc_info.value)
        assert "nonexistent-template" in str(exc_info.value)

    def test_should_reraise_other_aws_errors(self, mocker):
        """Should re-raise non-NotFound AWS errors (line 995)."""
        from remote.utils import get_launch_template_versions

        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

        error_response = {"Error": {"Code": "UnauthorizedOperation", "Message": "Access denied"}}
        mock_ec2_client.return_value.describe_launch_template_versions.side_effect = ClientError(
            error_response, "describe_launch_template_versions"
        )

        with pytest.raises(AWSServiceError) as exc_info:
            get_launch_template_versions("my-template")

        assert exc_info.value.aws_error_code == "UnauthorizedOperation"


# ============================================================================
# Tests for EventBridge Scheduler and IAM Client Functions
# ============================================================================


class TestSchedulerClientCaching:
    """Tests for EventBridge Scheduler client caching behavior."""

    def test_get_scheduler_client_caching(self, mocker):
        """Test that get_scheduler_client returns cached client on subsequent calls."""
        from remote.utils import clear_scheduler_client_cache, get_scheduler_client

        # Clear the cache before testing
        clear_scheduler_client_cache()

        mock_boto3_client = mocker.patch("remote.utils.boto3.client")
        mock_client_instance = mocker.MagicMock()
        mock_boto3_client.return_value = mock_client_instance

        # First call should create the client
        client1 = get_scheduler_client()

        # Second call should return the same cached client
        client2 = get_scheduler_client()

        # Third call should still return the same cached client
        client3 = get_scheduler_client()

        # boto3.client should only be called once due to caching
        mock_boto3_client.assert_called_once_with("scheduler")

        # All calls should return the same instance
        assert client1 is client2
        assert client2 is client3

        # Clean up cache for other tests
        clear_scheduler_client_cache()

    def test_get_scheduler_client_cache_clear_creates_new_client(self, mocker):
        """Test that clearing cache causes a new client to be created."""
        from remote.utils import clear_scheduler_client_cache, get_scheduler_client

        # Clear the cache before testing
        clear_scheduler_client_cache()

        mock_boto3_client = mocker.patch("remote.utils.boto3.client")
        mock_client_1 = mocker.MagicMock()
        mock_client_2 = mocker.MagicMock()
        mock_boto3_client.side_effect = [mock_client_1, mock_client_2]

        # First call creates first client
        client1 = get_scheduler_client()
        assert client1 is mock_client_1

        # Clear the cache
        clear_scheduler_client_cache()

        # Next call should create a new client
        client2 = get_scheduler_client()
        assert client2 is mock_client_2

        # boto3.client should be called twice
        assert mock_boto3_client.call_count == 2

        # Clean up
        clear_scheduler_client_cache()


class TestIAMClientCaching:
    """Tests for IAM client caching behavior."""

    def test_get_iam_client_caching(self, mocker):
        """Test that get_iam_client returns cached client on subsequent calls."""
        from remote.utils import clear_iam_client_cache, get_iam_client

        # Clear the cache before testing
        clear_iam_client_cache()

        mock_boto3_client = mocker.patch("remote.utils.boto3.client")
        mock_client_instance = mocker.MagicMock()
        mock_boto3_client.return_value = mock_client_instance

        # First call should create the client
        client1 = get_iam_client()

        # Second call should return the same cached client
        client2 = get_iam_client()

        # Third call should still return the same cached client
        client3 = get_iam_client()

        # boto3.client should only be called once due to caching
        mock_boto3_client.assert_called_once_with("iam")

        # All calls should return the same instance
        assert client1 is client2
        assert client2 is client3

        # Clean up cache for other tests
        clear_iam_client_cache()

    def test_get_iam_client_cache_clear_creates_new_client(self, mocker):
        """Test that clearing cache causes a new client to be created."""
        from remote.utils import clear_iam_client_cache, get_iam_client

        # Clear the cache before testing
        clear_iam_client_cache()

        mock_boto3_client = mocker.patch("remote.utils.boto3.client")
        mock_client_1 = mocker.MagicMock()
        mock_client_2 = mocker.MagicMock()
        mock_boto3_client.side_effect = [mock_client_1, mock_client_2]

        # First call creates first client
        client1 = get_iam_client()
        assert client1 is mock_client_1

        # Clear the cache
        clear_iam_client_cache()

        # Next call should create a new client
        client2 = get_iam_client()
        assert client2 is mock_client_2

        # boto3.client should be called twice
        assert mock_boto3_client.call_count == 2

        # Clean up
        clear_iam_client_cache()


class TestClearAWSClientCaches:
    """Tests for the clear_aws_client_caches convenience function."""

    def test_clear_aws_client_caches_clears_all_clients(self, mocker):
        """Test that clear_aws_client_caches clears all AWS client caches."""
        from remote.utils import (
            clear_aws_client_caches,
            get_cloudwatch_client,
            get_ec2_client,
            get_iam_client,
            get_scheduler_client,
            get_sts_client,
        )

        # Clear all caches first
        clear_aws_client_caches()

        mock_boto3_client = mocker.patch("remote.utils.boto3.client")
        mock_clients = [mocker.MagicMock() for _ in range(10)]
        mock_boto3_client.side_effect = mock_clients

        # Create all clients
        ec2_1 = get_ec2_client()
        sts_1 = get_sts_client()
        cloudwatch_1 = get_cloudwatch_client()
        scheduler_1 = get_scheduler_client()
        iam_1 = get_iam_client()

        # Should have called boto3.client 5 times
        assert mock_boto3_client.call_count == 5

        # Clear all caches
        clear_aws_client_caches()

        # Creating clients again should call boto3.client again
        ec2_2 = get_ec2_client()
        sts_2 = get_sts_client()
        cloudwatch_2 = get_cloudwatch_client()
        scheduler_2 = get_scheduler_client()
        iam_2 = get_iam_client()

        # Should have called boto3.client 10 times total
        assert mock_boto3_client.call_count == 10

        # Clients should be different instances
        assert ec2_1 is not ec2_2
        assert sts_1 is not sts_2
        assert cloudwatch_1 is not cloudwatch_2
        assert scheduler_1 is not scheduler_2
        assert iam_1 is not iam_2

        # Clean up
        clear_aws_client_caches()


# ============================================================================
# Tests for get_instance_names_by_ids (Issue #80)
# ============================================================================


class TestGetInstanceNamesByIds:
    """Tests for batch instance name lookup function."""

    def test_returns_names_for_valid_instances(self, mocker):
        """Should return name mapping for instances with Name tags."""
        from remote.utils import get_instance_names_by_ids

        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")
        mock_ec2_client.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-111",
                            "Tags": [{"Key": "Name", "Value": "web-server"}],
                        },
                        {
                            "InstanceId": "i-222",
                            "Tags": [{"Key": "Name", "Value": "db-server"}],
                        },
                    ]
                }
            ]
        }

        result = get_instance_names_by_ids(["i-111", "i-222"])

        assert result == {"i-111": "web-server", "i-222": "db-server"}
        mock_ec2_client.return_value.describe_instances.assert_called_once_with(
            InstanceIds=["i-111", "i-222"]
        )

    def test_returns_empty_dict_for_empty_input(self):
        """Should return empty dict when no instance IDs provided."""
        from remote.utils import get_instance_names_by_ids

        result = get_instance_names_by_ids([])

        assert result == {}

    def test_omits_instances_without_name_tag(self, mocker):
        """Should omit instances that don't have a Name tag."""
        from remote.utils import get_instance_names_by_ids

        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")
        mock_ec2_client.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-111",
                            "Tags": [{"Key": "Name", "Value": "web-server"}],
                        },
                        {
                            "InstanceId": "i-222",
                            "Tags": [{"Key": "Environment", "Value": "prod"}],
                        },
                        {
                            "InstanceId": "i-333",
                            # No Tags at all
                        },
                    ]
                }
            ]
        }

        result = get_instance_names_by_ids(["i-111", "i-222", "i-333"])

        assert result == {"i-111": "web-server"}

    def test_returns_empty_dict_on_aws_error(self, mocker):
        """Should return empty dict when AWS API call fails."""
        from remote.utils import get_instance_names_by_ids

        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")
        mock_ec2_client.return_value.describe_instances.side_effect = ClientError(
            {"Error": {"Code": "InvalidInstanceID.NotFound", "Message": "Not found"}},
            "describe_instances",
        )

        result = get_instance_names_by_ids(["i-terminated"])

        assert result == {}

    def test_handles_multiple_reservations(self, mocker):
        """Should handle instances spread across multiple reservations."""
        from remote.utils import get_instance_names_by_ids

        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")
        mock_ec2_client.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-111",
                            "Tags": [{"Key": "Name", "Value": "server-a"}],
                        }
                    ]
                },
                {
                    "Instances": [
                        {
                            "InstanceId": "i-222",
                            "Tags": [{"Key": "Name", "Value": "server-b"}],
                        }
                    ]
                },
            ]
        }

        result = get_instance_names_by_ids(["i-111", "i-222"])

        assert result == {"i-111": "server-a", "i-222": "server-b"}
