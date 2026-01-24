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


def test_create_snapshot_missing_volume_id():
    """Should fail with helpful error when volume-id is missing."""
    result = runner.invoke(app, ["create", "--name", "test-snapshot"])

    assert result.exit_code != 0
    # Typer shows missing required options in output (includes stderr)
    output = (result.output or result.stdout).lower()
    assert "volume-id" in output or "missing" in output or "required" in output


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


def test_list_snapshots_instance_not_found(mocker):
    """Test that InstanceNotFoundError exits with code 1."""
    import typer

    mocker.patch(
        "remote.snapshot.resolve_instance_or_exit",
        side_effect=typer.Exit(1),
    )

    result = runner.invoke(app, ["list", "nonexistent"])

    assert result.exit_code == 1


def test_list_snapshots_multiple_instances_found(mocker):
    """Test that MultipleInstancesFoundError exits with code 1."""
    import typer

    mocker.patch(
        "remote.snapshot.resolve_instance_or_exit",
        side_effect=typer.Exit(1),
    )

    result = runner.invoke(app, ["list", "ambiguous"])

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
