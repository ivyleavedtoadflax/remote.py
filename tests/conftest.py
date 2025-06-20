"""Shared test configuration and fixtures."""

import configparser
import datetime
from unittest.mock import MagicMock, patch

import pytest

from remotepy.settings import Settings


@pytest.fixture(autouse=True)
def test_config():
    """Automatically use test configuration for all tests.

    This fixture ensures that tests don't depend on the user's local configuration
    and provides sensible defaults for testing.
    """
    test_settings = Settings(testing_mode=True, mock_aws_calls=True)

    # Create a mock config manager that returns test instance name
    mock_config_manager = MagicMock()
    mock_config_manager.get_instance_name.return_value = "test-instance"

    # Mock the global settings object and config manager
    with patch("remotepy.settings.settings", test_settings):
        with patch("remotepy.config.config_manager", mock_config_manager):
            yield test_settings


@pytest.fixture
def test_config_file(tmpdir):
    """Create a temporary config file for testing."""
    config_path = tmpdir.join("config.ini")
    cfg = configparser.ConfigParser()
    cfg["DEFAULT"] = {"instance_name": "test-instance"}

    with open(config_path, "w") as f:
        cfg.write(f)

    return str(config_path)


# ============================================================================
# Comprehensive AWS Mock Data Fixtures
# ============================================================================

@pytest.fixture
def mock_ec2_instances():
    """Standard mock EC2 instances data for testing."""
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
                            {"Key": "Name", "Value": "test-instance-1"},
                            {"Key": "Environment", "Value": "testing"},
                        ],
                    }
                ]
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
                    }
                ]
            },
        ]
    }


@pytest.fixture
def mock_ecs_clusters():
    """Standard mock ECS clusters data for testing."""
    return {
        "clusterArns": [
            "arn:aws:ecs:us-east-1:123456789012:cluster/test-cluster-1",
            "arn:aws:ecs:us-east-1:123456789012:cluster/test-cluster-2",
        ]
    }


@pytest.fixture
def mock_ecs_services():
    """Standard mock ECS services data for testing."""
    return {
        "serviceArns": [
            "arn:aws:ecs:us-east-1:123456789012:service/test-cluster/test-service-1",
            "arn:aws:ecs:us-east-1:123456789012:service/test-cluster/test-service-2",
        ]
    }


@pytest.fixture
def mock_ebs_volumes():
    """Standard mock EBS volumes data for testing."""
    return {
        "Volumes": [
            {
                "VolumeId": "vol-0123456789abcdef0",
                "Size": 20,
                "VolumeType": "gp3",
                "State": "in-use",
                "Attachments": [
                    {
                        "InstanceId": "i-0123456789abcdef0",
                        "Device": "/dev/sda1",
                        "State": "attached",
                    }
                ],
                "Tags": [
                    {"Key": "Name", "Value": "test-volume-1"},
                ],
            },
            {
                "VolumeId": "vol-0123456789abcdef1",
                "Size": 50,
                "VolumeType": "gp3",
                "State": "available",
                "Attachments": [],
                "Tags": [
                    {"Key": "Name", "Value": "test-volume-2"},
                ],
            },
        ]
    }


@pytest.fixture
def mock_ebs_snapshots():
    """Standard mock EBS snapshots data for testing."""
    return {
        "Snapshots": [
            {
                "SnapshotId": "snap-0123456789abcdef0",
                "VolumeId": "vol-0123456789abcdef0",
                "State": "completed",
                "Progress": "100%",
                "StartTime": datetime.datetime(2023, 7, 15, 0, 0, 0, tzinfo=datetime.UTC),
                "Description": "Test snapshot 1",
                "Tags": [
                    {"Key": "Name", "Value": "test-snapshot-1"},
                ],
            },
            {
                "SnapshotId": "snap-0123456789abcdef1", 
                "VolumeId": "vol-0123456789abcdef1",
                "State": "pending",
                "Progress": "50%",
                "StartTime": datetime.datetime(2023, 7, 16, 0, 0, 0, tzinfo=datetime.UTC),
                "Description": "Test snapshot 2",
                "Tags": [
                    {"Key": "Name", "Value": "test-snapshot-2"},
                ],
            },
        ]
    }


@pytest.fixture
def mock_amis():
    """Standard mock AMI data for testing."""
    return {
        "Images": [
            {
                "ImageId": "ami-0123456789abcdef0",
                "Name": "test-ami-1",
                "State": "available",
                "CreationDate": datetime.datetime(2023, 7, 15, 0, 0, 0, tzinfo=datetime.UTC),
                "Description": "Test AMI 1",
                "Tags": [
                    {"Key": "Name", "Value": "test-ami-1"},
                ],
            },
            {
                "ImageId": "ami-0123456789abcdef1",
                "Name": "test-ami-2", 
                "State": "pending",
                "CreationDate": datetime.datetime(2023, 7, 16, 0, 0, 0, tzinfo=datetime.UTC),
                "Description": "Test AMI 2",
                "Tags": [
                    {"Key": "Name", "Value": "test-ami-2"},
                ],
            },
        ]
    }


@pytest.fixture
def mock_launch_templates():
    """Standard mock Launch Template data for testing."""
    return {
        "LaunchTemplates": [
            {
                "LaunchTemplateId": "lt-0123456789abcdef0",
                "LaunchTemplateName": "test-template-1",
                "LatestVersionNumber": 2,
                "Tags": [
                    {"Key": "Name", "Value": "test-template-1"},
                ],
            },
            {
                "LaunchTemplateId": "lt-0123456789abcdef1",
                "LaunchTemplateName": "test-template-2",
                "LatestVersionNumber": 1,
                "Tags": [
                    {"Key": "Name", "Value": "test-template-2"},
                ],
            },
        ]
    }


# ============================================================================
# Comprehensive AWS Client Mocking
# ============================================================================

@pytest.fixture
def mock_aws_clients(mocker):
    """Mock all AWS clients used in the application with comprehensive responses."""
    # Mock EC2 client with comprehensive default responses
    mock_ec2 = mocker.patch("remotepy.utils.ec2_client", autospec=True)
    mock_ec2.describe_instances.return_value = {"Reservations": []}
    mock_ec2.describe_volumes.return_value = {"Volumes": []}
    mock_ec2.describe_snapshots.return_value = {"Snapshots": []}
    mock_ec2.describe_images.return_value = {"Images": []}
    mock_ec2.describe_launch_templates.return_value = {"LaunchTemplates": []}
    mock_ec2.describe_instance_status.return_value = {"InstanceStatuses": []}
    mock_ec2.start_instances.return_value = {"StartingInstances": []}
    mock_ec2.stop_instances.return_value = {"StoppingInstances": []}
    mock_ec2.terminate_instances.return_value = {"TerminatingInstances": []}
    mock_ec2.run_instances.return_value = {"Instances": [{"InstanceId": "i-new123"}]}
    mock_ec2.create_image.return_value = {"ImageId": "ami-new123"}
    mock_ec2.create_snapshot.return_value = {"SnapshotId": "snap-new123"}
    mock_ec2.modify_instance_attribute.return_value = {}

    # Mock ECS client with comprehensive default responses
    mock_ecs = mocker.patch("remotepy.ecs.ecs_client", autospec=True)
    mock_ecs.list_clusters.return_value = {"clusterArns": []}
    mock_ecs.list_services.return_value = {"serviceArns": []}
    mock_ecs.update_service.return_value = {}

    # Mock STS client for account ID
    mock_sts = mocker.patch("boto3.client")
    mock_sts_instance = MagicMock()
    mock_sts_instance.get_caller_identity.return_value = {"Account": "123456789012"}
    mock_sts.return_value = mock_sts_instance

    return {"ec2": mock_ec2, "ecs": mock_ecs, "sts": mock_sts}


@pytest.fixture
def populated_aws_clients(mocker, mock_ec2_instances, mock_ecs_clusters, mock_ecs_services,
                          mock_ebs_volumes, mock_ebs_snapshots, mock_amis, mock_launch_templates):
    """Mock AWS clients with realistic populated data for comprehensive testing."""
    # Mock EC2 client with populated responses
    mock_ec2 = mocker.patch("remotepy.utils.ec2_client", autospec=True)
    mock_ec2.describe_instances.return_value = mock_ec2_instances
    mock_ec2.describe_volumes.return_value = mock_ebs_volumes
    mock_ec2.describe_snapshots.return_value = mock_ebs_snapshots
    mock_ec2.describe_images.return_value = mock_amis
    mock_ec2.describe_launch_templates.return_value = mock_launch_templates
    mock_ec2.describe_instance_status.return_value = {
        "InstanceStatuses": [
            {
                "InstanceId": "i-0123456789abcdef0",
                "InstanceState": {"Name": "running"},
                "SystemStatus": {"Status": "ok"},
                "InstanceStatus": {
                    "Status": "ok",
                    "Details": [{"Status": "passed"}]
                },
            }
        ]
    }

    # Mock ECS client with populated responses
    mock_ecs = mocker.patch("remotepy.ecs.ecs_client", autospec=True) 
    mock_ecs.list_clusters.return_value = mock_ecs_clusters
    mock_ecs.list_services.return_value = mock_ecs_services

    # Mock STS client
    mock_sts = mocker.patch("boto3.client")
    mock_sts_instance = MagicMock()
    mock_sts_instance.get_caller_identity.return_value = {"Account": "123456789012"}
    mock_sts.return_value = mock_sts_instance

    return {"ec2": mock_ec2, "ecs": mock_ecs, "sts": mock_sts}


# ============================================================================
# Utility Test Fixtures
# ============================================================================

@pytest.fixture
def aws_account_id():
    """Standard AWS account ID for testing."""
    return "123456789012"


@pytest.fixture
def aws_region():
    """Standard AWS region for testing."""
    return "us-east-1"


@pytest.fixture
def sample_instance_ids():
    """Sample instance IDs for testing."""
    return ["i-0123456789abcdef0", "i-0123456789abcdef1"]


@pytest.fixture
def sample_volume_ids():
    """Sample volume IDs for testing."""
    return ["vol-0123456789abcdef0", "vol-0123456789abcdef1"]


@pytest.fixture
def sample_snapshot_ids():
    """Sample snapshot IDs for testing."""
    return ["snap-0123456789abcdef0", "snap-0123456789abcdef1"]
