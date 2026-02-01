import datetime

import pytest
import typer
from typer.testing import CliRunner

from remote.ami import app
from remote.utils import get_launch_template_id

runner = CliRunner()


@pytest.fixture
def mock_ami_response():
    return {
        "Images": [
            {
                "ImageId": "ami-0123456789abcdef0",
                "Name": "test-ami-1",
                "State": "available",
                "CreationDate": datetime.datetime(
                    2023, 7, 15, 0, 0, 0, tzinfo=datetime.timezone.utc
                ),
            },
            {
                "ImageId": "ami-0123456789abcdef1",
                "Name": "test-ami-2",
                "State": "pending",
                "CreationDate": datetime.datetime(
                    2023, 7, 16, 0, 0, 0, tzinfo=datetime.timezone.utc
                ),
            },
        ]
    }


@pytest.fixture
def mock_launch_template_response():
    return {
        "LaunchTemplates": [
            {
                "LaunchTemplateId": "lt-0123456789abcdef0",
                "LaunchTemplateName": "test-template-1",
                "LatestVersionNumber": 2,
            },
            {
                "LaunchTemplateId": "lt-0123456789abcdef1",
                "LaunchTemplateName": "test-template-2",
                "LatestVersionNumber": 1,
            },
        ]
    }


def test_create_ami_with_instance_name(mocker):
    mock_ec2_client = mocker.patch("remote.ami.get_ec2_client")
    mock_resolve_instance = mocker.patch(
        "remote.ami.resolve_instance_or_exit",
        return_value=("test-instance", "i-0123456789abcdef0"),
    )

    mock_ec2_client.return_value.create_image.return_value = {"ImageId": "ami-0123456789abcdef0"}

    result = runner.invoke(
        app,
        [
            "create",
            "test-instance",
            "--name",
            "test-ami",
            "--description",
            "Test AMI description",
        ],
        input="y\n",
    )

    assert result.exit_code == 0
    mock_resolve_instance.assert_called_once_with("test-instance")
    mock_ec2_client.return_value.create_image.assert_called_once_with(
        InstanceId="i-0123456789abcdef0",
        Name="test-ami",
        Description="Test AMI description",
        NoReboot=True,
    )
    assert "AMI ami-0123456789abcdef0 created" in result.stdout


def test_create_ami_without_instance_name(mocker):
    mock_ec2_client = mocker.patch("remote.ami.get_ec2_client")
    mock_resolve_instance = mocker.patch(
        "remote.ami.resolve_instance_or_exit",
        return_value=("default-instance", "i-0123456789abcdef0"),
    )

    mock_ec2_client.return_value.create_image.return_value = {"ImageId": "ami-default"}

    result = runner.invoke(app, ["create", "--name", "test-ami"], input="y\n")

    assert result.exit_code == 0
    mock_resolve_instance.assert_called_once_with(None)


def test_create_ami_minimal_params(mocker):
    mock_ec2_client = mocker.patch("remote.ami.get_ec2_client")
    mocker.patch(
        "remote.ami.resolve_instance_or_exit",
        return_value=("default-instance", "i-0123456789abcdef0"),
    )

    mock_ec2_client.return_value.create_image.return_value = {"ImageId": "ami-minimal"}

    result = runner.invoke(app, ["create"], input="y\n")

    assert result.exit_code == 0
    # When no name/description provided, defaults are used
    mock_ec2_client.return_value.create_image.assert_called_once_with(
        InstanceId="i-0123456789abcdef0",
        Name="ami-default-instance",  # Default name based on instance name
        Description="",  # Empty string as default
        NoReboot=True,
    )


def test_create_ami_cancelled(mocker):
    """Test that declining confirmation cancels AMI creation."""
    mocker.patch("remote.ami.get_ec2_client")
    mocker.patch(
        "remote.ami.resolve_instance_or_exit",
        return_value=("test-instance", "i-0123456789abcdef0"),
    )

    result = runner.invoke(app, ["create", "test-instance", "--name", "test-ami"], input="n\n")

    assert result.exit_code == 0
    assert "AMI creation cancelled" in result.stdout


def test_create_ami_with_yes_flag(mocker):
    """Test that --yes flag skips confirmation."""
    mock_ec2_client = mocker.patch("remote.ami.get_ec2_client")
    mocker.patch(
        "remote.ami.resolve_instance_or_exit",
        return_value=("test-instance", "i-0123456789abcdef0"),
    )

    mock_ec2_client.return_value.create_image.return_value = {"ImageId": "ami-0123456789abcdef0"}

    result = runner.invoke(
        app,
        ["create", "test-instance", "--name", "test-ami", "--yes"],
    )

    assert result.exit_code == 0
    mock_ec2_client.return_value.create_image.assert_called_once()
    assert "AMI ami-0123456789abcdef0 created" in result.stdout


@pytest.mark.parametrize(
    "instance_name,scenario",
    [
        ("nonexistent", "InstanceNotFoundError"),
        ("ambiguous", "MultipleInstancesFoundError"),
    ],
)
def test_create_ami_instance_resolution_error(mocker, instance_name, scenario):
    """Test that instance resolution errors exit with code 1."""
    mocker.patch(
        "remote.ami.resolve_instance_or_exit",
        side_effect=typer.Exit(1),
    )

    result = runner.invoke(app, ["create", instance_name, "--yes"])

    assert result.exit_code == 1


@pytest.mark.parametrize("command", ["list", "ls"])
def test_list_amis(mocker, mock_ami_response, command):
    """Test both list and ls commands work for listing AMIs."""
    mock_ec2_client = mocker.patch("remote.ami.get_ec2_client")
    mock_get_account_id = mocker.patch("remote.ami.get_account_id", return_value="123456789012")

    # Mock paginator for describe_images
    mock_paginator = mocker.MagicMock()
    mock_paginator.paginate.return_value = [mock_ami_response]
    mock_ec2_client.return_value.get_paginator.return_value = mock_paginator

    result = runner.invoke(app, [command])

    assert result.exit_code == 0
    mock_get_account_id.assert_called_once()
    mock_ec2_client.return_value.get_paginator.assert_called_once_with("describe_images")
    mock_paginator.paginate.assert_called_once_with(Owners=["123456789012"])

    assert "ami-0123456789abcdef0" in result.stdout
    assert "ami-0123456789abcdef1" in result.stdout
    assert "test-ami-1" in result.stdout
    assert "test-ami-2" in result.stdout
    assert "available" in result.stdout
    assert "pending" in result.stdout


def test_list_amis_empty(mocker):
    mock_ec2_client = mocker.patch("remote.ami.get_ec2_client")
    mocker.patch("remote.ami.get_account_id", return_value="123456789012")

    # Mock paginator for describe_images with empty result
    mock_paginator = mocker.MagicMock()
    mock_paginator.paginate.return_value = [{"Images": []}]
    mock_ec2_client.return_value.get_paginator.return_value = mock_paginator

    result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    # Should show headers but no AMI data
    assert "ImageId" in result.stdout
    assert "Name" in result.stdout


def test_list_amis_pagination_multiple_pages(mocker):
    """Test that list_amis correctly handles multiple pages of results."""
    mock_ec2_client = mocker.patch("remote.ami.get_ec2_client")
    mocker.patch("remote.ami.get_account_id", return_value="123456789012")

    # Create multiple pages of AMI results
    page1 = {
        "Images": [
            {
                "ImageId": "ami-page1-001",
                "Name": "ami-from-page-1",
                "State": "available",
                "CreationDate": "2024-01-01T00:00:00Z",
            }
        ]
    }
    page2 = {
        "Images": [
            {
                "ImageId": "ami-page2-001",
                "Name": "ami-from-page-2",
                "State": "available",
                "CreationDate": "2024-01-02T00:00:00Z",
            }
        ]
    }

    # Mock paginator to return multiple pages
    mock_paginator = mocker.MagicMock()
    mock_paginator.paginate.return_value = [page1, page2]
    mock_ec2_client.return_value.get_paginator.return_value = mock_paginator

    result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    # Verify AMIs from both pages are in output
    assert "ami-page1-001" in result.stdout
    assert "ami-from-page-1" in result.stdout
    assert "ami-page2-001" in result.stdout
    assert "ami-from-page-2" in result.stdout


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


def test_list_launch_templates(mocker, mock_launch_template_response):
    mocker.patch(
        "remote.ami.get_launch_templates",
        return_value=mock_launch_template_response["LaunchTemplates"],
    )

    result = runner.invoke(app, ["list-templates"])

    assert result.exit_code == 0
    assert "lt-0123456789abcdef0" in result.stdout
    assert "lt-0123456789abcdef1" in result.stdout
    assert "test-template-1" in result.stdout
    assert "test-template-2" in result.stdout


def test_list_launch_templates_empty(mocker):
    mocker.patch("remote.ami.get_launch_templates", return_value=[])

    result = runner.invoke(app, ["list-templates"])

    assert result.exit_code == 0
    assert "No launch templates found" in result.stdout


def test_list_launch_templates_with_details(mocker):
    """Test list-templates with --details flag showing version info."""
    templates = [
        {
            "LaunchTemplateId": "lt-123",
            "LaunchTemplateName": "my-template",
            "LatestVersionNumber": 2,
            "CreateTime": "2024-01-01",
        }
    ]
    versions = [
        {
            "VersionNumber": 2,
            "LaunchTemplateData": {
                "InstanceType": "t3.micro",
                "ImageId": "ami-12345",
                "KeyName": "my-key",
                "SecurityGroupIds": ["sg-123", "sg-456"],
            },
        }
    ]
    mocker.patch("remote.ami.get_launch_templates", return_value=templates)
    mocker.patch("remote.ami.get_launch_template_versions", return_value=versions)

    result = runner.invoke(app, ["list-templates", "--details"])

    assert result.exit_code == 0
    assert "my-template" in result.stdout
    assert "lt-" in result.stdout and "123" in result.stdout
    assert "Latest Version:" in result.stdout
    assert "t3.micro" in result.stdout
    assert "ami-" in result.stdout
    assert "my-key" in result.stdout
    assert "sg-" in result.stdout


def test_list_launch_templates_with_details_no_versions(mocker):
    """Test list-templates with --details when versions retrieval fails."""
    from remote.exceptions import ResourceNotFoundError

    templates = [
        {
            "LaunchTemplateId": "lt-123",
            "LaunchTemplateName": "my-template",
            "LatestVersionNumber": 1,
            "CreateTime": "2024-01-01",
        }
    ]
    mocker.patch("remote.ami.get_launch_templates", return_value=templates)
    mocker.patch(
        "remote.ami.get_launch_template_versions",
        side_effect=ResourceNotFoundError("Template", "lt-123"),
    )

    result = runner.invoke(app, ["list-templates", "--details"])

    assert result.exit_code == 0
    assert "my-template" in result.stdout


def test_template_versions_success(mocker):
    """Test template-versions command with valid template."""
    versions = [
        {
            "VersionNumber": 2,
            "CreateTime": "2024-01-15",
            "VersionDescription": "Latest version",
            "DefaultVersion": True,
        },
        {
            "VersionNumber": 1,
            "CreateTime": "2024-01-01",
            "VersionDescription": "Initial version",
            "DefaultVersion": False,
        },
    ]
    mocker.patch("remote.ami.get_launch_template_versions", return_value=versions)

    result = runner.invoke(app, ["template-versions", "my-template"])

    assert result.exit_code == 0
    assert "Versions for my-template" in result.stdout
    assert "Latest version" in result.stdout
    assert "Initial version" in result.stdout


def test_template_versions_not_found(mocker):
    """Test template-versions when template doesn't exist."""
    from remote.exceptions import ResourceNotFoundError

    mocker.patch(
        "remote.ami.get_launch_template_versions",
        side_effect=ResourceNotFoundError("Template", "missing-template"),
    )

    result = runner.invoke(app, ["template-versions", "missing-template"])

    assert result.exit_code == 1
    assert "not found" in result.stdout


def test_template_versions_empty(mocker):
    """Test template-versions when no versions exist."""
    mocker.patch("remote.ami.get_launch_template_versions", return_value=[])

    result = runner.invoke(app, ["template-versions", "my-template"])

    assert result.exit_code == 0
    assert "No versions found" in result.stdout


def test_template_info_success(mocker):
    """Test template-info command showing detailed info."""
    versions = [
        {
            "VersionNumber": 2,
            "VersionDescription": "Production config",
            "CreateTime": "2024-01-15",
            "LaunchTemplateData": {
                "InstanceType": "t3.large",
                "ImageId": "ami-prod",
                "KeyName": "prod-key",
                "SecurityGroupIds": ["sg-prod"],
                "NetworkInterfaces": [{"SubnetId": "subnet-123"}],
                "BlockDeviceMappings": [
                    {
                        "DeviceName": "/dev/sda1",
                        "Ebs": {"VolumeSize": 100, "VolumeType": "gp3"},
                    }
                ],
            },
        }
    ]
    mocker.patch("remote.ami.get_launch_template_versions", return_value=versions)

    result = runner.invoke(app, ["template-info", "my-template"])

    assert result.exit_code == 0
    assert "my-template" in result.stdout
    assert "t3.large" in result.stdout
    assert "ami-prod" in result.stdout
    assert "prod-key" in result.stdout
    assert "sg-prod" in result.stdout
    assert "subnet-" in result.stdout and "123" in result.stdout
    assert "100" in result.stdout
    assert "gp3" in result.stdout


def test_template_info_specific_version(mocker):
    """Test template-info with specific version number."""
    versions = [
        {
            "VersionNumber": 2,
            "LaunchTemplateData": {"InstanceType": "t3.large"},
        },
        {
            "VersionNumber": 1,
            "LaunchTemplateData": {"InstanceType": "t3.micro"},
        },
    ]
    mocker.patch("remote.ami.get_launch_template_versions", return_value=versions)

    result = runner.invoke(app, ["template-info", "my-template", "-V", "1"])

    assert result.exit_code == 0
    assert "t3.micro" in result.stdout


def test_template_info_version_not_found(mocker):
    """Test template-info when specific version doesn't exist."""
    versions = [
        {
            "VersionNumber": 1,
            "LaunchTemplateData": {"InstanceType": "t3.micro"},
        }
    ]
    mocker.patch("remote.ami.get_launch_template_versions", return_value=versions)

    result = runner.invoke(app, ["template-info", "my-template", "-V", "99"])

    assert result.exit_code == 1
    assert "Version 99 not found" in result.stdout


def test_template_info_not_found(mocker):
    """Test template-info when template doesn't exist."""
    from remote.exceptions import ResourceNotFoundError

    mocker.patch(
        "remote.ami.get_launch_template_versions",
        side_effect=ResourceNotFoundError("Template", "missing"),
    )

    result = runner.invoke(app, ["template-info", "missing"])

    assert result.exit_code == 1
    assert "not found" in result.stdout


def test_template_info_no_versions(mocker):
    """Test template-info when no versions exist."""
    mocker.patch("remote.ami.get_launch_template_versions", return_value=[])

    result = runner.invoke(app, ["template-info", "my-template"])

    assert result.exit_code == 0
    assert "No versions found" in result.stdout


class TestCreateTemplateCommand:
    """Tests for the create-template command."""

    def test_should_create_template_with_all_options(self, mocker):
        """Should create launch template with all required options."""
        mock_ec2 = mocker.patch("remote.ami.get_ec2_client")
        mock_ec2.return_value.create_launch_template.return_value = {
            "LaunchTemplate": {"LaunchTemplateId": "lt-0123456789abcdef0"}
        }

        result = runner.invoke(
            app,
            [
                "create-template",
                "my-template",
                "--ami",
                "ami-03446a3af42c5e74e",
                "--instance-type",
                "t3.small",
                "--key-name",
                "my-key",
                "--yes",
            ],
        )

        assert result.exit_code == 0
        assert "Created launch template" in result.stdout
        assert "my-template" in result.stdout
        assert "lt-0123456789abcdef0" in result.stdout

        mock_ec2.return_value.create_launch_template.assert_called_once_with(
            LaunchTemplateName="my-template",
            LaunchTemplateData={
                "ImageId": "ami-03446a3af42c5e74e",
                "InstanceType": "t3.small",
                "KeyName": "my-key",
            },
            TagSpecifications=[
                {
                    "ResourceType": "launch-template",
                    "Tags": [{"Key": "Name", "Value": "my-template"}],
                }
            ],
        )

    def test_should_require_ami_option(self):
        """Should require --ami option."""
        result = runner.invoke(
            app,
            [
                "create-template",
                "my-template",
                "--instance-type",
                "t3.small",
                "--key-name",
                "my-key",
                "--yes",
            ],
        )

        assert result.exit_code != 0

    def test_should_require_instance_type_option(self):
        """Should require --instance-type option."""
        result = runner.invoke(
            app,
            [
                "create-template",
                "my-template",
                "--ami",
                "ami-123",
                "--key-name",
                "my-key",
                "--yes",
            ],
        )

        assert result.exit_code != 0

    def test_should_require_key_name_option(self):
        """Should require --key-name option."""
        result = runner.invoke(
            app,
            [
                "create-template",
                "my-template",
                "--ami",
                "ami-123",
                "--instance-type",
                "t3.small",
                "--yes",
            ],
        )

        assert result.exit_code != 0

    def test_should_require_template_name_argument(self):
        """Should require template name argument."""
        result = runner.invoke(
            app,
            [
                "create-template",
                "--ami",
                "ami-123",
                "--instance-type",
                "t3.small",
                "--key-name",
                "my-key",
                "--yes",
            ],
        )

        assert result.exit_code != 0

    def test_should_validate_instance_type(self, mocker):
        """Should validate instance type format."""
        mocker.patch("remote.ami.get_ec2_client")

        result = runner.invoke(
            app,
            [
                "create-template",
                "my-template",
                "--ami",
                "ami-123",
                "--instance-type",
                "invalid",
                "--key-name",
                "my-key",
                "--yes",
            ],
        )

        assert result.exit_code == 1
        assert "Invalid instance_type" in result.stdout

    def test_should_prompt_for_confirmation(self, mocker):
        """Should prompt for confirmation without --yes flag."""
        mock_ec2 = mocker.patch("remote.ami.get_ec2_client")
        mock_ec2.return_value.create_launch_template.return_value = {
            "LaunchTemplate": {"LaunchTemplateId": "lt-123"}
        }

        result = runner.invoke(
            app,
            [
                "create-template",
                "my-template",
                "--ami",
                "ami-123",
                "--instance-type",
                "t3.small",
                "--key-name",
                "my-key",
            ],
            input="y\n",
        )

        assert result.exit_code == 0
        assert "Created launch template" in result.stdout

    def test_should_cancel_on_declined_confirmation(self, mocker):
        """Should cancel when user declines confirmation."""
        mocker.patch("remote.ami.get_ec2_client")

        result = runner.invoke(
            app,
            [
                "create-template",
                "my-template",
                "--ami",
                "ami-123",
                "--instance-type",
                "t3.small",
                "--key-name",
                "my-key",
            ],
            input="n\n",
        )

        assert result.exit_code == 0
        assert "Cancelled" in result.stdout

    def test_should_handle_aws_error(self, mocker):
        """Should handle AWS errors gracefully."""
        from botocore.exceptions import ClientError

        mock_ec2 = mocker.patch("remote.ami.get_ec2_client")
        mock_ec2.return_value.create_launch_template.side_effect = ClientError(
            {
                "Error": {
                    "Code": "InvalidLaunchTemplateName.AlreadyExistsException",
                    "Message": "Template already exists",
                }
            },
            "CreateLaunchTemplate",
        )

        result = runner.invoke(
            app,
            [
                "create-template",
                "my-template",
                "--ami",
                "ami-123",
                "--instance-type",
                "t3.small",
                "--key-name",
                "my-key",
                "--yes",
            ],
        )

        assert result.exit_code == 1
