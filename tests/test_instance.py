import configparser
import datetime

import pytest
from typer.testing import CliRunner

import remotepy
from remotepy.instance import app, get_launch_template_id

runner = CliRunner()


@pytest.fixture(scope="session")
def test_config(tmpdir_factory):
    config_path = tmpdir_factory.mktemp("remote.py").join("config.ini")
    cfg = configparser.ConfigParser()
    cfg["DEFAULT"]["instance_name"] = "test"

    with open(config_path, "w") as configfile:
        cfg.write(configfile)

    return config_path


@pytest.fixture
def mock_describe_instances_response():
    return {
        "Reservations": [
            {
                "Instances": [
                    {
                        "InstanceId": "i-0123456789abcdef0",
                        "InstanceType": "t2.micro",
                        "State": {"Name": "running", "Code": 16},
                        "LaunchTime": datetime.datetime(2023, 7, 15, 0, 0, 0),
                        "PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com",
                        "Tags": [
                            {"Key": "Name", "Value": "running-instance"},
                        ],
                    },
                ],
                "ReservationId": "r-0123456789abcdef0",
            },
            {
                "Instances": [
                    {
                        "InstanceId": "i-0123456789abcdef1",
                        "InstanceType": "t2.micro",
                        "State": {"Name": "stopped", "Code": 80},
                        "LaunchTime": datetime.datetime(2023, 7, 15, 0, 0, 0),
                        "PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com",
                        "Tags": [
                            {"Key": "Name", "Value": "stopped-instance"},
                        ],
                    },
                ],
                "ReservationId": "r-0123456789abcdef1",
            },
        ]
    }


def test_instance_status_when_not_found(mocker, test_config):
    # Mock the AWS EC2 client to return empty reservations (instance not found)
    mocker.patch("remotepy.utils.ec2_client", autospec=True)
    remotepy.utils.ec2_client.describe_instances.return_value = {"Reservations": []}

    result = runner.invoke(app, ["status", "test"])

    # Expect a 1 exit code as we sys.exit(1)
    assert result.exit_code == 1
    assert "Instance test not found" in result.stdout


def test_empty_list(mocker, test_config):
    # Mock the AWS EC2 client to return empty reservations
    mocker.patch("remotepy.utils.ec2_client", autospec=True)
    remotepy.utils.ec2_client.describe_instances.return_value = {"Reservations": []}

    result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    assert "Name" in result.stdout
    assert "InstanceId" in result.stdout
    assert "PublicDnsName" in result.stdout
    assert "Status" in result.stdout


def test_list(mocker, mock_describe_instances_response):
    # Mock the AWS EC2 client
    mocker.patch("remotepy.utils.ec2_client", autospec=True)

    # Simulate a response from AWS EC2
    remotepy.utils.ec2_client.describe_instances.return_value = mock_describe_instances_response
    # Call the function
    result = runner.invoke(app, ["list"])

    # Check that the describe_instances method was called
    remotepy.utils.ec2_client.describe_instances.assert_called_once()

    assert "Name" in result.stdout
    assert "InstanceId" in result.stdout
    assert "PublicDnsName" in result.stdout
    assert "Status" in result.stdout
    assert "Type" in result.stdout
    assert "Launch Time" in result.stdout

    assert "i-0123456789abcdef0" in result.stdout
    assert "running" in result.stdout
    assert "t2.micro" in result.stdout
    assert "2023-07-15 00:00:00 UTC" in result.stdout


def test_get_launch_template_id(mocker):
    # Mock the AWS EC2 client
    mocker.patch("remotepy.instance.ec2_client", autospec=True)

    # Mock the describe_launch_templates function
    mock_describe_launch_templates = remotepy.instance.ec2_client.describe_launch_templates

    # Simulate a response from AWS EC2
    mock_describe_launch_templates.return_value = {
        "LaunchTemplates": [{"LaunchTemplateId": "lt-0123456789abcdef0"}]
    }

    # Call the function with a launch template name
    result = get_launch_template_id("my-template-name")

    # Check that the describe_launch_templates function was called with the
    # correct arguments

    mock_describe_launch_templates.assert_called_once_with(
        Filters=[{"Name": "tag:Name", "Values": ["my-template-name"]}]
    )

    # Check that the function returned the correct launch template ID
    assert result == "lt-0123456789abcdef0"
