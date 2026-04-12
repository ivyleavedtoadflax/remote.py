import datetime

import pytest
from typer.testing import CliRunner

from remote.snapshot import app

runner = CliRunner()


@pytest.fixture
def mock_snapshot_response():
    return {
        "Snapshots": [
            {
                "SnapshotId": "snap-0123456789abcdef0",
                "VolumeId": "vol-0123456789abcdef0",
                "State": "completed",
                "StartTime": datetime.datetime(2023, 7, 15, 0, 0, 0, tzinfo=datetime.timezone.utc),
                "Description": "Test snapshot",
            },
            {
                "SnapshotId": "snap-0123456789abcdef1",
                "VolumeId": "vol-0123456789abcdef0",
                "State": "pending",
                "StartTime": datetime.datetime(2023, 7, 16, 0, 0, 0, tzinfo=datetime.timezone.utc),
                "Description": "Another test snapshot",
            },
        ]
    }


def test_create_snapshot(mocker):
    mock_ec2 = mocker.patch("remote.snapshot.get_ec2_client")
    mock_ec2_client = mock_ec2.return_value

    mock_ec2_client.create_snapshot.return_value = {"SnapshotId": "snap-0123456789abcdef0"}

    result = runner.invoke(
        app,
        [
            "create",
            "--volume-id",
            "vol-0123456789abcdef0",
            "--name",
            "test-snapshot",
            "--description",
            "Test snapshot description",
        ],
        input="y\n",
    )

    assert result.exit_code == 0
    mock_ec2_client.create_snapshot.assert_called_once_with(
        VolumeId="vol-0123456789abcdef0",
        Description="Test snapshot description",
        TagSpecifications=[
            {
                "ResourceType": "snapshot",
                "Tags": [{"Key": "Name", "Value": "test-snapshot"}],
            }
        ],
    )
    assert "Snapshot snap-0123456789abcdef0 created" in result.stdout


def test_create_snapshot_minimal_params(mocker):
    mock_ec2 = mocker.patch("remote.snapshot.get_ec2_client")
    mock_ec2_client = mock_ec2.return_value

    mock_ec2_client.create_snapshot.return_value = {"SnapshotId": "snap-minimal"}

    result = runner.invoke(
        app,
        ["create", "--volume-id", "vol-abcdef12", "--name", "minimal-snapshot"],
        input="y\n",
    )

    assert result.exit_code == 0
    mock_ec2_client.create_snapshot.assert_called_once_with(
        VolumeId="vol-abcdef12",
        Description="",
        TagSpecifications=[
            {
                "ResourceType": "snapshot",
                "Tags": [{"Key": "Name", "Value": "minimal-snapshot"}],
            }
        ],
    )


def test_create_snapshot_cancelled(mocker):
    """Test that declining confirmation cancels snapshot creation."""
    mocker.patch("remote.snapshot.get_ec2_client")

    result = runner.invoke(
        app,
        ["create", "--volume-id", "vol-abcdef12", "--name", "test-snapshot"],
        input="n\n",
    )

    assert result.exit_code == 0
    assert "Snapshot creation cancelled" in result.stdout


def test_create_snapshot_with_yes_flag(mocker):
    """Test that --yes flag skips confirmation."""
    mock_ec2 = mocker.patch("remote.snapshot.get_ec2_client")
    mock_ec2_client = mock_ec2.return_value

    mock_ec2_client.create_snapshot.return_value = {"SnapshotId": "snap-0123456789abcdef0"}

    result = runner.invoke(
        app,
        [
            "create",
            "--volume-id",
            "vol-0123456789abcdef0",
            "--name",
            "test-snapshot",
            "--yes",
        ],
    )

    assert result.exit_code == 0
    mock_ec2_client.create_snapshot.assert_called_once()
    assert "Snapshot snap-0123456789abcdef0 created" in result.stdout


def test_create_snapshot_no_instance_or_volume():
    """Should fail when neither instance name nor --volume-id is provided."""
    result = runner.invoke(app, ["create", "--name", "test-snapshot"])

    assert result.exit_code != 0
    output = (result.output or result.stdout).lower()
    assert "volume-id" in output or "instance" in output or "required" in output


def test_create_snapshot_missing_name():
    """Should fail with helpful error when name is missing."""
    result = runner.invoke(app, ["create", "--volume-id", "vol-abcdef12"])

    assert result.exit_code != 0
    # Typer shows missing required options in output (includes stderr)
    output = (result.output or result.stdout).lower()
    assert "name" in output or "missing" in output or "required" in output


def test_create_snapshot_invalid_volume_id():
    """Should fail with validation error for invalid volume ID format."""
    result = runner.invoke(
        app, ["create", "--volume-id", "invalid-volume-id", "--name", "test-snapshot"]
    )

    assert result.exit_code == 1
    assert "Error:" in result.stdout
    assert "Invalid volume_id" in result.stdout
    assert "vol-" in result.stdout


@pytest.mark.parametrize(
    "instance_name,scenario",
    [
        ("nonexistent", "InstanceNotFoundError"),
        ("ambiguous", "MultipleInstancesFoundError"),
    ],
)
def test_list_snapshots_instance_resolution_error(mocker, instance_name, scenario):
    """Test that instance resolution errors exit with code 1."""
    import typer

    mocker.patch(
        "remote.snapshot.resolve_instance_or_exit",
        side_effect=typer.Exit(1),
    )

    result = runner.invoke(app, ["list", instance_name])

    assert result.exit_code == 1


@pytest.mark.parametrize("command", ["list", "ls"])
def test_list_snapshots_with_instance_name(mocker, mock_snapshot_response, command):
    """Test both list and ls commands work for listing snapshots."""
    mock_ec2 = mocker.patch("remote.snapshot.get_ec2_client")
    mock_ec2_client = mock_ec2.return_value
    mock_resolve_instance = mocker.patch(
        "remote.snapshot.resolve_instance_or_exit",
        return_value=("test-instance", "i-0123456789abcdef0"),
    )
    mock_get_volume_ids = mocker.patch(
        "remote.snapshot.get_volume_ids", return_value=["vol-0123456789abcdef0"]
    )

    mock_ec2_client.describe_snapshots.return_value = mock_snapshot_response

    result = runner.invoke(app, [command, "test-instance"])

    assert result.exit_code == 0
    mock_resolve_instance.assert_called_once_with("test-instance")
    mock_get_volume_ids.assert_called_once_with("i-0123456789abcdef0")
    mock_ec2_client.describe_snapshots.assert_called_once_with(
        Filters=[{"Name": "volume-id", "Values": ["vol-0123456789abcdef0"]}]
    )

    assert "snap-0123456789abcdef0" in result.stdout
    assert "snap-0123456789abcdef1" in result.stdout
    assert "Test snapshot" in result.stdout
    assert "completed" in result.stdout
    assert "pending" in result.stdout


def test_list_snapshots_without_instance_name(mocker, mock_snapshot_response):
    mock_ec2 = mocker.patch("remote.snapshot.get_ec2_client")
    mock_ec2_client = mock_ec2.return_value
    mock_resolve_instance = mocker.patch(
        "remote.snapshot.resolve_instance_or_exit",
        return_value=("default-instance", "i-0123456789abcdef0"),
    )
    mock_get_volume_ids = mocker.patch(
        "remote.snapshot.get_volume_ids", return_value=["vol-0123456789abcdef0"]
    )

    mock_ec2_client.describe_snapshots.return_value = mock_snapshot_response

    result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    mock_resolve_instance.assert_called_once_with(None)
    mock_get_volume_ids.assert_called_once_with("i-0123456789abcdef0")


def test_list_snapshots_multiple_volumes(mocker):
    mock_ec2 = mocker.patch("remote.snapshot.get_ec2_client")
    mock_ec2_client = mock_ec2.return_value
    mocker.patch(
        "remote.snapshot.resolve_instance_or_exit",
        return_value=("test-instance", "i-0123456789abcdef0"),
    )
    mocker.patch(
        "remote.snapshot.get_volume_ids",
        return_value=["vol-0123456789abcdef0", "vol-0123456789abcdef1"],
    )

    # Mock different responses for different volume IDs
    def mock_describe_snapshots(Filters):
        volume_id = Filters[0]["Values"][0]
        if volume_id == "vol-0123456789abcdef0":
            return {
                "Snapshots": [
                    {
                        "SnapshotId": "snap-vol1",
                        "VolumeId": "vol-0123456789abcdef0",
                        "State": "completed",
                        "StartTime": datetime.datetime(
                            2023, 7, 15, 0, 0, 0, tzinfo=datetime.timezone.utc
                        ),
                        "Description": "Snapshot for vol1",
                    }
                ]
            }
        else:
            return {
                "Snapshots": [
                    {
                        "SnapshotId": "snap-vol2",
                        "VolumeId": "vol-0123456789abcdef1",
                        "State": "pending",
                        "StartTime": datetime.datetime(
                            2023, 7, 16, 0, 0, 0, tzinfo=datetime.timezone.utc
                        ),
                        "Description": "Snapshot for vol2",
                    }
                ]
            }

    mock_ec2_client.describe_snapshots.side_effect = mock_describe_snapshots

    result = runner.invoke(app, ["list", "test-instance"])

    assert result.exit_code == 0
    assert mock_ec2_client.describe_snapshots.call_count == 2

    assert "snap-vol1" in result.stdout
    assert "snap-vol2" in result.stdout
    assert "vol-0123456789abcdef0" in result.stdout
    assert "vol-0123456789abcdef1" in result.stdout


def test_list_snapshots_no_snapshots(mocker):
    mock_ec2 = mocker.patch("remote.snapshot.get_ec2_client")
    mock_ec2_client = mock_ec2.return_value
    mocker.patch(
        "remote.snapshot.resolve_instance_or_exit",
        return_value=("test-instance", "i-0123456789abcdef0"),
    )
    mocker.patch("remote.snapshot.get_volume_ids", return_value=["vol-0123456789abcdef0"])

    mock_ec2_client.describe_snapshots.return_value = {"Snapshots": []}

    result = runner.invoke(app, ["list", "test-instance"])

    assert result.exit_code == 0

    # Should show headers but no snapshot data
    assert "SnapshotId" in result.stdout
    assert "VolumeId" in result.stdout
    assert "State" in result.stdout


# ============================================================================
# Instance-based snapshot creation tests
# ============================================================================


def test_create_snapshot_from_instance_single_volume(mocker):
    """Test creating a snapshot with instance name and a single attached volume."""
    mock_ec2 = mocker.patch("remote.snapshot.get_ec2_client")
    mock_ec2_client = mock_ec2.return_value
    mocker.patch(
        "remote.snapshot.resolve_instance_or_exit",
        return_value=("my-instance", "i-abc123"),
    )
    mocker.patch(
        "remote.snapshot.get_volumes_for_instance",
        return_value=[
            {
                "VolumeId": "vol-111",
                "Attachments": [
                    {"InstanceId": "i-abc123", "Device": "/dev/sda1", "State": "attached"}
                ],
            }
        ],
    )
    mock_ec2_client.create_snapshot.return_value = {"SnapshotId": "snap-new1"}

    result = runner.invoke(
        app,
        ["create", "my-instance", "--name", "my-snapshot", "--yes"],
    )

    assert result.exit_code == 0
    mock_ec2_client.create_snapshot.assert_called_once_with(
        VolumeId="vol-111",
        Description="",
        TagSpecifications=[
            {"ResourceType": "snapshot", "Tags": [{"Key": "Name", "Value": "my-snapshot"}]}
        ],
    )
    assert "snap-new1" in result.stdout
    assert "vol-111" in result.stdout


def test_create_snapshot_from_instance_multiple_volumes(mocker):
    """Test creating snapshots for all volumes attached to an instance."""
    mock_ec2 = mocker.patch("remote.snapshot.get_ec2_client")
    mock_ec2_client = mock_ec2.return_value
    mocker.patch(
        "remote.snapshot.resolve_instance_or_exit",
        return_value=("my-instance", "i-abc123"),
    )
    mocker.patch(
        "remote.snapshot.get_volumes_for_instance",
        return_value=[
            {
                "VolumeId": "vol-111",
                "Attachments": [
                    {"InstanceId": "i-abc123", "Device": "/dev/sda1", "State": "attached"}
                ],
            },
            {
                "VolumeId": "vol-222",
                "Attachments": [
                    {"InstanceId": "i-abc123", "Device": "/dev/sdf", "State": "attached"}
                ],
            },
        ],
    )
    mock_ec2_client.create_snapshot.side_effect = [
        {"SnapshotId": "snap-new1"},
        {"SnapshotId": "snap-new2"},
    ]

    result = runner.invoke(
        app,
        ["create", "my-instance", "--name", "backup", "--yes"],
    )

    assert result.exit_code == 0
    assert mock_ec2_client.create_snapshot.call_count == 2

    # First call: root volume gets name with device suffix
    first_call = mock_ec2_client.create_snapshot.call_args_list[0]
    assert first_call.kwargs["VolumeId"] == "vol-111"
    assert first_call.kwargs["TagSpecifications"][0]["Tags"][0]["Value"] == "backup-sda1"

    # Second call: data volume gets name with device suffix
    second_call = mock_ec2_client.create_snapshot.call_args_list[1]
    assert second_call.kwargs["VolumeId"] == "vol-222"
    assert second_call.kwargs["TagSpecifications"][0]["Tags"][0]["Value"] == "backup-sdf"

    assert "snap-new1" in result.stdout
    assert "snap-new2" in result.stdout


def test_create_snapshot_from_instance_with_device_filter(mocker):
    """Test --device filters to only the matching volume."""
    mock_ec2 = mocker.patch("remote.snapshot.get_ec2_client")
    mock_ec2_client = mock_ec2.return_value
    mocker.patch(
        "remote.snapshot.resolve_instance_or_exit",
        return_value=("my-instance", "i-abc123"),
    )
    mocker.patch(
        "remote.snapshot.get_volumes_for_instance",
        return_value=[
            {
                "VolumeId": "vol-111",
                "Attachments": [
                    {"InstanceId": "i-abc123", "Device": "/dev/sda1", "State": "attached"}
                ],
            },
            {
                "VolumeId": "vol-222",
                "Attachments": [
                    {"InstanceId": "i-abc123", "Device": "/dev/sdf", "State": "attached"}
                ],
            },
        ],
    )
    mock_ec2_client.create_snapshot.return_value = {"SnapshotId": "snap-data"}

    result = runner.invoke(
        app,
        ["create", "my-instance", "--device", "/dev/sdf", "--name", "data-snapshot", "--yes"],
    )

    assert result.exit_code == 0
    # Only the matching volume should be snapshotted
    mock_ec2_client.create_snapshot.assert_called_once_with(
        VolumeId="vol-222",
        Description="",
        TagSpecifications=[
            {"ResourceType": "snapshot", "Tags": [{"Key": "Name", "Value": "data-snapshot"}]}
        ],
    )
    assert "snap-data" in result.stdout


def test_create_snapshot_from_instance_with_confirmation(mocker):
    """Test that instance-based snapshot creation prompts for confirmation."""
    mock_ec2 = mocker.patch("remote.snapshot.get_ec2_client")
    mock_ec2_client = mock_ec2.return_value
    mocker.patch(
        "remote.snapshot.resolve_instance_or_exit",
        return_value=("my-instance", "i-abc123"),
    )
    mocker.patch(
        "remote.snapshot.get_volumes_for_instance",
        return_value=[
            {
                "VolumeId": "vol-111",
                "Attachments": [
                    {"InstanceId": "i-abc123", "Device": "/dev/sda1", "State": "attached"}
                ],
            },
        ],
    )
    mock_ec2_client.create_snapshot.return_value = {"SnapshotId": "snap-confirmed"}

    result = runner.invoke(
        app,
        ["create", "my-instance", "--name", "my-snap"],
        input="y\n",
    )

    assert result.exit_code == 0
    mock_ec2_client.create_snapshot.assert_called_once()
    assert "snap-confirmed" in result.stdout


def test_create_snapshot_from_instance_cancelled(mocker):
    """Test that declining confirmation cancels instance-based snapshot creation."""
    mocker.patch("remote.snapshot.get_ec2_client")
    mocker.patch(
        "remote.snapshot.resolve_instance_or_exit",
        return_value=("my-instance", "i-abc123"),
    )
    mocker.patch(
        "remote.snapshot.get_volumes_for_instance",
        return_value=[
            {
                "VolumeId": "vol-111",
                "Attachments": [
                    {"InstanceId": "i-abc123", "Device": "/dev/sda1", "State": "attached"}
                ],
            },
        ],
    )

    result = runner.invoke(
        app,
        ["create", "my-instance", "--name", "my-snap"],
        input="n\n",
    )

    assert result.exit_code == 0
    assert "cancelled" in result.stdout


def test_create_snapshot_no_volumes_for_instance(mocker):
    """Test error when instance has no attached volumes."""
    mocker.patch("remote.snapshot.get_ec2_client")
    mocker.patch(
        "remote.snapshot.resolve_instance_or_exit",
        return_value=("my-instance", "i-abc123"),
    )
    mocker.patch("remote.snapshot.get_volumes_for_instance", return_value=[])

    result = runner.invoke(
        app,
        ["create", "my-instance", "--name", "my-snap", "--yes"],
    )

    assert result.exit_code == 1
    assert "No volumes" in result.stdout


def test_create_snapshot_device_not_found(mocker):
    """Test error when --device doesn't match any attached volume."""
    mocker.patch("remote.snapshot.get_ec2_client")
    mocker.patch(
        "remote.snapshot.resolve_instance_or_exit",
        return_value=("my-instance", "i-abc123"),
    )
    mocker.patch(
        "remote.snapshot.get_volumes_for_instance",
        return_value=[
            {
                "VolumeId": "vol-111",
                "Attachments": [
                    {"InstanceId": "i-abc123", "Device": "/dev/sda1", "State": "attached"}
                ],
            },
        ],
    )

    result = runner.invoke(
        app,
        ["create", "my-instance", "--device", "/dev/sdf", "--name", "my-snap", "--yes"],
    )

    assert result.exit_code == 1
    assert "No volume with device /dev/sdf" in result.stdout


def test_create_snapshot_mutually_exclusive_options(mocker):
    """Test error when both --volume-id and instance name are provided."""
    mocker.patch("remote.snapshot.get_ec2_client")

    result = runner.invoke(
        app,
        ["create", "my-instance", "--volume-id", "vol-123", "--name", "my-snap", "--yes"],
    )

    assert result.exit_code == 1
    assert "mutually exclusive" in result.stdout


def test_create_snapshot_neither_volume_nor_instance():
    """Test error when neither instance name nor --volume-id is provided."""
    result = runner.invoke(
        app,
        ["create", "--name", "my-snap", "--yes"],
    )

    assert result.exit_code == 1
    assert "Either" in result.stdout and "required" in result.stdout


def test_create_snapshot_device_without_instance():
    """Test error when --device is used without an instance name."""
    result = runner.invoke(
        app,
        ["create", "--volume-id", "vol-123", "--device", "/dev/sdf", "--name", "my-snap", "--yes"],
    )

    assert result.exit_code == 1
    assert "--device can only be used with" in result.stdout


def test_create_snapshot_from_instance_with_description(mocker):
    """Test that --description is passed through for instance-based snapshots."""
    mock_ec2 = mocker.patch("remote.snapshot.get_ec2_client")
    mock_ec2_client = mock_ec2.return_value
    mocker.patch(
        "remote.snapshot.resolve_instance_or_exit",
        return_value=("my-instance", "i-abc123"),
    )
    mocker.patch(
        "remote.snapshot.get_volumes_for_instance",
        return_value=[
            {
                "VolumeId": "vol-111",
                "Attachments": [
                    {"InstanceId": "i-abc123", "Device": "/dev/sda1", "State": "attached"}
                ],
            },
        ],
    )
    mock_ec2_client.create_snapshot.return_value = {"SnapshotId": "snap-desc"}

    result = runner.invoke(
        app,
        [
            "create",
            "my-instance",
            "--name",
            "my-snap",
            "--description",
            "Baseline snapshot",
            "--yes",
        ],
    )

    assert result.exit_code == 0
    mock_ec2_client.create_snapshot.assert_called_once_with(
        VolumeId="vol-111",
        Description="Baseline snapshot",
        TagSpecifications=[
            {"ResourceType": "snapshot", "Tags": [{"Key": "Name", "Value": "my-snap"}]}
        ],
    )


def test_create_snapshot_instance_resolution_error(mocker):
    """Test that instance resolution errors exit with code 1 during create."""
    import typer

    mocker.patch("remote.snapshot.get_ec2_client")
    mocker.patch(
        "remote.snapshot.resolve_instance_or_exit",
        side_effect=typer.Exit(1),
    )

    result = runner.invoke(
        app,
        ["create", "nonexistent-instance", "--name", "my-snap", "--yes"],
    )

    assert result.exit_code == 1


def test_create_snapshot_partial_failure(mocker):
    """Test that partial failure reports successes and failures."""
    from remote.exceptions import AWSServiceError

    mock_ec2 = mocker.patch("remote.snapshot.get_ec2_client")
    mock_ec2_client = mock_ec2.return_value
    mocker.patch(
        "remote.snapshot.resolve_instance_or_exit",
        return_value=("my-instance", "i-abc123"),
    )
    mocker.patch(
        "remote.snapshot.get_volumes_for_instance",
        return_value=[
            {
                "VolumeId": "vol-111",
                "Attachments": [
                    {"InstanceId": "i-abc123", "Device": "/dev/sda1", "State": "attached"}
                ],
            },
            {
                "VolumeId": "vol-222",
                "Attachments": [
                    {"InstanceId": "i-abc123", "Device": "/dev/sdf", "State": "attached"}
                ],
            },
            {
                "VolumeId": "vol-333",
                "Attachments": [
                    {"InstanceId": "i-abc123", "Device": "/dev/sdg", "State": "attached"}
                ],
            },
        ],
    )

    # First succeeds, second fails, third succeeds
    mock_ec2_client.create_snapshot.side_effect = [
        {"SnapshotId": "snap-ok1"},
        AWSServiceError("EC2", "create_snapshot", "InternalError", "Something went wrong"),
        {"SnapshotId": "snap-ok3"},
    ]

    result = runner.invoke(
        app,
        ["create", "my-instance", "--name", "backup", "--yes"],
    )

    assert result.exit_code == 1
    # First and third should succeed
    assert "snap-ok1" in result.stdout
    assert "snap-ok3" in result.stdout
    # Should report the failure
    assert "Failed" in result.stdout
    assert "vol-222" in result.stdout
    # Should show summary
    assert "2 snapshot(s) created" in result.stdout
    assert "1 failed" in result.stdout
