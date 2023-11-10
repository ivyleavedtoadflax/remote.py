from unittest.mock import patch

import pytest
import typer
from remotepy.ecs import prompt_for_services_name


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
