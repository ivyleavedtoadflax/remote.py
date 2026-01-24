import pytest
from typer.testing import CliRunner

from remote.volume import app

runner = CliRunner()


@pytest.fixture
def mock_volume_response():
    """Mock response from describe_volumes with server-side filter.

    This fixture simulates the response when filtering by attachment.instance-id,
    so it only contains volumes attached to the target instance.
    """
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
        ]
    }


@pytest.mark.parametrize(
    "instance_name,scenario",
    [
        ("nonexistent", "InstanceNotFoundError"),
        ("ambiguous", "MultipleInstancesFoundError"),
    ],
)
def test_list_volumes_instance_resolution_error(mocker, instance_name, scenario):
    """Test that instance resolution errors exit with code 1."""
    import typer

    mocker.patch(
        "remote.volume.resolve_instance_or_exit",
        side_effect=typer.Exit(1),
    )

    result = runner.invoke(app, ["list", instance_name])

    assert result.exit_code == 1


@pytest.mark.parametrize("command", ["list", "ls"])
def test_list_volumes_with_instance_name(mocker, mock_volume_response, command):
    """Test both list and ls commands work for listing volumes."""
    mock_ec2 = mocker.patch("remote.volume.get_ec2_client")
    mock_ec2_client = mock_ec2.return_value
    mock_resolve_instance = mocker.patch(
        "remote.volume.resolve_instance_or_exit",
        return_value=("test-instance", "i-0123456789abcdef0"),
    )
    mock_get_volume_name = mocker.patch("remote.volume.get_volume_name", return_value="test-volume")

    mock_ec2_client.describe_volumes.return_value = mock_volume_response

    result = runner.invoke(app, [command, "test-instance"])

    assert result.exit_code == 0
    mock_resolve_instance.assert_called_once_with("test-instance")
    mock_ec2_client.describe_volumes.assert_called_once_with(
        Filters=[{"Name": "attachment.instance-id", "Values": ["i-0123456789abcdef0"]}]
    )
    mock_get_volume_name.assert_called_once_with("vol-0123456789abcdef0")

    assert "test-instance" in result.stdout
    assert "vol-0123456789abcdef0" in result.stdout
    assert "test-volume" in result.stdout


def test_list_volumes_without_instance_name(mocker, mock_volume_response):
    mock_ec2 = mocker.patch("remote.volume.get_ec2_client")
    mock_ec2_client = mock_ec2.return_value
    mock_resolve_instance = mocker.patch(
        "remote.volume.resolve_instance_or_exit",
        return_value=("default-instance", "i-0123456789abcdef0"),
    )
    mocker.patch("remote.volume.get_volume_name", return_value="test-volume")

    mock_ec2_client.describe_volumes.return_value = mock_volume_response

    result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    mock_resolve_instance.assert_called_once_with(None)
    mock_ec2_client.describe_volumes.assert_called_once_with(
        Filters=[{"Name": "attachment.instance-id", "Values": ["i-0123456789abcdef0"]}]
    )


def test_list_volumes_no_attachments(mocker):
    mock_ec2 = mocker.patch("remote.volume.get_ec2_client")
    mock_ec2_client = mock_ec2.return_value
    mock_resolve_instance = mocker.patch(
        "remote.volume.resolve_instance_or_exit",
        return_value=("test-instance", "i-0123456789abcdef0"),
    )

    # Server-side filter returns empty list when no volumes attached to instance
    mock_ec2_client.describe_volumes.return_value = {"Volumes": []}

    result = runner.invoke(app, ["list", "test-instance"])

    assert result.exit_code == 0
    mock_resolve_instance.assert_called_once_with("test-instance")
    mock_ec2_client.describe_volumes.assert_called_once_with(
        Filters=[{"Name": "attachment.instance-id", "Values": ["i-0123456789abcdef0"]}]
    )

    # Should show headers but no volume data since no volumes are attached to our instance
    assert "Instance Name" in result.stdout
    assert "VolumeId" in result.stdout


def test_list_volumes_multiple_attachments(mocker):
    mock_ec2 = mocker.patch("remote.volume.get_ec2_client")
    mock_ec2_client = mock_ec2.return_value
    mocker.patch(
        "remote.volume.resolve_instance_or_exit",
        return_value=("test-instance", "i-0123456789abcdef0"),
    )
    mocker.patch("remote.volume.get_volume_name", side_effect=["vol1-name", "vol2-name"])

    # Multiple volumes attached to the same instance (returned by server-side filter)
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
    mock_ec2_client.describe_volumes.assert_called_once_with(
        Filters=[{"Name": "attachment.instance-id", "Values": ["i-0123456789abcdef0"]}]
    )
    assert "vol-0123456789abcdef0" in result.stdout
    assert "vol-0123456789abcdef1" in result.stdout
    assert "vol1-name" in result.stdout
    assert "vol2-name" in result.stdout
