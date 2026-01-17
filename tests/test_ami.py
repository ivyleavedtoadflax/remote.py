import datetime

import pytest
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
    mock_get_instance_id = mocker.patch(
        "remote.ami.get_instance_id", return_value="i-0123456789abcdef0"
    )

    mock_ec2_client.return_value.create_image.return_value = {"ImageId": "ami-0123456789abcdef0"}

    result = runner.invoke(
        app,
        [
            "create",
            "--instance-name",
            "test-instance",
            "--name",
            "test-ami",
            "--description",
            "Test AMI description",
        ],
    )

    assert result.exit_code == 0
    mock_get_instance_id.assert_called_once_with("test-instance")
    mock_ec2_client.return_value.create_image.assert_called_once_with(
        InstanceId="i-0123456789abcdef0",
        Name="test-ami",
        Description="Test AMI description",
        NoReboot=True,
    )
    assert "AMI ami-0123456789abcdef0 created" in result.stdout


def test_create_ami_without_instance_name(mocker):
    mock_ec2_client = mocker.patch("remote.ami.get_ec2_client")
    mock_get_instance_name = mocker.patch(
        "remote.ami.get_instance_name", return_value="default-instance"
    )
    mock_get_instance_id = mocker.patch(
        "remote.ami.get_instance_id", return_value="i-0123456789abcdef0"
    )

    mock_ec2_client.return_value.create_image.return_value = {"ImageId": "ami-default"}

    result = runner.invoke(app, ["create", "--name", "test-ami"])

    assert result.exit_code == 0
    mock_get_instance_name.assert_called_once()
    mock_get_instance_id.assert_called_once_with("default-instance")


def test_create_ami_minimal_params(mocker):
    mock_ec2_client = mocker.patch("remote.ami.get_ec2_client")
    mocker.patch("remote.ami.get_instance_name", return_value="default-instance")
    mocker.patch("remote.ami.get_instance_id", return_value="i-0123456789abcdef0")

    mock_ec2_client.return_value.create_image.return_value = {"ImageId": "ami-minimal"}

    result = runner.invoke(app, ["create"])

    assert result.exit_code == 0
    # When no name/description provided, defaults are used
    mock_ec2_client.return_value.create_image.assert_called_once_with(
        InstanceId="i-0123456789abcdef0",
        Name="ami-default-instance",  # Default name based on instance name
        Description="",  # Empty string as default
        NoReboot=True,
    )


def test_list_amis(mocker, mock_ami_response):
    mock_ec2_client = mocker.patch("remote.ami.get_ec2_client")
    mock_get_account_id = mocker.patch("remote.ami.get_account_id", return_value="123456789012")

    mock_ec2_client.return_value.describe_images.return_value = mock_ami_response

    result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    mock_get_account_id.assert_called_once()
    mock_ec2_client.return_value.describe_images.assert_called_once_with(Owners=["123456789012"])

    assert "ami-0123456789abcdef0" in result.stdout
    assert "ami-0123456789abcdef1" in result.stdout
    assert "test-ami-1" in result.stdout
    assert "test-ami-2" in result.stdout
    assert "available" in result.stdout
    assert "pending" in result.stdout


def test_list_amis_alias_ls(mocker, mock_ami_response):
    mock_ec2_client = mocker.patch("remote.ami.get_ec2_client")
    mock_get_account_id = mocker.patch("remote.ami.get_account_id", return_value="123456789012")

    mock_ec2_client.return_value.describe_images.return_value = mock_ami_response

    result = runner.invoke(app, ["ls"])

    assert result.exit_code == 0
    mock_get_account_id.assert_called_once()
    mock_ec2_client.return_value.describe_images.assert_called_once_with(Owners=["123456789012"])


def test_list_amis_empty(mocker):
    mock_ec2_client = mocker.patch("remote.ami.get_ec2_client")
    mocker.patch("remote.ami.get_account_id", return_value="123456789012")

    mock_ec2_client.return_value.describe_images.return_value = {"Images": []}

    result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    # Should show headers but no AMI data
    assert "ImageId" in result.stdout
    assert "Name" in result.stdout


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


def test_launch_with_template_name(mocker):
    mock_ec2_client = mocker.patch("remote.ami.get_ec2_client")
    mocker.patch("remote.ami.get_launch_template_id", return_value="lt-0123456789abcdef0")

    mock_ec2_client.return_value.run_instances.return_value = {
        "Instances": [{"InstanceId": "i-0123456789abcdef0"}]
    }

    result = runner.invoke(
        app,
        [
            "launch",
            "--launch-template",
            "test-template",
            "--name",
            "test-instance",
            "--version",
            "2",
        ],
    )

    assert result.exit_code == 0
    mock_ec2_client.return_value.run_instances.assert_called_once_with(
        LaunchTemplate={"LaunchTemplateId": "lt-0123456789abcdef0", "Version": "2"},
        MaxCount=1,
        MinCount=1,
        TagSpecifications=[
            {
                "ResourceType": "instance",
                "Tags": [{"Key": "Name", "Value": "test-instance"}],
            }
        ],
    )
    assert "Instance i-0123456789abcdef0 with name 'test-instance' launched" in result.stdout


def test_launch_with_default_version(mocker):
    mock_ec2_client = mocker.patch("remote.ami.get_ec2_client")
    mocker.patch("remote.ami.get_launch_template_id", return_value="lt-0123456789abcdef0")

    mock_ec2_client.return_value.run_instances.return_value = {
        "Instances": [{"InstanceId": "i-default"}]
    }

    result = runner.invoke(
        app, ["launch", "--launch-template", "test-template", "--name", "test-instance"]
    )

    assert result.exit_code == 0
    mock_ec2_client.return_value.run_instances.assert_called_once_with(
        LaunchTemplate={"LaunchTemplateId": "lt-0123456789abcdef0", "Version": "$Latest"},
        MaxCount=1,
        MinCount=1,
        TagSpecifications=[
            {
                "ResourceType": "instance",
                "Tags": [{"Key": "Name", "Value": "test-instance"}],
            }
        ],
    )


def test_launch_without_template_interactive(mocker, mock_launch_template_response):
    mock_ec2_client = mocker.patch("remote.ami.get_ec2_client")
    mock_get_templates = mocker.patch(
        "remote.ami.get_launch_templates",
        return_value=mock_launch_template_response["LaunchTemplates"],
    )
    mocker.patch("remote.ami.config_manager.get_value", return_value=None)

    mock_ec2_client.return_value.run_instances.return_value = {
        "Instances": [{"InstanceId": "i-interactive"}]
    }

    # Mock user input: select template 1, use suggested name
    result = runner.invoke(app, ["launch"], input="1\ntest-instance-abc123\n")

    assert result.exit_code == 0
    mock_get_templates.assert_called_once()
    mock_ec2_client.return_value.run_instances.assert_called_once()

    assert "Please specify a launch template" in result.stdout
    assert "Available launch templates:" in result.stdout


def test_launch_without_name_uses_suggestion(mocker):
    mock_ec2_client = mocker.patch("remote.ami.get_ec2_client")
    mocker.patch("remote.ami.get_launch_template_id", return_value="lt-0123456789abcdef0")

    # Mock random string generation for name suggestion
    mocker.patch("remote.ami.random.choices", return_value=list("abc123"))

    mock_ec2_client.return_value.run_instances.return_value = {
        "Instances": [{"InstanceId": "i-suggested"}]
    }

    # User accepts the suggested name by pressing enter
    result = runner.invoke(app, ["launch", "--launch-template", "test-template"], input="\n")

    assert result.exit_code == 0

    # Check that the suggested name pattern was used
    call_args = mock_ec2_client.return_value.run_instances.call_args
    tag_specs = call_args[1]["TagSpecifications"]
    instance_name = tag_specs[0]["Tags"][0]["Value"]
    assert "test-template-abc123" == instance_name


def test_launch_no_instances_returned(mocker):
    """Test launch when AWS returns no instances in the response."""
    mock_ec2_client = mocker.patch("remote.ami.get_ec2_client")
    mocker.patch("remote.ami.get_launch_template_id", return_value="lt-0123456789abcdef0")

    # Return empty instances list
    mock_ec2_client.return_value.run_instances.return_value = {"Instances": []}

    result = runner.invoke(
        app, ["launch", "--launch-template", "test-template", "--name", "test-instance"]
    )

    assert result.exit_code == 0
    assert "Warning: No instance information returned from launch" in result.stdout


def test_launch_validation_error_accessing_results(mocker):
    """Test launch when ValidationError occurs accessing launch results."""
    mock_ec2_client = mocker.patch("remote.ami.get_ec2_client")
    mocker.patch("remote.ami.get_launch_template_id", return_value="lt-0123456789abcdef0")

    # Mock safe_get_array_item to raise ValidationError
    from remote.exceptions import ValidationError

    mock_safe_get = mocker.patch("remote.ami.safe_get_array_item")
    mock_safe_get.side_effect = ValidationError("Array access failed")

    # Return instances but safe_get_array_item will fail
    mock_ec2_client.return_value.run_instances.return_value = {
        "Instances": [{"InstanceId": "i-0123456789abcdef0"}]
    }

    result = runner.invoke(
        app, ["launch", "--launch-template", "test-template", "--name", "test-instance"]
    )

    assert result.exit_code == 1
    assert "Error accessing launch result: Validation error: Array access failed" in result.stdout


def test_launch_invalid_template_number(mocker, mock_launch_template_response):
    """Test launch with invalid template number selection (out of bounds)."""
    mocker.patch("remote.ami.get_ec2_client")
    mocker.patch(
        "remote.ami.get_launch_templates",
        return_value=mock_launch_template_response["LaunchTemplates"],
    )
    mocker.patch("remote.ami.config_manager.get_value", return_value=None)

    # User enters invalid template number (3, but only 2 templates exist)
    result = runner.invoke(app, ["launch"], input="3\n")

    assert result.exit_code == 1
    assert "Error:" in result.stdout


def test_launch_zero_template_number(mocker, mock_launch_template_response):
    """Test launch with zero as template number selection."""
    mocker.patch("remote.ami.get_ec2_client")
    mocker.patch(
        "remote.ami.get_launch_templates",
        return_value=mock_launch_template_response["LaunchTemplates"],
    )
    mocker.patch("remote.ami.config_manager.get_value", return_value=None)

    # User enters 0 (invalid since templates are 1-indexed)
    result = runner.invoke(app, ["launch"], input="0\n")

    assert result.exit_code == 1
    assert "Error:" in result.stdout


def test_launch_negative_template_number(mocker, mock_launch_template_response):
    """Test launch with negative template number selection."""
    mocker.patch("remote.ami.get_ec2_client")
    mocker.patch(
        "remote.ami.get_launch_templates",
        return_value=mock_launch_template_response["LaunchTemplates"],
    )
    mocker.patch("remote.ami.config_manager.get_value", return_value=None)

    # User enters negative number
    result = runner.invoke(app, ["launch"], input="-1\n")

    assert result.exit_code == 1
    assert "Error:" in result.stdout


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


def test_launch_with_default_template_from_config(mocker):
    """Test launch using default template from config."""
    mock_ec2_client = mocker.patch("remote.ami.get_ec2_client")
    mocker.patch("remote.ami.get_launch_template_id", return_value="lt-default")
    mocker.patch("remote.ami.config_manager.get_value", return_value="default-template")

    mock_ec2_client.return_value.run_instances.return_value = {
        "Instances": [{"InstanceId": "i-from-default"}]
    }

    result = runner.invoke(app, ["launch", "--name", "my-instance"])

    assert result.exit_code == 0
    assert "Using default template: default-template" in result.stdout
    assert "i-from-default" in result.stdout


def test_launch_no_templates_found(mocker):
    """Test launch when no templates are available."""
    mocker.patch("remote.ami.get_ec2_client")
    mocker.patch("remote.ami.get_launch_templates", return_value=[])
    mocker.patch("remote.ami.config_manager.get_value", return_value=None)

    result = runner.invoke(app, ["launch"])

    assert result.exit_code == 1
    assert "No launch templates found" in result.stdout


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

    result = runner.invoke(app, ["template-info", "my-template", "-v", "1"])

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

    result = runner.invoke(app, ["template-info", "my-template", "-v", "99"])

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
