import datetime

import pytest
from botocore.exceptions import ClientError, NoCredentialsError
from click.exceptions import Exit

from remotepy.exceptions import (
    InstanceNotFoundError, 
    MultipleInstancesFoundError, 
    AWSServiceError,
    ResourceNotFoundError,
    ValidationError
)
from remotepy.utils import (
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


@pytest.fixture
def mock_instances_response():
    return {
        "Reservations": [
            {
                "Instances": [
                    {
                        "InstanceId": "i-0123456789abcdef0",
                        "InstanceType": "t2.micro",
                        "State": {"Name": "running", "Code": 16},
                        "LaunchTime": datetime.datetime(2023, 7, 15, 0, 0, 0, tzinfo=datetime.UTC),
                        "PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com",
                        "Tags": [
                            {"Key": "Name", "Value": "test-instance"},
                            {"Key": "Environment", "Value": "testing"},
                        ],
                    },
                ],
            },
            {
                "Instances": [
                    {
                        "InstanceId": "i-0123456789abcdef1",
                        "InstanceType": "t2.small",
                        "State": {"Name": "stopped", "Code": 80},
                        "LaunchTime": datetime.datetime(2023, 7, 16, 0, 0, 0, tzinfo=datetime.UTC),
                        "PublicDnsName": "",
                        "Tags": [
                            {"Key": "Name", "Value": "test-instance-2"},
                        ],
                    },
                ],
            },
        ]
    }


def test_get_account_id(mocker):
    mock_boto3_client = mocker.patch("remotepy.utils.boto3.client")
    mock_sts_client = mock_boto3_client.return_value
    mock_sts_client.get_caller_identity.return_value = {"Account": "123456789012"}

    result = get_account_id()

    assert result == "123456789012"
    mock_boto3_client.assert_called_once_with("sts")
    mock_sts_client.get_caller_identity.assert_called_once()


def test_get_instance_id_single_instance(mocker):
    mock_ec2_client = mocker.patch("remotepy.utils.ec2_client")

    mock_ec2_client.describe_instances.return_value = {
        "Reservations": [{"Instances": [{"InstanceId": "i-0123456789abcdef0"}]}]
    }

    result = get_instance_id("test-instance")

    assert result == "i-0123456789abcdef0"
    mock_ec2_client.describe_instances.assert_called_once_with(
        Filters=[
            {"Name": "tag:Name", "Values": ["test-instance"]},
            {
                "Name": "instance-state-name",
                "Values": ["pending", "stopping", "stopped", "running"],
            },
        ]
    )


def test_get_instance_id_multiple_instances(mocker):
    mock_ec2_client = mocker.patch("remotepy.utils.ec2_client")

    mock_ec2_client.describe_instances.return_value = {
        "Reservations": [
            {"Instances": [{"InstanceId": "i-0123456789abcdef0"}]},
            {"Instances": [{"InstanceId": "i-0123456789abcdef1"}]},
        ]
    }

    with pytest.raises(MultipleInstancesFoundError) as exc_info:
        get_instance_id("test-instance")
    assert "Multiple instances (2) found" in str(exc_info.value)


def test_get_instance_id_not_found(mocker):
    mock_ec2_client = mocker.patch("remotepy.utils.ec2_client")

    mock_ec2_client.describe_instances.return_value = {"Reservations": []}

    with pytest.raises(InstanceNotFoundError) as exc_info:
        get_instance_id("nonexistent-instance")
    assert "not found" in str(exc_info.value)


def test_get_instance_status_with_id(mocker):
    mock_ec2_client = mocker.patch("remotepy.utils.ec2_client")

    expected_response = {
        "InstanceStatuses": [
            {
                "InstanceId": "i-0123456789abcdef0",
                "InstanceState": {"Name": "running"},
            }
        ]
    }
    mock_ec2_client.describe_instance_status.return_value = expected_response

    result = get_instance_status("i-0123456789abcdef0")

    assert result == expected_response
    mock_ec2_client.describe_instance_status.assert_called_once_with(
        InstanceIds=["i-0123456789abcdef0"]
    )


def test_get_instance_status_without_id(mocker):
    mock_ec2_client = mocker.patch("remotepy.utils.ec2_client")

    expected_response = {"InstanceStatuses": []}
    mock_ec2_client.describe_instance_status.return_value = expected_response

    result = get_instance_status()

    assert result == expected_response
    mock_ec2_client.describe_instance_status.assert_called_once_with()


def test_get_instances(mocker, mock_instances_response):
    mock_ec2_client = mocker.patch("remotepy.utils.ec2_client")

    mock_ec2_client.describe_instances.return_value = mock_instances_response

    result = get_instances()

    assert result == mock_instances_response["Reservations"]
    mock_ec2_client.describe_instances.assert_called_once()


def test_get_instance_dns(mocker):
    mock_ec2_client = mocker.patch("remotepy.utils.ec2_client")

    mock_ec2_client.describe_instances.return_value = {
        "Reservations": [
            {"Instances": [{"PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com"}]}
        ]
    }

    result = get_instance_dns("i-0123456789abcdef0")

    assert result == "ec2-123-45-67-89.compute-1.amazonaws.com"
    mock_ec2_client.describe_instances.assert_called_once_with(InstanceIds=["i-0123456789abcdef0"])


def test_get_instance_name_success(mocker):
    mock_config_manager = mocker.patch("remotepy.config.config_manager")
    mock_config_manager.get_instance_name.return_value = "test-instance"

    result = get_instance_name()

    assert result == "test-instance"
    mock_config_manager.get_instance_name.assert_called_once()


def test_get_instance_name_no_config(mocker):
    mock_config_manager = mocker.patch("remotepy.config.config_manager")
    mock_config_manager.get_instance_name.return_value = None

    with pytest.raises(Exit) as exc_info:
        get_instance_name()
    assert exc_info.value.exit_code == 1


def test_get_instance_info_with_running_instances(mocker, mock_instances_response):
    instances = mock_instances_response["Reservations"]

    names, public_dnss, statuses, instance_types, launch_times = get_instance_info(instances)

    assert names == ["test-instance", "test-instance-2"]
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


def test_get_instance_ids(mock_instances_response):
    instances = mock_instances_response["Reservations"]

    result = get_instance_ids(instances)

    assert result == ["i-0123456789abcdef0", "i-0123456789abcdef1"]


def test_is_instance_running_true(mocker):
    mock_get_instance_status = mocker.patch("remotepy.utils.get_instance_status")
    mock_get_instance_status.return_value = {
        "InstanceStatuses": [{"InstanceState": {"Name": "running"}}]
    }

    result = is_instance_running("i-0123456789abcdef0")

    assert result is True
    mock_get_instance_status.assert_called_once_with("i-0123456789abcdef0")


def test_is_instance_running_false(mocker):
    mock_get_instance_status = mocker.patch("remotepy.utils.get_instance_status")
    mock_get_instance_status.return_value = {
        "InstanceStatuses": [{"InstanceState": {"Name": "stopped"}}]
    }

    result = is_instance_running("i-0123456789abcdef0")

    assert result is False


def test_is_instance_running_no_status(mocker):
    mock_get_instance_status = mocker.patch("remotepy.utils.get_instance_status")
    mock_get_instance_status.return_value = {"InstanceStatuses": []}

    result = is_instance_running("i-0123456789abcdef0")

    assert result is False


def test_is_instance_stopped_true(mocker):
    mock_get_instance_status = mocker.patch("remotepy.utils.get_instance_status")
    mock_get_instance_status.return_value = {
        "InstanceStatuses": [{"InstanceState": {"Name": "stopped"}}]
    }

    result = is_instance_stopped("i-0123456789abcdef0")

    assert result is True


def test_is_instance_stopped_false(mocker):
    mock_get_instance_status = mocker.patch("remotepy.utils.get_instance_status")
    mock_get_instance_status.return_value = {
        "InstanceStatuses": [{"InstanceState": {"Name": "running"}}]
    }

    result = is_instance_stopped("i-0123456789abcdef0")

    assert result is False


def test_get_instance_type(mocker):
    mock_ec2_client = mocker.patch("remotepy.utils.ec2_client")

    mock_ec2_client.describe_instances.return_value = {
        "Reservations": [{"Instances": [{"InstanceType": "t2.micro"}]}]
    }

    result = get_instance_type("i-0123456789abcdef0")

    assert result == "t2.micro"
    mock_ec2_client.describe_instances.assert_called_once_with(InstanceIds=["i-0123456789abcdef0"])


def test_get_volume_ids(mocker):
    mock_ec2_client = mocker.patch("remotepy.utils.ec2_client")

    mock_ec2_client.describe_volumes.return_value = {
        "Volumes": [
            {"VolumeId": "vol-0123456789abcdef0"},
            {"VolumeId": "vol-0123456789abcdef1"},
        ]
    }

    result = get_volume_ids("i-0123456789abcdef0")

    assert result == ["vol-0123456789abcdef0", "vol-0123456789abcdef1"]
    mock_ec2_client.describe_volumes.assert_called_once_with(
        Filters=[{"Name": "attachment.instance-id", "Values": ["i-0123456789abcdef0"]}]
    )


def test_get_volume_name_with_name_tag(mocker):
    mock_ec2_client = mocker.patch("remotepy.utils.ec2_client")

    mock_ec2_client.describe_volumes.return_value = {
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
    mock_ec2_client.describe_volumes.assert_called_once_with(VolumeIds=["vol-0123456789abcdef0"])


def test_get_volume_name_without_name_tag(mocker):
    mock_ec2_client = mocker.patch("remotepy.utils.ec2_client")

    mock_ec2_client.describe_volumes.return_value = {
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
    mock_ec2_client = mocker.patch("remotepy.utils.ec2_client")

    mock_ec2_client.describe_volumes.return_value = {
        "Volumes": [{}]  # No Tags field
    }

    result = get_volume_name("vol-0123456789abcdef0")

    assert result == ""


def test_get_snapshot_status(mocker):
    mock_ec2_client = mocker.patch("remotepy.utils.ec2_client")

    mock_ec2_client.describe_snapshots.return_value = {"Snapshots": [{"State": "completed"}]}

    result = get_snapshot_status("snap-0123456789abcdef0")

    assert result == "completed"
    mock_ec2_client.describe_snapshots.assert_called_once_with(
        SnapshotIds=["snap-0123456789abcdef0"]
    )


def test_get_launch_template_id(mocker):
    mock_ec2_client = mocker.patch("remotepy.utils.ec2_client")

    mock_ec2_client.describe_launch_templates.return_value = {
        "LaunchTemplates": [{"LaunchTemplateId": "lt-0123456789abcdef0"}]
    }

    result = get_launch_template_id("test-template")

    assert result == "lt-0123456789abcdef0"
    mock_ec2_client.describe_launch_templates.assert_called_once_with(
        Filters=[{"Name": "tag:Name", "Values": ["test-template"]}]
    )


# Error path tests for improved coverage

def test_get_account_id_client_error(mocker):
    """Test get_account_id with ClientError."""
    mock_boto3_client = mocker.patch("remotepy.utils.boto3.client")
    mock_sts_client = mock_boto3_client.return_value
    
    error_response = {"Error": {"Code": "AccessDenied", "Message": "Access denied"}}
    mock_sts_client.get_caller_identity.side_effect = ClientError(error_response, "get_caller_identity")
    
    with pytest.raises(AWSServiceError) as exc_info:
        get_account_id()
    
    assert exc_info.value.service == "STS"
    assert exc_info.value.operation == "get_caller_identity"
    assert exc_info.value.aws_error_code == "AccessDenied"


def test_get_account_id_no_credentials_error(mocker):
    """Test get_account_id with NoCredentialsError."""
    mock_boto3_client = mocker.patch("remotepy.utils.boto3.client")
    mock_sts_client = mock_boto3_client.return_value
    
    mock_sts_client.get_caller_identity.side_effect = NoCredentialsError()
    
    with pytest.raises(AWSServiceError) as exc_info:
        get_account_id()
    
    assert exc_info.value.service == "STS"
    assert exc_info.value.operation == "get_caller_identity"
    assert exc_info.value.aws_error_code == "NoCredentials"


def test_get_instance_id_client_error(mocker):
    """Test get_instance_id with ClientError."""
    mock_ec2_client = mocker.patch("remotepy.utils.ec2_client")
    
    error_response = {"Error": {"Code": "UnauthorizedOperation", "Message": "Unauthorized"}}
    mock_ec2_client.describe_instances.side_effect = ClientError(error_response, "describe_instances")
    
    with pytest.raises(AWSServiceError) as exc_info:
        get_instance_id("test-instance")
    
    assert exc_info.value.service == "EC2"
    assert exc_info.value.operation == "describe_instances"
    assert exc_info.value.aws_error_code == "UnauthorizedOperation"


def test_get_instance_id_no_credentials_error(mocker):
    """Test get_instance_id with NoCredentialsError."""
    mock_ec2_client = mocker.patch("remotepy.utils.ec2_client")
    
    mock_ec2_client.describe_instances.side_effect = NoCredentialsError()
    
    with pytest.raises(AWSServiceError) as exc_info:
        get_instance_id("test-instance")
    
    assert exc_info.value.service == "EC2"
    assert exc_info.value.operation == "describe_instances"
    assert exc_info.value.aws_error_code == "NoCredentials"


def test_get_instance_id_no_instances_in_reservation(mocker):
    """Test get_instance_id when reservation has no instances."""
    mock_ec2_client = mocker.patch("remotepy.utils.ec2_client")
    
    mock_ec2_client.describe_instances.return_value = {
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
    mock_ec2_client = mocker.patch("remotepy.utils.ec2_client")
    
    error_response = {"Error": {"Code": "InvalidInstanceID.NotFound", "Message": "Instance not found"}}
    mock_ec2_client.describe_instance_status.side_effect = ClientError(error_response, "describe_instance_status")
    
    with pytest.raises(AWSServiceError) as exc_info:
        get_instance_status("i-12345678")
    
    assert exc_info.value.service == "EC2"
    assert exc_info.value.operation == "describe_instance_status"


def test_get_instance_status_no_credentials_error(mocker):
    """Test get_instance_status with NoCredentialsError."""
    mock_ec2_client = mocker.patch("remotepy.utils.ec2_client")
    
    mock_ec2_client.describe_instance_status.side_effect = NoCredentialsError()
    
    with pytest.raises(AWSServiceError) as exc_info:
        get_instance_status()
    
    assert exc_info.value.aws_error_code == "NoCredentials"


def test_get_instances_client_error(mocker):
    """Test get_instances with ClientError."""
    mock_ec2_client = mocker.patch("remotepy.utils.ec2_client")
    
    error_response = {"Error": {"Code": "RequestLimitExceeded", "Message": "Rate limit exceeded"}}
    mock_ec2_client.describe_instances.side_effect = ClientError(error_response, "describe_instances")
    
    with pytest.raises(AWSServiceError) as exc_info:
        get_instances()
    
    assert exc_info.value.aws_error_code == "RequestLimitExceeded"


def test_get_instances_no_credentials_error(mocker):
    """Test get_instances with NoCredentialsError."""
    mock_ec2_client = mocker.patch("remotepy.utils.ec2_client")
    
    mock_ec2_client.describe_instances.side_effect = NoCredentialsError()
    
    with pytest.raises(AWSServiceError) as exc_info:
        get_instances()
    
    assert exc_info.value.aws_error_code == "NoCredentials"


def test_get_instance_dns_instance_not_found_error(mocker):
    """Test get_instance_dns with instance not found."""
    mock_ec2_client = mocker.patch("remotepy.utils.ec2_client")
    
    error_response = {"Error": {"Code": "InvalidInstanceID.NotFound", "Message": "Instance not found"}}
    mock_ec2_client.describe_instances.side_effect = ClientError(error_response, "describe_instances")
    
    with pytest.raises(ResourceNotFoundError) as exc_info:
        get_instance_dns("i-nonexistent")
    
    assert exc_info.value.resource_type == "Instance"
    assert exc_info.value.resource_id == "i-nonexistent"


def test_get_instance_dns_other_client_error(mocker):
    """Test get_instance_dns with other ClientError."""
    mock_ec2_client = mocker.patch("remotepy.utils.ec2_client")
    
    error_response = {"Error": {"Code": "UnauthorizedOperation", "Message": "Unauthorized"}}
    mock_ec2_client.describe_instances.side_effect = ClientError(error_response, "describe_instances")
    
    with pytest.raises(AWSServiceError) as exc_info:
        get_instance_dns("i-12345678")
    
    assert exc_info.value.aws_error_code == "UnauthorizedOperation"


def test_get_instance_type_instance_not_found_error(mocker):
    """Test get_instance_type with instance not found."""
    mock_ec2_client = mocker.patch("remotepy.utils.ec2_client")
    
    error_response = {"Error": {"Code": "InvalidInstanceID.NotFound", "Message": "Instance not found"}}
    mock_ec2_client.describe_instances.side_effect = ClientError(error_response, "describe_instances")
    
    with pytest.raises(ResourceNotFoundError) as exc_info:
        get_instance_type("i-nonexistent")
    
    assert exc_info.value.resource_type == "Instance"
    assert exc_info.value.resource_id == "i-nonexistent"


def test_get_instance_type_other_client_error(mocker):
    """Test get_instance_type with other ClientError."""
    mock_ec2_client = mocker.patch("remotepy.utils.ec2_client")
    
    error_response = {"Error": {"Code": "UnauthorizedOperation", "Message": "Unauthorized"}}
    mock_ec2_client.describe_instances.side_effect = ClientError(error_response, "describe_instances")
    
    with pytest.raises(AWSServiceError) as exc_info:
        get_instance_type("i-12345678")
    
    assert exc_info.value.aws_error_code == "UnauthorizedOperation"


def test_get_volume_ids_client_error(mocker):
    """Test get_volume_ids with ClientError."""
    mock_ec2_client = mocker.patch("remotepy.utils.ec2_client")
    
    error_response = {"Error": {"Code": "InvalidInstanceID.NotFound", "Message": "Instance not found"}}
    mock_ec2_client.describe_volumes.side_effect = ClientError(error_response, "describe_volumes")
    
    with pytest.raises(AWSServiceError) as exc_info:
        get_volume_ids("i-12345678")
    
    assert exc_info.value.service == "EC2"
    assert exc_info.value.operation == "describe_volumes"


def test_get_volume_ids_no_credentials_error(mocker):
    """Test get_volume_ids with NoCredentialsError."""
    mock_ec2_client = mocker.patch("remotepy.utils.ec2_client")
    
    mock_ec2_client.describe_volumes.side_effect = NoCredentialsError()
    
    with pytest.raises(AWSServiceError) as exc_info:
        get_volume_ids("i-12345678")
    
    assert exc_info.value.aws_error_code == "NoCredentials"


def test_get_volume_name_volume_not_found_error(mocker):
    """Test get_volume_name with volume not found."""
    mock_ec2_client = mocker.patch("remotepy.utils.ec2_client")
    
    error_response = {"Error": {"Code": "InvalidVolumeID.NotFound", "Message": "Volume not found"}}
    mock_ec2_client.describe_volumes.side_effect = ClientError(error_response, "describe_volumes")
    
    with pytest.raises(ResourceNotFoundError) as exc_info:
        get_volume_name("vol-nonexistent")
    
    assert exc_info.value.resource_type == "Volume"
    assert exc_info.value.resource_id == "vol-nonexistent"


def test_get_volume_name_other_client_error(mocker):
    """Test get_volume_name with other ClientError."""
    mock_ec2_client = mocker.patch("remotepy.utils.ec2_client")
    
    error_response = {"Error": {"Code": "UnauthorizedOperation", "Message": "Unauthorized"}}
    mock_ec2_client.describe_volumes.side_effect = ClientError(error_response, "describe_volumes")
    
    with pytest.raises(AWSServiceError) as exc_info:
        get_volume_name("vol-12345678")
    
    assert exc_info.value.aws_error_code == "UnauthorizedOperation"


def test_get_snapshot_status_snapshot_not_found_error(mocker):
    """Test get_snapshot_status with snapshot not found."""
    mock_ec2_client = mocker.patch("remotepy.utils.ec2_client")
    
    error_response = {"Error": {"Code": "InvalidSnapshotID.NotFound", "Message": "Snapshot not found"}}
    mock_ec2_client.describe_snapshots.side_effect = ClientError(error_response, "describe_snapshots")
    
    with pytest.raises(ResourceNotFoundError) as exc_info:
        get_snapshot_status("snap-nonexistent")
    
    assert exc_info.value.resource_type == "Snapshot"
    assert exc_info.value.resource_id == "snap-nonexistent"


def test_get_snapshot_status_other_client_error(mocker):
    """Test get_snapshot_status with other ClientError."""
    mock_ec2_client = mocker.patch("remotepy.utils.ec2_client")
    
    error_response = {"Error": {"Code": "UnauthorizedOperation", "Message": "Unauthorized"}}
    mock_ec2_client.describe_snapshots.side_effect = ClientError(error_response, "describe_snapshots")
    
    with pytest.raises(AWSServiceError) as exc_info:
        get_snapshot_status("snap-12345678")
    
    assert exc_info.value.aws_error_code == "UnauthorizedOperation"


def test_get_launch_template_id_client_error(mocker):
    """Test get_launch_template_id with ClientError."""
    mock_ec2_client = mocker.patch("remotepy.utils.ec2_client")
    
    error_response = {"Error": {"Code": "UnauthorizedOperation", "Message": "Unauthorized"}}
    mock_ec2_client.describe_launch_templates.side_effect = ClientError(error_response, "describe_launch_templates")
    
    with pytest.raises(AWSServiceError) as exc_info:
        get_launch_template_id("test-template")
    
    assert exc_info.value.service == "EC2"
    assert exc_info.value.operation == "describe_launch_templates"
    assert exc_info.value.aws_error_code == "UnauthorizedOperation"


def test_get_launch_template_id_validation_error(mocker):
    """Test get_launch_template_id with empty template name."""
    from remotepy.exceptions import ValidationError
    
    with pytest.raises(ValidationError) as exc_info:
        get_launch_template_id("")
    
    assert "Launch template name cannot be empty" in str(exc_info.value)


def test_get_launch_template_id_no_templates_found(mocker):
    """Test get_launch_template_id when no templates found."""
    mock_ec2_client = mocker.patch("remotepy.utils.ec2_client")
    
    mock_ec2_client.describe_launch_templates.return_value = {
        "LaunchTemplates": []
    }
    
    with pytest.raises(ResourceNotFoundError) as exc_info:
        get_launch_template_id("nonexistent-template")
    
    assert exc_info.value.resource_type == "Launch Template"
    assert exc_info.value.resource_id == "nonexistent-template"
