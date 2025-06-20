import datetime

import pytest
from typer.testing import CliRunner

from remotepy.ami import app, get_launch_template_id

runner = CliRunner()


@pytest.fixture
def mock_ami_response():
    return {
        "Images": [
            {
                "ImageId": "ami-0123456789abcdef0",
                "Name": "test-ami-1",
                "State": "available",
                "CreationDate": datetime.datetime(2023, 7, 15, 0, 0, 0, tzinfo=datetime.UTC),
            },
            {
                "ImageId": "ami-0123456789abcdef1",
                "Name": "test-ami-2",
                "State": "pending",
                "CreationDate": datetime.datetime(2023, 7, 16, 0, 0, 0, tzinfo=datetime.UTC),
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
    mock_ec2_client = mocker.patch("remotepy.ami.ec2_client", autospec=True)
    mock_get_instance_id = mocker.patch(
        "remotepy.ami.get_instance_id", return_value="i-0123456789abcdef0"
    )

    mock_ec2_client.create_image.return_value = {"ImageId": "ami-0123456789abcdef0"}

    result = runner.invoke(app, [
        "create",
        "--instance-name", "test-instance",
        "--name", "test-ami",
        "--description", "Test AMI description"
    ])

    assert result.exit_code == 0
    mock_get_instance_id.assert_called_once_with("test-instance")
    mock_ec2_client.create_image.assert_called_once_with(
        InstanceId="i-0123456789abcdef0",
        Name="test-ami",
        Description="Test AMI description",
        NoReboot=True,
    )
    assert "AMI ami-0123456789abcdef0 created" in result.stdout


def test_create_ami_without_instance_name(mocker):
    mock_ec2_client = mocker.patch("remotepy.ami.ec2_client", autospec=True)
    mock_get_instance_name = mocker.patch(
        "remotepy.ami.get_instance_name", return_value="default-instance"
    )
    mock_get_instance_id = mocker.patch(
        "remotepy.ami.get_instance_id", return_value="i-0123456789abcdef0"
    )

    mock_ec2_client.create_image.return_value = {"ImageId": "ami-default"}

    result = runner.invoke(app, ["create", "--name", "test-ami"])

    assert result.exit_code == 0
    mock_get_instance_name.assert_called_once()
    mock_get_instance_id.assert_called_once_with("default-instance")


def test_create_ami_minimal_params(mocker):
    mock_ec2_client = mocker.patch("remotepy.ami.ec2_client", autospec=True)
    mock_get_instance_name = mocker.patch(
        "remotepy.ami.get_instance_name", return_value="default-instance"
    )
    mock_get_instance_id = mocker.patch(
        "remotepy.ami.get_instance_id", return_value="i-0123456789abcdef0"
    )

    mock_ec2_client.create_image.return_value = {"ImageId": "ami-minimal"}

    result = runner.invoke(app, ["create"])

    assert result.exit_code == 0
    mock_ec2_client.create_image.assert_called_once_with(
        InstanceId="i-0123456789abcdef0",
        Name=None,
        Description=None,
        NoReboot=True,
    )


def test_list_amis(mocker, mock_ami_response):
    mock_ec2_client = mocker.patch("remotepy.ami.ec2_client", autospec=True)
    mock_get_account_id = mocker.patch(
        "remotepy.ami.get_account_id", return_value="123456789012"
    )

    mock_ec2_client.describe_images.return_value = mock_ami_response

    result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    mock_get_account_id.assert_called_once()
    mock_ec2_client.describe_images.assert_called_once_with(Owners=["123456789012"])

    assert "ami-0123456789abcdef0" in result.stdout
    assert "ami-0123456789abcdef1" in result.stdout
    assert "test-ami-1" in result.stdout
    assert "test-ami-2" in result.stdout
    assert "available" in result.stdout
    assert "pending" in result.stdout


def test_list_amis_alias_ls(mocker, mock_ami_response):
    mock_ec2_client = mocker.patch("remotepy.ami.ec2_client", autospec=True)
    mock_get_account_id = mocker.patch(
        "remotepy.ami.get_account_id", return_value="123456789012"
    )

    mock_ec2_client.describe_images.return_value = mock_ami_response

    result = runner.invoke(app, ["ls"])

    assert result.exit_code == 0
    mock_get_account_id.assert_called_once()
    mock_ec2_client.describe_images.assert_called_once_with(Owners=["123456789012"])


def test_list_amis_empty(mocker):
    mock_ec2_client = mocker.patch("remotepy.ami.ec2_client", autospec=True)
    mock_get_account_id = mocker.patch(
        "remotepy.ami.get_account_id", return_value="123456789012"
    )

    mock_ec2_client.describe_images.return_value = {"Images": []}

    result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    # Should show headers but no AMI data
    assert "ImageId" in result.stdout
    assert "Name" in result.stdout


def test_get_launch_template_id(mocker):
    mock_ec2_client = mocker.patch("remotepy.ami.ec2_client", autospec=True)

    mock_ec2_client.describe_launch_templates.return_value = {
        "LaunchTemplates": [{"LaunchTemplateId": "lt-0123456789abcdef0"}]
    }

    result = get_launch_template_id("test-template")

    assert result == "lt-0123456789abcdef0"
    mock_ec2_client.describe_launch_templates.assert_called_once_with(
        Filters=[{"Name": "tag:Name", "Values": ["test-template"]}]
    )


def test_list_launch_templates(mocker, mock_launch_template_response):
    mock_ec2_client = mocker.patch("remotepy.ami.ec2_client", autospec=True)

    mock_ec2_client.describe_launch_templates.return_value = mock_launch_template_response

    result = runner.invoke(app, ["list-launch-templates"])

    assert result.exit_code == 0
    mock_ec2_client.describe_launch_templates.assert_called_once()

    assert "lt-0123456789abcdef0" in result.stdout
    assert "lt-0123456789abcdef1" in result.stdout
    assert "test-template-1" in result.stdout
    assert "test-template-2" in result.stdout


def test_list_launch_templates_empty(mocker):
    mock_ec2_client = mocker.patch("remotepy.ami.ec2_client", autospec=True)

    mock_ec2_client.describe_launch_templates.return_value = {"LaunchTemplates": []}

    result = runner.invoke(app, ["list-launch-templates"])

    assert result.exit_code == 0
    # Should show headers but no template data
    assert "LaunchTemplateId" in result.stdout
    assert "LaunchTemplateName" in result.stdout


def test_launch_with_template_name(mocker):
    mock_ec2_client = mocker.patch("remotepy.ami.ec2_client", autospec=True)
    mock_get_launch_template_id = mocker.patch(
        "remotepy.ami.get_launch_template_id", return_value="lt-0123456789abcdef0"
    )

    mock_ec2_client.run_instances.return_value = {
        "Instances": [{"InstanceId": "i-0123456789abcdef0"}]
    }

    result = runner.invoke(app, [
        "launch",
        "--launch-template", "test-template",
        "--name", "test-instance",
        "--version", "2"
    ])

    assert result.exit_code == 0
    mock_ec2_client.run_instances.assert_called_once_with(
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
    mock_ec2_client = mocker.patch("remotepy.ami.ec2_client", autospec=True)
    mock_get_launch_template_id = mocker.patch(
        "remotepy.ami.get_launch_template_id", return_value="lt-0123456789abcdef0"
    )

    mock_ec2_client.run_instances.return_value = {
        "Instances": [{"InstanceId": "i-default"}]
    }

    result = runner.invoke(app, [
        "launch",
        "--launch-template", "test-template",
        "--name", "test-instance"
    ])

    assert result.exit_code == 0
    mock_ec2_client.run_instances.assert_called_once_with(
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
    mock_ec2_client = mocker.patch("remotepy.ami.ec2_client", autospec=True)
    mock_list_launch_templates = mocker.patch(
        "remotepy.ami.list_launch_templates", return_value=mock_launch_template_response
    )

    mock_ec2_client.run_instances.return_value = {
        "Instances": [{"InstanceId": "i-interactive"}]
    }

    # Mock user input: select template 1, use suggested name
    result = runner.invoke(app, ["launch"], input="1\ntest-instance-abc123\n")

    assert result.exit_code == 0
    mock_list_launch_templates.assert_called_once()
    mock_ec2_client.run_instances.assert_called_once()

    assert "Please specify a launch template" in result.stdout
    assert "Available launch templates:" in result.stdout


def test_launch_without_name_uses_suggestion(mocker):
    mock_ec2_client = mocker.patch("remotepy.ami.ec2_client", autospec=True)
    mock_get_launch_template_id = mocker.patch(
        "remotepy.ami.get_launch_template_id", return_value="lt-0123456789abcdef0"
    )

    # Mock random string generation for name suggestion
    mock_random_choices = mocker.patch("remotepy.ami.random.choices", return_value=list("abc123"))

    mock_ec2_client.run_instances.return_value = {
        "Instances": [{"InstanceId": "i-suggested"}]
    }

    # User accepts the suggested name by pressing enter
    result = runner.invoke(app, [
        "launch",
        "--launch-template", "test-template"
    ], input="\n")

    assert result.exit_code == 0

    # Check that the suggested name pattern was used
    call_args = mock_ec2_client.run_instances.call_args
    tag_specs = call_args[1]["TagSpecifications"]
    instance_name = tag_specs[0]["Tags"][0]["Value"]
    assert "test-template-abc123" == instance_name
