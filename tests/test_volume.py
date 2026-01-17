import pytest
from typer.testing import CliRunner

from remote.volume import app

runner = CliRunner()


@pytest.fixture
def mock_volume_response():
    return {
        "Volumes": [
            {
                "VolumeId": "vol-0123456789abcdef0",
                "Size": 8,
                "State": "in-use",
                "AvailabilityZone": "us-east-1a",
                "Attachments": [
                    {
                        "InstanceId": "i-0123456789abcdef0",
                        "Device": "/dev/sda1",
                        "State": "attached",
                    }
                ],
                "Tags": [{"Key": "Name", "Value": "test-volume"}],
            },
            {
                "VolumeId": "vol-0123456789abcdef1",
                "Size": 10,
                "State": "available",
                "AvailabilityZone": "us-east-1b",
                "Attachments": [],
                "Tags": [],
            },
        ]
    }


def test_list_volumes_with_instance_name(mocker, mock_volume_response):
    mock_ec2 = mocker.patch("remote.volume.get_ec2_client")
    mock_ec2_client = mock_ec2.return_value
    mock_get_instance_id = mocker.patch(
        "remote.volume.get_instance_id", return_value="i-0123456789abcdef0"
    )
    mock_get_volume_name = mocker.patch("remote.volume.get_volume_name", return_value="test-volume")

    mock_ec2_client.describe_volumes.return_value = mock_volume_response

    result = runner.invoke(app, ["list", "test-instance"])

    assert result.exit_code == 0
    mock_get_instance_id.assert_called_once_with("test-instance")
    mock_ec2_client.describe_volumes.assert_called_once()
    mock_get_volume_name.assert_called_once_with("vol-0123456789abcdef0")

    assert "test-instance" in result.stdout
    assert "vol-0123456789abcdef0" in result.stdout
    assert "test-volume" in result.stdout


def test_list_volumes_without_instance_name(mocker, mock_volume_response):
    mock_ec2 = mocker.patch("remote.volume.get_ec2_client")
    mock_ec2_client = mock_ec2.return_value
    mock_get_instance_name = mocker.patch(
        "remote.volume.get_instance_name", return_value="default-instance"
    )
    mock_get_instance_id = mocker.patch(
        "remote.volume.get_instance_id", return_value="i-0123456789abcdef0"
    )
    mocker.patch("remote.volume.get_volume_name", return_value="test-volume")

    mock_ec2_client.describe_volumes.return_value = mock_volume_response

    result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    mock_get_instance_name.assert_called_once()
    mock_get_instance_id.assert_called_once_with("default-instance")
    mock_ec2_client.describe_volumes.assert_called_once()


def test_list_volumes_no_attachments(mocker):
    mock_ec2 = mocker.patch("remote.volume.get_ec2_client")
    mock_ec2_client = mock_ec2.return_value
    mock_get_instance_id = mocker.patch(
        "remote.volume.get_instance_id", return_value="i-0123456789abcdef0"
    )

    # Volume with no attachments to our instance
    mock_ec2_client.describe_volumes.return_value = {
        "Volumes": [
            {
                "VolumeId": "vol-unattached",
                "Size": 5,
                "State": "available",
                "AvailabilityZone": "us-east-1a",
                "Attachments": [],
                "Tags": [],
            }
        ]
    }

    result = runner.invoke(app, ["list", "test-instance"])

    assert result.exit_code == 0
    mock_get_instance_id.assert_called_once_with("test-instance")
    mock_ec2_client.describe_volumes.assert_called_once()

    # Should show headers but no volume data since no volumes are attached to our instance
    assert "Instance Name" in result.stdout
    assert "VolumeId" in result.stdout
    assert "vol-unattached" not in result.stdout


def test_list_volumes_multiple_attachments(mocker):
    mock_ec2 = mocker.patch("remote.volume.get_ec2_client")
    mock_ec2_client = mock_ec2.return_value
    mocker.patch("remote.volume.get_instance_id", return_value="i-0123456789abcdef0")
    mocker.patch("remote.volume.get_volume_name", side_effect=["vol1-name", "vol2-name"])

    # Multiple volumes attached to the same instance
    mock_ec2_client.describe_volumes.return_value = {
        "Volumes": [
            {
                "VolumeId": "vol-0123456789abcdef0",
                "Size": 8,
                "State": "in-use",
                "AvailabilityZone": "us-east-1a",
                "Attachments": [
                    {
                        "InstanceId": "i-0123456789abcdef0",
                        "Device": "/dev/sda1",
                        "State": "attached",
                    }
                ],
                "Tags": [],
            },
            {
                "VolumeId": "vol-0123456789abcdef1",
                "Size": 10,
                "State": "in-use",
                "AvailabilityZone": "us-east-1a",
                "Attachments": [
                    {
                        "InstanceId": "i-0123456789abcdef0",
                        "Device": "/dev/sdb",
                        "State": "attached",
                    }
                ],
                "Tags": [],
            },
        ]
    }

    result = runner.invoke(app, ["list", "test-instance"])

    assert result.exit_code == 0
    assert "vol-0123456789abcdef0" in result.stdout
    assert "vol-0123456789abcdef1" in result.stdout
    assert "vol1-name" in result.stdout
    assert "vol2-name" in result.stdout


def test_list_command_alias_ls(mocker, mock_volume_response):
    mock_ec2 = mocker.patch("remote.volume.get_ec2_client")
    mock_ec2_client = mock_ec2.return_value
    mock_get_instance_id = mocker.patch(
        "remote.volume.get_instance_id", return_value="i-0123456789abcdef0"
    )
    mocker.patch("remote.volume.get_volume_name", return_value="test-volume")

    mock_ec2_client.describe_volumes.return_value = mock_volume_response

    result = runner.invoke(app, ["ls", "test-instance"])

    assert result.exit_code == 0
    mock_get_instance_id.assert_called_once_with("test-instance")
    mock_ec2_client.describe_volumes.assert_called_once()
