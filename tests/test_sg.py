"""Tests for security group management module."""

from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from remote.exceptions import ValidationError
from remote.sg import (
    add_ip_to_security_group,
    app,
    clear_ssh_rules,
    get_instance_security_groups,
    get_public_ip,
    get_security_group_rules,
    get_ssh_ip_rules,
    remove_ip_from_security_group,
    whitelist_ip_for_instance,
)

runner = CliRunner()


class TestGetPublicIp:
    """Tests for get_public_ip function."""

    def test_returns_valid_ip(self, mocker):
        """Test that get_public_ip returns a valid IP address."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"203.0.113.1\n"
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        mocker.patch("urllib.request.urlopen", return_value=mock_response)

        result = get_public_ip()
        assert result == "203.0.113.1"

    def test_raises_on_invalid_ip(self, mocker):
        """Test that get_public_ip raises ValidationError for invalid IP."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"invalid-ip\n"
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        mocker.patch("urllib.request.urlopen", return_value=mock_response)

        with pytest.raises(ValidationError) as exc_info:
            get_public_ip()
        assert "Invalid IP address" in str(exc_info.value)

    def test_raises_on_network_error(self, mocker):
        """Test that get_public_ip raises ValidationError on network error."""
        import urllib.error

        mocker.patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("Network unreachable"),
        )

        with pytest.raises(ValidationError) as exc_info:
            get_public_ip()
        assert "Failed to retrieve public IP" in str(exc_info.value)


class TestGetInstanceSecurityGroups:
    """Tests for get_instance_security_groups function."""

    def test_returns_security_groups(self, mocker):
        """Test that security groups are returned for an instance."""
        mock_ec2 = mocker.patch("remote.sg.get_ec2_client")
        mock_ec2.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "SecurityGroups": [
                                {"GroupId": "sg-12345", "GroupName": "my-sg"},
                                {"GroupId": "sg-67890", "GroupName": "other-sg"},
                            ]
                        }
                    ]
                }
            ]
        }

        result = get_instance_security_groups("i-12345")
        assert len(result) == 2
        assert result[0]["GroupId"] == "sg-12345"
        assert result[1]["GroupName"] == "other-sg"

    def test_returns_empty_list_when_no_reservations(self, mocker):
        """Test that empty list is returned when no reservations found."""
        mock_ec2 = mocker.patch("remote.sg.get_ec2_client")
        mock_ec2.return_value.describe_instances.return_value = {"Reservations": []}

        result = get_instance_security_groups("i-12345")
        assert result == []

    def test_returns_empty_list_when_no_instances(self, mocker):
        """Test that empty list is returned when no instances found."""
        mock_ec2 = mocker.patch("remote.sg.get_ec2_client")
        mock_ec2.return_value.describe_instances.return_value = {
            "Reservations": [{"Instances": []}]
        }

        result = get_instance_security_groups("i-12345")
        assert result == []


class TestGetSecurityGroupRules:
    """Tests for get_security_group_rules function."""

    def test_returns_inbound_rules(self, mocker):
        """Test that inbound rules are returned for a security group."""
        mock_ec2 = mocker.patch("remote.sg.get_ec2_client")
        mock_ec2.return_value.describe_security_groups.return_value = {
            "SecurityGroups": [
                {
                    "IpPermissions": [
                        {
                            "FromPort": 22,
                            "ToPort": 22,
                            "IpProtocol": "tcp",
                            "IpRanges": [{"CidrIp": "10.0.0.1/32"}],
                        }
                    ]
                }
            ]
        }

        result = get_security_group_rules("sg-12345")
        assert len(result) == 1
        assert result[0]["FromPort"] == 22

    def test_returns_empty_list_when_no_groups(self, mocker):
        """Test that empty list is returned when no security groups found."""
        mock_ec2 = mocker.patch("remote.sg.get_ec2_client")
        mock_ec2.return_value.describe_security_groups.return_value = {"SecurityGroups": []}

        result = get_security_group_rules("sg-12345")
        assert result == []


class TestAddIpToSecurityGroup:
    """Tests for add_ip_to_security_group function."""

    def test_adds_ip_successfully(self, mocker):
        """Test that IP is added to security group."""
        mock_ec2 = mocker.patch("remote.sg.get_ec2_client")

        add_ip_to_security_group("sg-12345", "10.0.0.1", 22, "Test description")

        mock_ec2.return_value.authorize_security_group_ingress.assert_called_once_with(
            GroupId="sg-12345",
            IpPermissions=[
                {
                    "IpProtocol": "tcp",
                    "FromPort": 22,
                    "ToPort": 22,
                    "IpRanges": [{"CidrIp": "10.0.0.1/32", "Description": "Test description"}],
                }
            ],
        )

    def test_adds_cidr_block_directly(self, mocker):
        """Test that CIDR block is used as-is when provided with slash notation."""
        mock_ec2 = mocker.patch("remote.sg.get_ec2_client")

        add_ip_to_security_group("sg-12345", "10.0.0.0/16", 22, "Test description")

        mock_ec2.return_value.authorize_security_group_ingress.assert_called_once_with(
            GroupId="sg-12345",
            IpPermissions=[
                {
                    "IpProtocol": "tcp",
                    "FromPort": 22,
                    "ToPort": 22,
                    "IpRanges": [{"CidrIp": "10.0.0.0/16", "Description": "Test description"}],
                }
            ],
        )


class TestRemoveIpFromSecurityGroup:
    """Tests for remove_ip_from_security_group function."""

    def test_removes_ip_successfully(self, mocker):
        """Test that IP is removed from security group."""
        mock_ec2 = mocker.patch("remote.sg.get_ec2_client")

        remove_ip_from_security_group("sg-12345", "10.0.0.1", 22)

        mock_ec2.return_value.revoke_security_group_ingress.assert_called_once_with(
            GroupId="sg-12345",
            IpPermissions=[
                {
                    "IpProtocol": "tcp",
                    "FromPort": 22,
                    "ToPort": 22,
                    "IpRanges": [{"CidrIp": "10.0.0.1/32"}],
                }
            ],
        )

    def test_removes_cidr_block_directly(self, mocker):
        """Test that CIDR block is used as-is when provided with slash notation."""
        mock_ec2 = mocker.patch("remote.sg.get_ec2_client")

        remove_ip_from_security_group("sg-12345", "0.0.0.0/0", 22)

        mock_ec2.return_value.revoke_security_group_ingress.assert_called_once_with(
            GroupId="sg-12345",
            IpPermissions=[
                {
                    "IpProtocol": "tcp",
                    "FromPort": 22,
                    "ToPort": 22,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                }
            ],
        )


class TestGetSshIpRules:
    """Tests for get_ssh_ip_rules function."""

    def test_returns_ssh_ip_ranges(self, mocker):
        """Test that SSH IP ranges are returned."""
        mocker.patch(
            "remote.sg.get_security_group_rules",
            return_value=[
                {
                    "FromPort": 22,
                    "ToPort": 22,
                    "IpProtocol": "tcp",
                    "IpRanges": [
                        {"CidrIp": "10.0.0.1/32"},
                        {"CidrIp": "10.0.0.2/32"},
                    ],
                },
                {
                    "FromPort": 443,
                    "ToPort": 443,
                    "IpProtocol": "tcp",
                    "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                },
            ],
        )

        result = get_ssh_ip_rules("sg-12345", 22)
        assert len(result) == 2
        assert "10.0.0.1/32" in result
        assert "10.0.0.2/32" in result
        assert "0.0.0.0/0" not in result  # HTTPS rule shouldn't be included

    def test_returns_empty_list_when_no_ssh_rules(self, mocker):
        """Test that empty list is returned when no SSH rules exist."""
        mocker.patch(
            "remote.sg.get_security_group_rules",
            return_value=[
                {
                    "FromPort": 443,
                    "ToPort": 443,
                    "IpProtocol": "tcp",
                    "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                }
            ],
        )

        result = get_ssh_ip_rules("sg-12345", 22)
        assert result == []

    def test_handles_port_ranges(self, mocker):
        """Test that port ranges are handled correctly."""
        mocker.patch(
            "remote.sg.get_security_group_rules",
            return_value=[
                {
                    "FromPort": 0,
                    "ToPort": 65535,
                    "IpProtocol": "tcp",
                    "IpRanges": [{"CidrIp": "10.0.0.1/32"}],
                }
            ],
        )

        result = get_ssh_ip_rules("sg-12345", 22)
        assert "10.0.0.1/32" in result


class TestClearSshRules:
    """Tests for clear_ssh_rules function."""

    def test_clears_all_rules(self, mocker):
        """Test that all SSH rules are cleared."""
        mocker.patch(
            "remote.sg.get_security_group_rules",
            return_value=[
                {
                    "FromPort": 22,
                    "ToPort": 22,
                    "IpProtocol": "tcp",
                    "IpRanges": [
                        {"CidrIp": "10.0.0.1/32"},
                        {"CidrIp": "10.0.0.2/32"},
                    ],
                }
            ],
        )
        mock_remove = mocker.patch("remote.sg.remove_ip_from_security_group")

        result = clear_ssh_rules("sg-12345", 22)

        assert result == 2
        assert mock_remove.call_count == 2

    def test_excludes_specified_ip(self, mocker):
        """Test that specified IP is excluded from clearing."""
        mocker.patch(
            "remote.sg.get_security_group_rules",
            return_value=[
                {
                    "FromPort": 22,
                    "ToPort": 22,
                    "IpProtocol": "tcp",
                    "IpRanges": [
                        {"CidrIp": "10.0.0.1/32"},
                        {"CidrIp": "10.0.0.2/32"},
                    ],
                }
            ],
        )
        mock_remove = mocker.patch("remote.sg.remove_ip_from_security_group")

        result = clear_ssh_rules("sg-12345", 22, exclude_ip="10.0.0.1")

        assert result == 1
        mock_remove.assert_called_once_with("sg-12345", "10.0.0.2", 22)


class TestWhitelistIpForInstance:
    """Tests for whitelist_ip_for_instance function."""

    def test_whitelists_current_ip(self, mocker):
        """Test that current IP is whitelisted."""
        mocker.patch("remote.sg.get_public_ip", return_value="203.0.113.1")
        mocker.patch(
            "remote.sg.get_instance_security_groups",
            return_value=[{"GroupId": "sg-12345", "GroupName": "my-sg"}],
        )
        mocker.patch("remote.sg.get_ssh_ip_rules", return_value=[])
        mock_add = mocker.patch("remote.sg.add_ip_to_security_group")

        ip, modified = whitelist_ip_for_instance("i-12345")

        assert ip == "203.0.113.1"
        assert modified == ["sg-12345"]
        mock_add.assert_called_once()

    def test_skips_already_whitelisted(self, mocker):
        """Test that already whitelisted IPs are skipped."""
        mocker.patch(
            "remote.sg.get_instance_security_groups",
            return_value=[{"GroupId": "sg-12345", "GroupName": "my-sg"}],
        )
        mocker.patch("remote.sg.get_ssh_ip_rules", return_value=["203.0.113.1/32"])
        mock_add = mocker.patch("remote.sg.add_ip_to_security_group")

        ip, modified = whitelist_ip_for_instance("i-12345", ip_address="203.0.113.1")

        assert ip == "203.0.113.1"
        assert modified == []
        mock_add.assert_not_called()

    def test_skips_already_whitelisted_cidr_block(self, mocker):
        """Test that already whitelisted CIDR blocks are skipped."""
        mocker.patch(
            "remote.sg.get_instance_security_groups",
            return_value=[{"GroupId": "sg-12345", "GroupName": "my-sg"}],
        )
        mocker.patch("remote.sg.get_ssh_ip_rules", return_value=["10.0.0.0/16"])
        mock_add = mocker.patch("remote.sg.add_ip_to_security_group")

        ip, modified = whitelist_ip_for_instance("i-12345", ip_address="10.0.0.0/16")

        assert ip == "10.0.0.0/16"
        assert modified == []
        mock_add.assert_not_called()

    def test_clears_existing_when_exclusive(self, mocker):
        """Test that existing rules are cleared when exclusive=True."""
        mocker.patch(
            "remote.sg.get_instance_security_groups",
            return_value=[{"GroupId": "sg-12345", "GroupName": "my-sg"}],
        )
        mocker.patch("remote.sg.get_ssh_ip_rules", return_value=[])
        mock_clear = mocker.patch("remote.sg.clear_ssh_rules")
        mock_add = mocker.patch("remote.sg.add_ip_to_security_group")

        whitelist_ip_for_instance("i-12345", ip_address="203.0.113.1", exclusive=True)

        mock_clear.assert_called_once_with("sg-12345", 22, exclude_ip="203.0.113.1")
        mock_add.assert_called_once()

    def test_raises_when_no_security_groups(self, mocker):
        """Test that ValidationError is raised when no security groups found."""
        mocker.patch("remote.sg.get_instance_security_groups", return_value=[])

        with pytest.raises(ValidationError) as exc_info:
            whitelist_ip_for_instance("i-12345", ip_address="203.0.113.1")
        assert "No security groups found" in str(exc_info.value)


class TestAddIpCommand:
    """Tests for the add-ip CLI command."""

    def test_adds_ip_successfully(self, mocker, test_config):
        """Test that add-ip command works."""
        mocker.patch(
            "remote.sg.resolve_instance_or_exit",
            return_value=("test-instance", "i-12345"),
        )
        mocker.patch("remote.sg.get_public_ip", return_value="203.0.113.1")
        mocker.patch(
            "remote.sg.get_instance_security_groups",
            return_value=[{"GroupId": "sg-12345", "GroupName": "my-sg"}],
        )
        mocker.patch("remote.sg.get_ssh_ip_rules", return_value=[])
        mocker.patch("remote.sg.add_ip_to_security_group")

        result = runner.invoke(app, ["add-ip", "test-instance"])

        assert result.exit_code == 0
        assert "203.0.113.1" in result.stdout

    def test_adds_specific_ip(self, mocker, test_config):
        """Test that add-ip command works with specific IP."""
        mocker.patch(
            "remote.sg.resolve_instance_or_exit",
            return_value=("test-instance", "i-12345"),
        )
        mocker.patch(
            "remote.sg.get_instance_security_groups",
            return_value=[{"GroupId": "sg-12345", "GroupName": "my-sg"}],
        )
        mocker.patch("remote.sg.get_ssh_ip_rules", return_value=[])
        mocker.patch("remote.sg.add_ip_to_security_group")

        result = runner.invoke(app, ["add-ip", "test-instance", "--ip", "10.0.0.1"])

        assert result.exit_code == 0
        assert "10.0.0.1" in result.stdout

    def test_adds_cidr_block(self, mocker, test_config):
        """Test that add-ip command works with CIDR notation like 10.0.0.0/16."""
        mocker.patch(
            "remote.sg.resolve_instance_or_exit",
            return_value=("test-instance", "i-12345"),
        )
        mocker.patch(
            "remote.sg.get_instance_security_groups",
            return_value=[{"GroupId": "sg-12345", "GroupName": "my-sg"}],
        )
        mocker.patch("remote.sg.get_ssh_ip_rules", return_value=[])
        mock_add = mocker.patch("remote.sg.add_ip_to_security_group")

        result = runner.invoke(app, ["add-ip", "test-instance", "--ip", "10.0.0.0/16"])

        assert result.exit_code == 0
        assert "10.0.0.0/16" in result.stdout
        mock_add.assert_called_once_with("sg-12345", "10.0.0.0/16", 22, "Added by remote.py")


class TestRemoveIpCommand:
    """Tests for the remove-ip CLI command."""

    def test_removes_ip_successfully(self, mocker, test_config):
        """Test that remove-ip command works."""
        mocker.patch(
            "remote.sg.resolve_instance_or_exit",
            return_value=("test-instance", "i-12345"),
        )
        mocker.patch("remote.sg.get_public_ip", return_value="203.0.113.1")
        mocker.patch(
            "remote.sg.get_instance_security_groups",
            return_value=[{"GroupId": "sg-12345", "GroupName": "my-sg"}],
        )
        mocker.patch("remote.sg.get_ssh_ip_rules", return_value=["203.0.113.1/32"])
        mocker.patch("remote.sg.remove_ip_from_security_group")

        result = runner.invoke(app, ["remove-ip", "test-instance", "--yes"])

        assert result.exit_code == 0
        assert "Removed" in result.stdout

    def test_removes_cidr_block(self, mocker, test_config):
        """Test that remove-ip command works with CIDR notation like 0.0.0.0/0."""
        mocker.patch(
            "remote.sg.resolve_instance_or_exit",
            return_value=("test-instance", "i-12345"),
        )
        mocker.patch(
            "remote.sg.get_instance_security_groups",
            return_value=[{"GroupId": "sg-12345", "GroupName": "my-sg"}],
        )
        mocker.patch("remote.sg.get_ssh_ip_rules", return_value=["0.0.0.0/0"])
        mock_remove = mocker.patch("remote.sg.remove_ip_from_security_group")

        result = runner.invoke(app, ["remove-ip", "test-instance", "--ip", "0.0.0.0/0", "--yes"])

        assert result.exit_code == 0
        assert "Removed" in result.stdout
        mock_remove.assert_called_once_with("sg-12345", "0.0.0.0/0", 22)


class TestListIpsCommand:
    """Tests for the list-ips CLI command."""

    def test_lists_ips_successfully(self, mocker, test_config):
        """Test that list-ips command works."""
        mocker.patch(
            "remote.sg.resolve_instance_or_exit",
            return_value=("test-instance", "i-12345"),
        )
        mocker.patch(
            "remote.sg.get_instance_security_groups",
            return_value=[{"GroupId": "sg-12345", "GroupName": "my-sg"}],
        )
        mocker.patch(
            "remote.sg.get_security_group_rules",
            return_value=[
                {
                    "FromPort": 22,
                    "ToPort": 22,
                    "IpProtocol": "tcp",
                    "IpRanges": [
                        {"CidrIp": "10.0.0.1/32", "Description": "Test IP"},
                    ],
                }
            ],
        )

        result = runner.invoke(app, ["list-ips", "test-instance"])

        assert result.exit_code == 0
        assert "10.0.0.1/32" in result.stdout

    def test_shows_message_when_no_rules(self, mocker, test_config):
        """Test that message is shown when no rules exist."""
        mocker.patch(
            "remote.sg.resolve_instance_or_exit",
            return_value=("test-instance", "i-12345"),
        )
        mocker.patch(
            "remote.sg.get_instance_security_groups",
            return_value=[{"GroupId": "sg-12345", "GroupName": "my-sg"}],
        )
        mocker.patch("remote.sg.get_security_group_rules", return_value=[])

        result = runner.invoke(app, ["list-ips", "test-instance"])

        assert result.exit_code == 0
        assert "No IP rules found" in result.stdout


class TestMyIpCommand:
    """Tests for the my-ip CLI command."""

    def test_shows_public_ip(self, mocker, test_config):
        """Test that my-ip command shows the public IP."""
        mocker.patch("remote.sg.get_public_ip", return_value="203.0.113.1")

        result = runner.invoke(app, ["my-ip"])

        assert result.exit_code == 0
        assert "203.0.113.1" in result.stdout
