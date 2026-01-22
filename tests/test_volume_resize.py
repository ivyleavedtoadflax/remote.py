import pytest
from typer.testing import CliRunner

from remote.volume import app

runner = CliRunner()


@pytest.fixture
def mock_volume_response():
    """Mock response with a single root volume attached to instance."""
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
                "Tags": [{"Key": "Name", "Value": "root-volume"}],
            },
        ]
    }


@pytest.fixture
def mock_modify_volume_response():
    """Mock response from modify_volume."""
    return {
        "VolumeModification": {
            "VolumeId": "vol-0123456789abcdef0",
            "ModificationState": "modifying",
            "TargetSize": 20,
            "OriginalSize": 8,
        }
    }


class TestResizeCommand:
    """Tests for the volume resize command."""

    def test_resize_requires_size_argument(self, mocker):
        """Test that resize command requires --size argument."""
        mocker.patch(
            "remote.volume.resolve_instance_or_exit",
            return_value=("test-instance", "i-0123456789abcdef0"),
        )

        result = runner.invoke(app, ["resize", "test-instance"])

        assert result.exit_code != 0
        # Typer outputs required option errors to output (combined stdout/stderr)
        assert "size" in result.output.lower()

    def test_resize_instance_not_found(self, mocker):
        """Test that resize handles instance not found."""
        import typer

        mocker.patch(
            "remote.volume.resolve_instance_or_exit",
            side_effect=typer.Exit(1),
        )

        result = runner.invoke(app, ["resize", "nonexistent", "--size", "20"])

        assert result.exit_code == 1

    def test_resize_no_volumes_attached(self, mocker):
        """Test that resize fails when no volumes attached."""
        mock_ec2 = mocker.patch("remote.volume.get_ec2_client")
        mock_ec2_client = mock_ec2.return_value
        mocker.patch(
            "remote.volume.resolve_instance_or_exit",
            return_value=("test-instance", "i-0123456789abcdef0"),
        )
        mock_ec2_client.describe_volumes.return_value = {"Volumes": []}

        result = runner.invoke(app, ["resize", "test-instance", "--size", "20"])

        assert result.exit_code == 1
        assert "no volume" in result.stdout.lower() or "no root" in result.stdout.lower()

    def test_resize_success(self, mocker, mock_volume_response, mock_modify_volume_response):
        """Test successful volume resize."""
        mock_ec2 = mocker.patch("remote.volume.get_ec2_client")
        mock_ec2_client = mock_ec2.return_value
        mocker.patch(
            "remote.volume.resolve_instance_or_exit",
            return_value=("test-instance", "i-0123456789abcdef0"),
        )
        mock_ec2_client.describe_volumes.return_value = mock_volume_response
        mock_ec2_client.modify_volume.return_value = mock_modify_volume_response

        result = runner.invoke(app, ["resize", "test-instance", "--size", "20", "--yes"])

        assert result.exit_code == 0
        mock_ec2_client.modify_volume.assert_called_once_with(
            VolumeId="vol-0123456789abcdef0",
            Size=20,
        )
        assert "vol-0123456789abcdef0" in result.stdout
        assert "20" in result.stdout

    def test_resize_prompts_for_confirmation(self, mocker, mock_volume_response):
        """Test that resize prompts for confirmation without --yes."""
        mock_ec2 = mocker.patch("remote.volume.get_ec2_client")
        mock_ec2_client = mock_ec2.return_value
        mocker.patch(
            "remote.volume.resolve_instance_or_exit",
            return_value=("test-instance", "i-0123456789abcdef0"),
        )
        mock_ec2_client.describe_volumes.return_value = mock_volume_response

        # User declines
        result = runner.invoke(app, ["resize", "test-instance", "--size", "20"], input="n\n")

        assert result.exit_code == 1
        mock_ec2_client.modify_volume.assert_not_called()

    def test_resize_confirmation_accepted(
        self, mocker, mock_volume_response, mock_modify_volume_response
    ):
        """Test that resize proceeds when user confirms."""
        mock_ec2 = mocker.patch("remote.volume.get_ec2_client")
        mock_ec2_client = mock_ec2.return_value
        mocker.patch(
            "remote.volume.resolve_instance_or_exit",
            return_value=("test-instance", "i-0123456789abcdef0"),
        )
        mock_ec2_client.describe_volumes.return_value = mock_volume_response
        mock_ec2_client.modify_volume.return_value = mock_modify_volume_response

        result = runner.invoke(app, ["resize", "test-instance", "--size", "20"], input="y\n")

        assert result.exit_code == 0
        mock_ec2_client.modify_volume.assert_called_once()

    def test_resize_rejects_smaller_size(self, mocker, mock_volume_response):
        """Test that resize rejects size smaller than current."""
        mock_ec2 = mocker.patch("remote.volume.get_ec2_client")
        mock_ec2_client = mock_ec2.return_value
        mocker.patch(
            "remote.volume.resolve_instance_or_exit",
            return_value=("test-instance", "i-0123456789abcdef0"),
        )
        mock_ec2_client.describe_volumes.return_value = mock_volume_response

        result = runner.invoke(app, ["resize", "test-instance", "--size", "5", "--yes"])

        assert result.exit_code == 1
        assert "smaller" in result.stdout.lower() or "must be greater" in result.stdout.lower()
        mock_ec2_client.modify_volume.assert_not_called()

    def test_resize_rejects_same_size(self, mocker, mock_volume_response):
        """Test that resize rejects same size as current."""
        mock_ec2 = mocker.patch("remote.volume.get_ec2_client")
        mock_ec2_client = mock_ec2.return_value
        mocker.patch(
            "remote.volume.resolve_instance_or_exit",
            return_value=("test-instance", "i-0123456789abcdef0"),
        )
        mock_ec2_client.describe_volumes.return_value = mock_volume_response

        result = runner.invoke(app, ["resize", "test-instance", "--size", "8", "--yes"])

        assert result.exit_code == 1
        assert "already" in result.stdout.lower() or "same" in result.stdout.lower()
        mock_ec2_client.modify_volume.assert_not_called()

    def test_resize_uses_default_instance(
        self, mocker, mock_volume_response, mock_modify_volume_response
    ):
        """Test that resize uses default instance when none specified."""
        mock_ec2 = mocker.patch("remote.volume.get_ec2_client")
        mock_ec2_client = mock_ec2.return_value
        mock_resolve = mocker.patch(
            "remote.volume.resolve_instance_or_exit",
            return_value=("default-instance", "i-0123456789abcdef0"),
        )
        mock_ec2_client.describe_volumes.return_value = mock_volume_response
        mock_ec2_client.modify_volume.return_value = mock_modify_volume_response

        result = runner.invoke(app, ["resize", "--size", "20", "--yes"])

        assert result.exit_code == 0
        mock_resolve.assert_called_once_with(None)

    def test_resize_selects_root_volume(self, mocker, mock_modify_volume_response):
        """Test that resize selects the root volume when multiple volumes attached."""
        mock_ec2 = mocker.patch("remote.volume.get_ec2_client")
        mock_ec2_client = mock_ec2.return_value
        mocker.patch(
            "remote.volume.resolve_instance_or_exit",
            return_value=("test-instance", "i-0123456789abcdef0"),
        )
        # Multiple volumes - root (/dev/sda1) and data (/dev/sdb)
        mock_ec2_client.describe_volumes.return_value = {
            "Volumes": [
                {
                    "VolumeId": "vol-0123456789abcdef1",
                    "Size": 100,
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
                {
                    "VolumeId": "vol-0123456789abcdef2",
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
            ]
        }
        mock_ec2_client.modify_volume.return_value = mock_modify_volume_response

        result = runner.invoke(app, ["resize", "test-instance", "--size", "20", "--yes"])

        assert result.exit_code == 0
        mock_ec2_client.modify_volume.assert_called_once_with(
            VolumeId="vol-0123456789abcdef2",
            Size=20,
        )

    def test_resize_handles_nvme_root_device(self, mocker, mock_modify_volume_response):
        """Test that resize identifies NVMe root devices."""
        mock_ec2 = mocker.patch("remote.volume.get_ec2_client")
        mock_ec2_client = mock_ec2.return_value
        mocker.patch(
            "remote.volume.resolve_instance_or_exit",
            return_value=("test-instance", "i-0123456789abcdef0"),
        )
        mock_ec2_client.describe_volumes.return_value = {
            "Volumes": [
                {
                    "VolumeId": "vol-nvme-root",
                    "Size": 8,
                    "State": "in-use",
                    "AvailabilityZone": "us-east-1a",
                    "Attachments": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "Device": "/dev/xvda",
                            "State": "attached",
                        }
                    ],
                    "Tags": [],
                },
            ]
        }
        mock_ec2_client.modify_volume.return_value = mock_modify_volume_response

        result = runner.invoke(app, ["resize", "test-instance", "--size", "20", "--yes"])

        assert result.exit_code == 0
        mock_ec2_client.modify_volume.assert_called_once_with(
            VolumeId="vol-nvme-root",
            Size=20,
        )

    def test_resize_with_volume_id_option(self, mocker, mock_modify_volume_response):
        """Test that resize can target specific volume by ID."""
        mock_ec2 = mocker.patch("remote.volume.get_ec2_client")
        mock_ec2_client = mock_ec2.return_value
        mocker.patch(
            "remote.volume.resolve_instance_or_exit",
            return_value=("test-instance", "i-0123456789abcdef0"),
        )
        # Multiple volumes
        mock_ec2_client.describe_volumes.return_value = {
            "Volumes": [
                {
                    "VolumeId": "vol-0123456789abcdef2",
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
                    "VolumeId": "vol-0123456789abcdef3",
                    "Size": 100,
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
        mock_ec2_client.modify_volume.return_value = {
            "VolumeModification": {
                "VolumeId": "vol-0123456789abcdef3",
                "ModificationState": "modifying",
                "TargetSize": 200,
                "OriginalSize": 100,
            }
        }

        result = runner.invoke(
            app,
            [
                "resize",
                "test-instance",
                "--size",
                "200",
                "--volume",
                "vol-0123456789abcdef3",
                "--yes",
            ],
        )

        assert result.exit_code == 0
        mock_ec2_client.modify_volume.assert_called_once_with(
            VolumeId="vol-0123456789abcdef3",
            Size=200,
        )
