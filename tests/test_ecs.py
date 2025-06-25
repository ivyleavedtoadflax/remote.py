from unittest.mock import patch

import pytest
from botocore.exceptions import ClientError, NoCredentialsError
from click.exceptions import Exit
from typer.testing import CliRunner

from remotepy.ecs import (
    app,
    get_all_clusters,
    get_all_services,
    prompt_for_cluster_name,
    prompt_for_services_name,
    scale_service,
)
from remotepy.exceptions import AWSServiceError

runner = CliRunner()


@pytest.fixture
def mock_clusters_response():
    return {
        "clusterArns": [
            "arn:aws:ecs:us-east-1:123456789012:cluster/test-cluster-1",
            "arn:aws:ecs:us-east-1:123456789012:cluster/test-cluster-2",
        ]
    }


@pytest.fixture
def mock_services_response():
    return {
        "serviceArns": [
            "arn:aws:ecs:us-east-1:123456789012:service/test-cluster/test-service-1",
            "arn:aws:ecs:us-east-1:123456789012:service/test-cluster/test-service-2",
        ]
    }


def test_get_all_clusters(mocker, mock_clusters_response):
    mock_ecs_client = mocker.patch("remotepy.ecs.ecs_client")
    mock_ecs_client.list_clusters.return_value = mock_clusters_response

    result = get_all_clusters()

    assert result == [
        "arn:aws:ecs:us-east-1:123456789012:cluster/test-cluster-1",
        "arn:aws:ecs:us-east-1:123456789012:cluster/test-cluster-2",
    ]
    mock_ecs_client.list_clusters.assert_called_once()


def test_get_all_services(mocker, mock_services_response):
    mock_ecs_client = mocker.patch("remotepy.ecs.ecs_client")
    mock_ecs_client.list_services.return_value = mock_services_response

    result = get_all_services("test-cluster")

    assert result == [
        "arn:aws:ecs:us-east-1:123456789012:service/test-cluster/test-service-1",
        "arn:aws:ecs:us-east-1:123456789012:service/test-cluster/test-service-2",
    ]
    mock_ecs_client.list_services.assert_called_once_with(cluster="test-cluster")


def test_scale_service(mocker):
    mock_ecs_client = mocker.patch("remotepy.ecs.ecs_client")

    scale_service("test-cluster", "test-service", 5)

    mock_ecs_client.update_service.assert_called_once_with(
        cluster="test-cluster", service="test-service", desiredCount=5
    )


def test_prompt_for_cluster_name_single_cluster(mocker, capsys):
    mock_get_all_clusters = mocker.patch(
        "remotepy.ecs.get_all_clusters", return_value=["test-cluster"]
    )

    result = prompt_for_cluster_name()

    assert result == "test-cluster"
    mock_get_all_clusters.assert_called_once()
    captured = capsys.readouterr()
    assert "Using cluster: test-cluster" in captured.out


def test_prompt_for_cluster_name_multiple_clusters(mocker, capsys):
    mock_get_all_clusters = mocker.patch(
        "remotepy.ecs.get_all_clusters", return_value=["test-cluster-1", "test-cluster-2"]
    )
    mock_prompt = mocker.patch("typer.prompt", return_value="2")

    result = prompt_for_cluster_name()

    assert result == "test-cluster-2"
    mock_get_all_clusters.assert_called_once()
    mock_prompt.assert_called_once_with("Enter the number of the cluster")
    captured = capsys.readouterr()
    assert "Please select a cluster from the following list:" in captured.out
    assert "1. test-cluster-1" in captured.out
    assert "2. test-cluster-2" in captured.out


def test_prompt_for_cluster_name_no_clusters(mocker):
    mock_get_all_clusters = mocker.patch("remotepy.ecs.get_all_clusters", return_value=[])

    with pytest.raises(Exit):
        prompt_for_cluster_name()

    mock_get_all_clusters.assert_called_once()


def test_prompt_for_services_name_single_service_found(capsys):
    with patch("remotepy.ecs.get_all_services", return_value=["test-service"]):
        result = prompt_for_services_name("test-cluster")
        assert result == ["test-service"]
        captured = capsys.readouterr()
        assert "Using service: test-service" in captured.out


def test_prompt_for_services_name_multiple_services_found(capsys):
    with patch(
        "remotepy.ecs.get_all_services",
        return_value=["test-service-1", "test-service-2"],
    ):
        with patch("typer.prompt", return_value="1, 2"):
            result = prompt_for_services_name("test-cluster")
            assert result == ["test-service-1", "test-service-2"]
            captured = capsys.readouterr()
            assert "Please select one or more services" in captured.out
            assert "1. test-service-1" in captured.out
            assert "2. test-service-2" in captured.out


def test_prompt_for_services_name_no_services(mocker):
    mock_get_all_services = mocker.patch("remotepy.ecs.get_all_services", return_value=[])

    with pytest.raises(Exit):
        prompt_for_services_name("test-cluster")

    mock_get_all_services.assert_called_once_with("test-cluster")


def test_prompt_for_services_name_single_service_selection(mocker, capsys):
    mock_get_all_services = mocker.patch(
        "remotepy.ecs.get_all_services",
        return_value=["test-service-1", "test-service-2", "test-service-3"],
    )
    mocker.patch("typer.prompt", return_value="2")

    result = prompt_for_services_name("test-cluster")

    assert result == ["test-service-2"]
    mock_get_all_services.assert_called_once_with("test-cluster")
    captured = capsys.readouterr()
    assert "Please select one or more services" in captured.out


def test_list_clusters_command(mocker):
    mock_get_all_clusters = mocker.patch(
        "remotepy.ecs.get_all_clusters", return_value=["test-cluster-1", "test-cluster-2"]
    )

    result = runner.invoke(app, ["list-clusters"])

    assert result.exit_code == 0
    mock_get_all_clusters.assert_called_once()
    assert "test-cluster-1" in result.stdout
    assert "test-cluster-2" in result.stdout


def test_list_clusters_command_empty(mocker):
    mock_get_all_clusters = mocker.patch("remotepy.ecs.get_all_clusters", return_value=[])

    result = runner.invoke(app, ["list-clusters"])

    assert result.exit_code == 0
    mock_get_all_clusters.assert_called_once()


def test_list_services_command_with_cluster_name(mocker):
    mock_get_all_services = mocker.patch(
        "remotepy.ecs.get_all_services", return_value=["test-service-1", "test-service-2"]
    )

    result = runner.invoke(app, ["list-services", "test-cluster"])

    assert result.exit_code == 0
    mock_get_all_services.assert_called_once_with("test-cluster")
    assert "test-service-1" in result.stdout
    assert "test-service-2" in result.stdout


def test_list_services_command_without_cluster_name(mocker):
    mock_prompt_for_cluster_name = mocker.patch(
        "remotepy.ecs.prompt_for_cluster_name", return_value="selected-cluster"
    )
    mock_get_all_services = mocker.patch(
        "remotepy.ecs.get_all_services", return_value=["service-1"]
    )

    result = runner.invoke(app, ["list-services"])

    assert result.exit_code == 0
    mock_prompt_for_cluster_name.assert_called_once()
    mock_get_all_services.assert_called_once_with("selected-cluster")


def test_scale_command_with_all_params(mocker):
    mock_scale_service = mocker.patch("remotepy.ecs.scale_service")

    result = runner.invoke(
        app, ["scale", "test-cluster", "test-service", "--count", "3"], input="y\n"
    )

    assert result.exit_code == 0
    mock_scale_service.assert_called_once_with("test-cluster", "test-service", 3)
    assert "Scaled test-service to 3 tasks" in result.stdout


def test_scale_command_without_cluster_name(mocker):
    mock_prompt_for_cluster_name = mocker.patch(
        "remotepy.ecs.prompt_for_cluster_name", return_value="selected-cluster"
    )
    mock_prompt_for_services_name = mocker.patch(
        "remotepy.ecs.prompt_for_services_name", return_value=["test-service"]
    )
    mock_scale_service = mocker.patch("remotepy.ecs.scale_service")

    result = runner.invoke(app, ["scale", "--count", "2"], input="y\n")

    assert result.exit_code == 0
    mock_prompt_for_cluster_name.assert_called_once()
    mock_prompt_for_services_name.assert_called_once_with("selected-cluster")
    mock_scale_service.assert_called_once_with("selected-cluster", "test-service", 2)


def test_scale_command_without_service_name(mocker):
    mock_prompt_for_services_name = mocker.patch(
        "remotepy.ecs.prompt_for_services_name", return_value=["selected-service"]
    )
    mock_scale_service = mocker.patch("remotepy.ecs.scale_service")

    result = runner.invoke(app, ["scale", "test-cluster", "--count", "4"], input="y\n")

    assert result.exit_code == 0
    mock_prompt_for_services_name.assert_called_once_with("test-cluster")
    mock_scale_service.assert_called_once_with("test-cluster", "selected-service", 4)


def test_scale_command_without_desired_count(mocker):
    mock_scale_service = mocker.patch("remotepy.ecs.scale_service")

    result = runner.invoke(app, ["scale", "test-cluster", "test-service"], input="5\ny\n")

    assert result.exit_code == 0
    mock_scale_service.assert_called_once_with("test-cluster", "test-service", 5)


def test_scale_command_cancelled(mocker):
    mock_scale_service = mocker.patch("remotepy.ecs.scale_service")

    result = runner.invoke(
        app, ["scale", "test-cluster", "test-service", "--count", "3"], input="n\n"
    )

    assert result.exit_code == 0
    mock_scale_service.assert_not_called()


def test_scale_command_multiple_services(mocker):
    mock_prompt_for_services_name = mocker.patch(
        "remotepy.ecs.prompt_for_services_name", return_value=["service-1", "service-2"]
    )
    mock_scale_service = mocker.patch("remotepy.ecs.scale_service")

    result = runner.invoke(app, ["scale", "test-cluster", "--count", "2"], input="y\ny\n")

    assert result.exit_code == 0
    mock_prompt_for_services_name.assert_called_once_with("test-cluster")
    assert mock_scale_service.call_count == 2
    mock_scale_service.assert_any_call("test-cluster", "service-1", 2)
    mock_scale_service.assert_any_call("test-cluster", "service-2", 2)


# Error path tests for improved coverage

def test_get_all_clusters_client_error(mocker):
    """Test get_all_clusters with ClientError."""
    mock_ecs_client = mocker.patch("remotepy.ecs.ecs_client")
    
    error_response = {"Error": {"Code": "UnauthorizedOperation", "Message": "Access denied"}}
    mock_ecs_client.list_clusters.side_effect = ClientError(error_response, "list_clusters")
    
    with pytest.raises(AWSServiceError) as exc_info:
        get_all_clusters()
    
    assert exc_info.value.service == "ECS"
    assert exc_info.value.operation == "list_clusters"
    assert exc_info.value.aws_error_code == "UnauthorizedOperation"


def test_get_all_clusters_no_credentials_error(mocker):
    """Test get_all_clusters with NoCredentialsError."""
    mock_ecs_client = mocker.patch("remotepy.ecs.ecs_client")
    
    mock_ecs_client.list_clusters.side_effect = NoCredentialsError()
    
    with pytest.raises(AWSServiceError) as exc_info:
        get_all_clusters()
    
    assert exc_info.value.service == "ECS"
    assert exc_info.value.operation == "list_clusters"
    assert exc_info.value.aws_error_code == "NoCredentials"


def test_get_all_services_client_error(mocker):
    """Test get_all_services with ClientError."""
    mock_ecs_client = mocker.patch("remotepy.ecs.ecs_client")
    
    error_response = {"Error": {"Code": "ClusterNotFoundException", "Message": "Cluster not found"}}
    mock_ecs_client.list_services.side_effect = ClientError(error_response, "list_services")
    
    with pytest.raises(AWSServiceError) as exc_info:
        get_all_services("nonexistent-cluster")
    
    assert exc_info.value.service == "ECS"
    assert exc_info.value.operation == "list_services"
    assert exc_info.value.aws_error_code == "ClusterNotFoundException"


def test_get_all_services_no_credentials_error(mocker):
    """Test get_all_services with NoCredentialsError."""
    mock_ecs_client = mocker.patch("remotepy.ecs.ecs_client")
    
    mock_ecs_client.list_services.side_effect = NoCredentialsError()
    
    with pytest.raises(AWSServiceError) as exc_info:
        get_all_services("test-cluster")
    
    assert exc_info.value.service == "ECS"
    assert exc_info.value.operation == "list_services"
    assert exc_info.value.aws_error_code == "NoCredentials"


def test_scale_service_client_error(mocker):
    """Test scale_service with ClientError."""
    mock_ecs_client = mocker.patch("remotepy.ecs.ecs_client")
    
    error_response = {"Error": {"Code": "ServiceNotFoundException", "Message": "Service not found"}}
    mock_ecs_client.update_service.side_effect = ClientError(error_response, "update_service")
    
    with pytest.raises(AWSServiceError) as exc_info:
        scale_service("test-cluster", "nonexistent-service", 5)
    
    assert exc_info.value.service == "ECS"
    assert exc_info.value.operation == "update_service"
    assert exc_info.value.aws_error_code == "ServiceNotFoundException"


def test_scale_service_no_credentials_error(mocker):
    """Test scale_service with NoCredentialsError."""
    mock_ecs_client = mocker.patch("remotepy.ecs.ecs_client")
    
    mock_ecs_client.update_service.side_effect = NoCredentialsError()
    
    with pytest.raises(AWSServiceError) as exc_info:
        scale_service("test-cluster", "test-service", 3)
    
    assert exc_info.value.service == "ECS"
    assert exc_info.value.operation == "update_service"
    assert exc_info.value.aws_error_code == "NoCredentials"
