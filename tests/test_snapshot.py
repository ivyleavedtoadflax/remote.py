import datetime

import pytest
from typer.testing import CliRunner

from remotepy.snapshot import app

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
    mock_ec2_client = mocker.patch("remotepy.snapshot.ec2_client", autospec=True)

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
    mock_ec2_client = mocker.patch("remotepy.snapshot.ec2_client", autospec=True)

    mock_ec2_client.create_snapshot.return_value = {"SnapshotId": "snap-minimal"}

    result = runner.invoke(app, ["create", "--volume-id", "vol-test", "--name", "minimal-snapshot"])

    assert result.exit_code == 0
    mock_ec2_client.create_snapshot.assert_called_once_with(
        VolumeId="vol-test",
        Description="",
        TagSpecifications=[
            {
                "ResourceType": "snapshot",
                "Tags": [{"Key": "Name", "Value": "minimal-snapshot"}],
            }
        ],
    )


def test_create_snapshot_missing_volume_id():
    """Should fail with helpful error when volume-id is missing."""
    result = runner.invoke(app, ["create", "--name", "test-snapshot"])

    assert result.exit_code != 0
    # Typer shows missing required options in output (includes stderr)
    output = (result.output or result.stdout).lower()
    assert "volume-id" in output or "missing" in output or "required" in output


def test_create_snapshot_missing_name():
    """Should fail with helpful error when name is missing."""
    result = runner.invoke(app, ["create", "--volume-id", "vol-test"])

    assert result.exit_code != 0
    # Typer shows missing required options in output (includes stderr)
    output = (result.output or result.stdout).lower()
    assert "name" in output or "missing" in output or "required" in output


def test_list_snapshots_with_instance_name(mocker, mock_snapshot_response):
    mock_ec2_client = mocker.patch("remotepy.snapshot.ec2_client", autospec=True)
    mock_get_instance_id = mocker.patch(
        "remotepy.snapshot.get_instance_id", return_value="i-0123456789abcdef0"
    )
    mock_get_volume_ids = mocker.patch(
        "remotepy.snapshot.get_volume_ids", return_value=["vol-0123456789abcdef0"]
    )

    mock_ec2_client.describe_snapshots.return_value = mock_snapshot_response

    result = runner.invoke(app, ["list", "test-instance"])

    assert result.exit_code == 0
    mock_get_instance_id.assert_called_once_with("test-instance")
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
    mock_ec2_client = mocker.patch("remotepy.snapshot.ec2_client", autospec=True)
    mock_get_instance_name = mocker.patch(
        "remotepy.snapshot.get_instance_name", return_value="default-instance"
    )
    mock_get_instance_id = mocker.patch(
        "remotepy.snapshot.get_instance_id", return_value="i-0123456789abcdef0"
    )
    mock_get_volume_ids = mocker.patch(
        "remotepy.snapshot.get_volume_ids", return_value=["vol-0123456789abcdef0"]
    )

    mock_ec2_client.describe_snapshots.return_value = mock_snapshot_response

    result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    mock_get_instance_name.assert_called_once()
    mock_get_instance_id.assert_called_once_with("default-instance")
    mock_get_volume_ids.assert_called_once_with("i-0123456789abcdef0")


def test_list_snapshots_multiple_volumes(mocker):
    mock_ec2_client = mocker.patch("remotepy.snapshot.ec2_client", autospec=True)
    mocker.patch("remotepy.snapshot.get_instance_id", return_value="i-0123456789abcdef0")
    mocker.patch(
        "remotepy.snapshot.get_volume_ids",
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
    mock_ec2_client = mocker.patch("remotepy.snapshot.ec2_client", autospec=True)
    mocker.patch("remotepy.snapshot.get_instance_id", return_value="i-0123456789abcdef0")
    mocker.patch("remotepy.snapshot.get_volume_ids", return_value=["vol-0123456789abcdef0"])

    mock_ec2_client.describe_snapshots.return_value = {"Snapshots": []}

    result = runner.invoke(app, ["list", "test-instance"])

    assert result.exit_code == 0

    # Should show headers but no snapshot data
    assert "SnapshotId" in result.stdout
    assert "VolumeId" in result.stdout
    assert "State" in result.stdout


def test_list_command_alias_ls(mocker, mock_snapshot_response):
    mock_ec2_client = mocker.patch("remotepy.snapshot.ec2_client", autospec=True)
    mock_get_instance_id = mocker.patch(
        "remotepy.snapshot.get_instance_id", return_value="i-0123456789abcdef0"
    )
    mock_get_volume_ids = mocker.patch(
        "remotepy.snapshot.get_volume_ids", return_value=["vol-0123456789abcdef0"]
    )

    mock_ec2_client.describe_snapshots.return_value = mock_snapshot_response

    result = runner.invoke(app, ["ls", "test-instance"])

    assert result.exit_code == 0
    mock_get_instance_id.assert_called_once_with("test-instance")
    mock_get_volume_ids.assert_called_once_with("i-0123456789abcdef0")
