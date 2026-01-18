import datetime

import pytest
from botocore.exceptions import ClientError, NoCredentialsError
from click.exceptions import Exit

from remote.exceptions import (
    AWSServiceError,
    InstanceNotFoundError,
    MultipleInstancesFoundError,
    ResourceNotFoundError,
)
from remote.utils import (
    get_account_id,
    get_instance_dns,
    get_instance_id,
    get_instance_ids,
    get_instance_info,
    get_instance_name,
    get_instance_status,
    get_instance_type,
    get_instances,
    get_launch_template_id,
    get_snapshot_status,
    get_volume_ids,
    get_volume_name,
    is_instance_running,
    is_instance_stopped,
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
    mock_config_manager = mocker.patch("remote.config.config_manager")
    mock_config_manager.get_instance_name.return_value = "test-instance"

    result = get_instance_name()

    assert result == "test-instance"
    mock_config_manager.get_instance_name.assert_called_once()


def test_get_instance_name_no_config(mocker):
    mock_config_manager = mocker.patch("remote.config.config_manager")
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


def test_is_instance_stopped_true(mocker):
    mock_get_instance_status = mocker.patch("remote.utils.get_instance_status")
    mock_get_instance_status.return_value = {
        "InstanceStatuses": [{"InstanceState": {"Name": "stopped"}}]
    }

    result = is_instance_stopped("i-0123456789abcdef0")

    assert result is True


def test_is_instance_stopped_false(mocker):
    mock_get_instance_status = mocker.patch("remote.utils.get_instance_status")
    mock_get_instance_status.return_value = {
        "InstanceStatuses": [{"InstanceState": {"Name": "running"}}]
    }

    result = is_instance_stopped("i-0123456789abcdef0")

    assert result is False


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


def test_get_snapshot_status(mocker):
    mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

    mock_ec2_client.return_value.describe_snapshots.return_value = {
        "Snapshots": [{"State": "completed"}]
    }

    result = get_snapshot_status("snap-0123456789abcdef0")

    assert result == "completed"
    mock_ec2_client.return_value.describe_snapshots.assert_called_once_with(
        SnapshotIds=["snap-0123456789abcdef0"]
    )


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


# Error path tests for improved coverage


def test_get_account_id_client_error(mocker):
    """Test get_account_id with ClientError."""
    mock_boto3_client = mocker.patch("remote.utils.boto3.client")
    mock_sts_client = mock_boto3_client.return_value

    error_response = {"Error": {"Code": "AccessDenied", "Message": "Access denied"}}
    mock_sts_client.get_caller_identity.side_effect = ClientError(
        error_response, "get_caller_identity"
    )

    with pytest.raises(AWSServiceError) as exc_info:
        get_account_id()

    assert exc_info.value.service == "STS"
    assert exc_info.value.operation == "get_caller_identity"
    assert exc_info.value.aws_error_code == "AccessDenied"


def test_get_account_id_no_credentials_error(mocker):
    """Test get_account_id with NoCredentialsError."""
    mock_boto3_client = mocker.patch("remote.utils.boto3.client")
    mock_sts_client = mock_boto3_client.return_value

    mock_sts_client.get_caller_identity.side_effect = NoCredentialsError()

    with pytest.raises(AWSServiceError) as exc_info:
        get_account_id()

    assert exc_info.value.service == "STS"
    assert exc_info.value.operation == "get_caller_identity"
    assert exc_info.value.aws_error_code == "NoCredentials"


def test_get_instance_id_client_error(mocker):
    """Test get_instance_id with ClientError."""
    mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

    error_response = {"Error": {"Code": "UnauthorizedOperation", "Message": "Unauthorized"}}
    mock_ec2_client.return_value.describe_instances.side_effect = ClientError(
        error_response, "describe_instances"
    )

    with pytest.raises(AWSServiceError) as exc_info:
        get_instance_id("test-instance")

    assert exc_info.value.service == "EC2"
    assert exc_info.value.operation == "describe_instances"
    assert exc_info.value.aws_error_code == "UnauthorizedOperation"


def test_get_instance_id_no_credentials_error(mocker):
    """Test get_instance_id with NoCredentialsError."""
    mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

    mock_ec2_client.return_value.describe_instances.side_effect = NoCredentialsError()

    with pytest.raises(AWSServiceError) as exc_info:
        get_instance_id("test-instance")

    assert exc_info.value.service == "EC2"
    assert exc_info.value.operation == "describe_instances"
    assert exc_info.value.aws_error_code == "NoCredentials"


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


def test_get_instance_status_client_error(mocker):
    """Test get_instance_status with ClientError."""
    mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

    error_response = {
        "Error": {"Code": "InvalidInstanceID.NotFound", "Message": "Instance not found"}
    }
    mock_ec2_client.return_value.describe_instance_status.side_effect = ClientError(
        error_response, "describe_instance_status"
    )

    with pytest.raises(AWSServiceError) as exc_info:
        get_instance_status("i-12345678")

    assert exc_info.value.service == "EC2"
    assert exc_info.value.operation == "describe_instance_status"


def test_get_instance_status_no_credentials_error(mocker):
    """Test get_instance_status with NoCredentialsError."""
    mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

    mock_ec2_client.return_value.describe_instance_status.side_effect = NoCredentialsError()

    with pytest.raises(AWSServiceError) as exc_info:
        get_instance_status()

    assert exc_info.value.aws_error_code == "NoCredentials"


def test_get_instances_client_error(mocker):
    """Test get_instances with ClientError."""
    mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

    error_response = {"Error": {"Code": "RequestLimitExceeded", "Message": "Rate limit exceeded"}}

    # Mock paginator that raises error during iteration
    mock_paginator = mocker.MagicMock()
    mock_paginator.paginate.side_effect = ClientError(error_response, "describe_instances")
    mock_ec2_client.return_value.get_paginator.return_value = mock_paginator

    with pytest.raises(AWSServiceError) as exc_info:
        get_instances()

    assert exc_info.value.aws_error_code == "RequestLimitExceeded"


def test_get_instances_no_credentials_error(mocker):
    """Test get_instances with NoCredentialsError."""
    mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

    # Mock paginator that raises error during iteration
    mock_paginator = mocker.MagicMock()
    mock_paginator.paginate.side_effect = NoCredentialsError()
    mock_ec2_client.return_value.get_paginator.return_value = mock_paginator

    with pytest.raises(AWSServiceError) as exc_info:
        get_instances()

    assert exc_info.value.aws_error_code == "NoCredentials"


def test_get_instance_dns_instance_not_found_error(mocker):
    """Test get_instance_dns with instance not found."""
    mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

    error_response = {
        "Error": {"Code": "InvalidInstanceID.NotFound", "Message": "Instance not found"}
    }
    mock_ec2_client.return_value.describe_instances.side_effect = ClientError(
        error_response, "describe_instances"
    )

    with pytest.raises(ResourceNotFoundError) as exc_info:
        get_instance_dns("i-1234567890abcdef0")

    assert exc_info.value.resource_type == "Instance"
    assert exc_info.value.resource_id == "i-1234567890abcdef0"


def test_get_instance_dns_other_client_error(mocker):
    """Test get_instance_dns with other ClientError."""
    mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

    error_response = {"Error": {"Code": "UnauthorizedOperation", "Message": "Unauthorized"}}
    mock_ec2_client.return_value.describe_instances.side_effect = ClientError(
        error_response, "describe_instances"
    )

    with pytest.raises(AWSServiceError) as exc_info:
        get_instance_dns("i-12345678")

    assert exc_info.value.aws_error_code == "UnauthorizedOperation"


def test_get_instance_type_instance_not_found_error(mocker):
    """Test get_instance_type with instance not found."""
    mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

    error_response = {
        "Error": {"Code": "InvalidInstanceID.NotFound", "Message": "Instance not found"}
    }
    mock_ec2_client.return_value.describe_instances.side_effect = ClientError(
        error_response, "describe_instances"
    )

    with pytest.raises(ResourceNotFoundError) as exc_info:
        get_instance_type("i-1234567890abcdef0")

    assert exc_info.value.resource_type == "Instance"
    assert exc_info.value.resource_id == "i-1234567890abcdef0"


def test_get_instance_type_other_client_error(mocker):
    """Test get_instance_type with other ClientError."""
    mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

    error_response = {"Error": {"Code": "UnauthorizedOperation", "Message": "Unauthorized"}}
    mock_ec2_client.return_value.describe_instances.side_effect = ClientError(
        error_response, "describe_instances"
    )

    with pytest.raises(AWSServiceError) as exc_info:
        get_instance_type("i-12345678")

    assert exc_info.value.aws_error_code == "UnauthorizedOperation"


def test_get_volume_ids_client_error(mocker):
    """Test get_volume_ids with ClientError."""
    mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

    error_response = {
        "Error": {"Code": "InvalidInstanceID.NotFound", "Message": "Instance not found"}
    }
    mock_ec2_client.return_value.describe_volumes.side_effect = ClientError(
        error_response, "describe_volumes"
    )

    with pytest.raises(AWSServiceError) as exc_info:
        get_volume_ids("i-12345678")

    assert exc_info.value.service == "EC2"
    assert exc_info.value.operation == "describe_volumes"


def test_get_volume_ids_no_credentials_error(mocker):
    """Test get_volume_ids with NoCredentialsError."""
    mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

    mock_ec2_client.return_value.describe_volumes.side_effect = NoCredentialsError()

    with pytest.raises(AWSServiceError) as exc_info:
        get_volume_ids("i-12345678")

    assert exc_info.value.aws_error_code == "NoCredentials"


def test_get_volume_name_volume_not_found_error(mocker):
    """Test get_volume_name with volume not found."""
    mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

    error_response = {"Error": {"Code": "InvalidVolumeID.NotFound", "Message": "Volume not found"}}
    mock_ec2_client.return_value.describe_volumes.side_effect = ClientError(
        error_response, "describe_volumes"
    )

    with pytest.raises(ResourceNotFoundError) as exc_info:
        get_volume_name("vol-1234567890abcdef0")

    assert exc_info.value.resource_type == "Volume"
    assert exc_info.value.resource_id == "vol-1234567890abcdef0"


def test_get_volume_name_other_client_error(mocker):
    """Test get_volume_name with other ClientError."""
    mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

    error_response = {"Error": {"Code": "UnauthorizedOperation", "Message": "Unauthorized"}}
    mock_ec2_client.return_value.describe_volumes.side_effect = ClientError(
        error_response, "describe_volumes"
    )

    with pytest.raises(AWSServiceError) as exc_info:
        get_volume_name("vol-12345678")

    assert exc_info.value.aws_error_code == "UnauthorizedOperation"


def test_get_snapshot_status_snapshot_not_found_error(mocker):
    """Test get_snapshot_status with snapshot not found."""
    mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

    error_response = {
        "Error": {"Code": "InvalidSnapshotID.NotFound", "Message": "Snapshot not found"}
    }
    mock_ec2_client.return_value.describe_snapshots.side_effect = ClientError(
        error_response, "describe_snapshots"
    )

    with pytest.raises(ResourceNotFoundError) as exc_info:
        get_snapshot_status("snap-1234567890abcdef0")

    assert exc_info.value.resource_type == "Snapshot"
    assert exc_info.value.resource_id == "snap-1234567890abcdef0"


def test_get_snapshot_status_other_client_error(mocker):
    """Test get_snapshot_status with other ClientError."""
    mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

    error_response = {"Error": {"Code": "UnauthorizedOperation", "Message": "Unauthorized"}}
    mock_ec2_client.return_value.describe_snapshots.side_effect = ClientError(
        error_response, "describe_snapshots"
    )

    with pytest.raises(AWSServiceError) as exc_info:
        get_snapshot_status("snap-12345678")

    assert exc_info.value.aws_error_code == "UnauthorizedOperation"


def test_get_launch_template_id_client_error(mocker):
    """Test get_launch_template_id with ClientError."""
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


def test_get_launch_template_id_validation_error(mocker):
    """Test get_launch_template_id with empty template name."""
    from remote.exceptions import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        get_launch_template_id("")

    assert "Launch template name cannot be empty" in str(exc_info.value)


def test_get_launch_template_id_no_templates_found(mocker):
    """Test get_launch_template_id when no templates found."""
    mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

    mock_ec2_client.return_value.describe_launch_templates.return_value = {"LaunchTemplates": []}

    with pytest.raises(ResourceNotFoundError) as exc_info:
        get_launch_template_id("nonexistent-template")

    assert exc_info.value.resource_type == "Launch Template"
    assert exc_info.value.resource_id == "nonexistent-template"


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
