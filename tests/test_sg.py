"""Tests for security group management module."""

from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from remote.exceptions import ValidationError
from remote.sg import (
    add_ip_to_security_group,
    app,
    attach_security_group_to_instance,
    clear_port_rules,
    clear_ssh_rules,
    create_instance_security_group,
    delete_instance_security_group,
    detach_security_group_from_instance,
    get_instance_security_groups,
    get_instance_vpc_id,
    get_ip_rules_for_port,
    get_public_ip,
    get_security_group_details,
    get_security_group_rules,
    get_ssh_ip_rules,
    remove_ip_from_security_group,
    resolve_port,
    whitelist_ip_for_instance,
)

runner = CliRunner()


class TestResolvePort:
    """Tests for resolve_port function."""

    def test_resolves_numeric_string(self):
        """Test that numeric strings are resolved to port numbers."""
        assert resolve_port("22") == 22
        assert resolve_port("80") == 80
        assert resolve_port("443") == 443
        assert resolve_port("8080") == 8080

    def test_resolves_service_names(self):
        """Test that service names are resolved to port numbers."""
        assert resolve_port("ssh") == 22
        assert resolve_port("http") == 80
        assert resolve_port("https") == 443
        assert resolve_port("syncthing") == 22000
        assert resolve_port("syncthing-gui") == 8384
        assert resolve_port("jupyter") == 8888
        assert resolve_port("rdp") == 3389
        assert resolve_port("postgres") == 5432
        assert resolve_port("mysql") == 3306
        assert resolve_port("redis") == 6379

    def test_case_insensitive(self):
        """Test that service name lookup is case-insensitive."""
        assert resolve_port("SSH") == 22
        assert resolve_port("Http") == 80

    def test_strips_whitespace(self):
        """Test that whitespace is stripped from service names."""
        assert resolve_port(" ssh ") == 22

    def test_raises_on_invalid_port_number(self):
        """Test that invalid port numbers raise ValidationError."""
        with pytest.raises(ValidationError):
            resolve_port("0")
        with pytest.raises(ValidationError):
            resolve_port("65536")
        with pytest.raises(ValidationError):
            resolve_port("-1")

    def test_raises_on_unknown_service(self):
        """Test that unknown service names raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            resolve_port("unknown-service")
        assert "Unknown port or service" in str(exc_info.value)

    def test_valid_boundary_ports(self):
        """Test port number boundaries."""
        assert resolve_port("1") == 1
        assert resolve_port("65535") == 65535


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


class TestGetIpRulesForPort:
    """Tests for get_ip_rules_for_port function (and get_ssh_ip_rules alias)."""

    def test_returns_ip_ranges_for_port(self, mocker):
        """Test that IP ranges are returned for a specific port."""
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

        result = get_ip_rules_for_port("sg-12345", 22)
        assert len(result) == 2
        assert "10.0.0.1/32" in result
        assert "10.0.0.2/32" in result
        assert "0.0.0.0/0" not in result  # HTTPS rule shouldn't be included

    def test_returns_empty_list_when_no_matching_rules(self, mocker):
        """Test that empty list is returned when no matching rules exist."""
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

        result = get_ip_rules_for_port("sg-12345", 22)
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

        result = get_ip_rules_for_port("sg-12345", 22)
        assert "10.0.0.1/32" in result

    def test_alias_get_ssh_ip_rules(self, mocker):
        """Test that get_ssh_ip_rules is an alias for get_ip_rules_for_port."""
        assert get_ssh_ip_rules is get_ip_rules_for_port


class TestClearPortRules:
    """Tests for clear_port_rules function (and clear_ssh_rules alias)."""

    def test_clears_all_rules(self, mocker):
        """Test that all rules for a port are cleared."""
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

        result = clear_port_rules("sg-12345", 22)

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

        result = clear_port_rules("sg-12345", 22, exclude_ip="10.0.0.1")

        assert result == 1
        mock_remove.assert_called_once_with("sg-12345", "10.0.0.2", 22)

    def test_alias_clear_ssh_rules(self):
        """Test that clear_ssh_rules is an alias for clear_port_rules."""
        assert clear_ssh_rules is clear_port_rules


class TestWhitelistIpForInstance:
    """Tests for whitelist_ip_for_instance function."""

    def test_whitelists_current_ip(self, mocker):
        """Test that current IP is whitelisted."""
        mocker.patch("remote.sg.get_public_ip", return_value="203.0.113.1")
        mocker.patch(
            "remote.sg.get_instance_security_groups",
            return_value=[{"GroupId": "sg-12345", "GroupName": "my-sg"}],
        )
        mocker.patch("remote.sg.get_ip_rules_for_port", return_value=[])
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
        mocker.patch("remote.sg.get_ip_rules_for_port", return_value=["203.0.113.1/32"])
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
        mocker.patch("remote.sg.get_ip_rules_for_port", return_value=["10.0.0.0/16"])
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
        mocker.patch("remote.sg.get_ip_rules_for_port", return_value=[])
        mock_clear = mocker.patch("remote.sg.clear_port_rules")
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

    def test_multi_port_whitelisting(self, mocker):
        """Test whitelisting across multiple ports."""
        mocker.patch(
            "remote.sg.get_instance_security_groups",
            return_value=[{"GroupId": "sg-12345", "GroupName": "my-sg"}],
        )
        mocker.patch("remote.sg.get_ip_rules_for_port", return_value=[])
        mock_add = mocker.patch("remote.sg.add_ip_to_security_group")

        ip, modified = whitelist_ip_for_instance(
            "i-12345", ip_address="203.0.113.1", ports=[22, 22000, 8384]
        )

        assert ip == "203.0.113.1"
        assert modified == ["sg-12345"]
        assert mock_add.call_count == 3
        # Verify each port was called
        call_ports = [call.args[2] for call in mock_add.call_args_list]
        assert sorted(call_ports) == [22, 8384, 22000]


# ============================================================================
# Per-instance security group tests (Phase 3)
# ============================================================================


class TestGetInstanceVpcId:
    """Tests for get_instance_vpc_id function."""

    def test_returns_vpc_id(self, mocker):
        """Test that VPC ID is returned for an instance."""
        mock_ec2 = mocker.patch("remote.sg.get_ec2_client")
        mock_ec2.return_value.describe_instances.return_value = {
            "Reservations": [{"Instances": [{"VpcId": "vpc-12345"}]}]
        }

        result = get_instance_vpc_id("i-12345")
        assert result == "vpc-12345"

    def test_raises_when_no_reservations(self, mocker):
        """Test that ValidationError is raised when no reservations found."""
        mock_ec2 = mocker.patch("remote.sg.get_ec2_client")
        mock_ec2.return_value.describe_instances.return_value = {"Reservations": []}

        with pytest.raises(ValidationError) as exc_info:
            get_instance_vpc_id("i-12345")
        assert "not found" in str(exc_info.value)

    def test_raises_when_no_vpc_id(self, mocker):
        """Test that ValidationError is raised when instance has no VPC ID."""
        mock_ec2 = mocker.patch("remote.sg.get_ec2_client")
        mock_ec2.return_value.describe_instances.return_value = {
            "Reservations": [{"Instances": [{}]}]
        }

        with pytest.raises(ValidationError) as exc_info:
            get_instance_vpc_id("i-12345")
        assert "no VPC ID" in str(exc_info.value)


class TestCreateInstanceSecurityGroup:
    """Tests for create_instance_security_group function."""

    def test_creates_security_group(self, mocker):
        """Test that security group is created with correct parameters."""
        mock_ec2 = mocker.patch("remote.sg.get_ec2_client")
        mock_ec2.return_value.create_security_group.return_value = {"GroupId": "sg-new123"}

        result = create_instance_security_group("my-instance", "vpc-12345")

        assert result == "sg-new123"
        mock_ec2.return_value.create_security_group.assert_called_once_with(
            GroupName="remotepy-my-instance",
            Description="Managed by remotepy for instance my-instance",
            VpcId="vpc-12345",
            TagSpecifications=[
                {
                    "ResourceType": "security-group",
                    "Tags": [
                        {"Key": "Name", "Value": "remotepy-my-instance"},
                        {"Key": "ManagedBy", "Value": "remotepy"},
                    ],
                }
            ],
        )


class TestDeleteInstanceSecurityGroup:
    """Tests for delete_instance_security_group function."""

    def test_deletes_security_group(self, mocker):
        """Test that security group is found and deleted."""
        mock_ec2 = mocker.patch("remote.sg.get_ec2_client")
        mock_ec2.return_value.describe_security_groups.return_value = {
            "SecurityGroups": [{"GroupId": "sg-12345"}]
        }

        result = delete_instance_security_group("my-instance", "vpc-12345")

        assert result == "sg-12345"
        mock_ec2.return_value.delete_security_group.assert_called_once_with(GroupId="sg-12345")

    def test_returns_none_when_not_found(self, mocker):
        """Test that None is returned when security group not found."""
        mock_ec2 = mocker.patch("remote.sg.get_ec2_client")
        mock_ec2.return_value.describe_security_groups.return_value = {"SecurityGroups": []}

        result = delete_instance_security_group("my-instance", "vpc-12345")

        assert result is None


class TestAttachSecurityGroup:
    """Tests for attach_security_group_to_instance function."""

    def test_attaches_security_group(self, mocker):
        """Test that security group is attached to instance."""
        mocker.patch(
            "remote.sg.get_instance_security_groups",
            return_value=[{"GroupId": "sg-existing", "GroupName": "existing"}],
        )
        mock_ec2 = mocker.patch("remote.sg.get_ec2_client")

        attach_security_group_to_instance("i-12345", "sg-new123")

        mock_ec2.return_value.modify_instance_attribute.assert_called_once_with(
            InstanceId="i-12345",
            Groups=["sg-existing", "sg-new123"],
        )

    def test_skips_if_already_attached(self, mocker):
        """Test that no-op if SG is already attached."""
        mocker.patch(
            "remote.sg.get_instance_security_groups",
            return_value=[{"GroupId": "sg-12345", "GroupName": "my-sg"}],
        )
        mock_ec2 = mocker.patch("remote.sg.get_ec2_client")

        attach_security_group_to_instance("i-12345", "sg-12345")

        mock_ec2.return_value.modify_instance_attribute.assert_not_called()


class TestDetachSecurityGroup:
    """Tests for detach_security_group_from_instance function."""

    def test_detaches_security_group(self, mocker):
        """Test that security group is detached from instance."""
        mocker.patch(
            "remote.sg.get_instance_security_groups",
            return_value=[
                {"GroupId": "sg-existing", "GroupName": "existing"},
                {"GroupId": "sg-remove", "GroupName": "to-remove"},
            ],
        )
        mock_ec2 = mocker.patch("remote.sg.get_ec2_client")

        detach_security_group_from_instance("i-12345", "sg-remove")

        mock_ec2.return_value.modify_instance_attribute.assert_called_once_with(
            InstanceId="i-12345",
            Groups=["sg-existing"],
        )

    def test_raises_if_last_security_group(self, mocker):
        """Test that ValidationError is raised if removing last SG."""
        mocker.patch(
            "remote.sg.get_instance_security_groups",
            return_value=[{"GroupId": "sg-only", "GroupName": "only"}],
        )

        with pytest.raises(ValidationError) as exc_info:
            detach_security_group_from_instance("i-12345", "sg-only")
        assert "Cannot remove the last" in str(exc_info.value)

    def test_skips_if_not_attached(self, mocker):
        """Test that no-op if SG is not attached."""
        mocker.patch(
            "remote.sg.get_instance_security_groups",
            return_value=[{"GroupId": "sg-12345", "GroupName": "my-sg"}],
        )
        mock_ec2 = mocker.patch("remote.sg.get_ec2_client")

        detach_security_group_from_instance("i-12345", "sg-nonexistent")

        mock_ec2.return_value.modify_instance_attribute.assert_not_called()


# ============================================================================
# CLI Command Tests
# ============================================================================


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
        mocker.patch("remote.sg.get_ip_rules_for_port", return_value=[])
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
        mocker.patch("remote.sg.get_ip_rules_for_port", return_value=[])
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
        mocker.patch("remote.sg.get_ip_rules_for_port", return_value=[])
        mock_add = mocker.patch("remote.sg.add_ip_to_security_group")

        result = runner.invoke(app, ["add-ip", "test-instance", "--ip", "10.0.0.0/16"])

        assert result.exit_code == 0
        assert "10.0.0.0/16" in result.stdout
        mock_add.assert_called_once_with("sg-12345", "10.0.0.0/16", 22, "Added by remote.py")

    def test_adds_ip_with_service_name_port(self, mocker, test_config):
        """Test that add-ip command works with service name ports."""
        mocker.patch(
            "remote.sg.resolve_instance_or_exit",
            return_value=("test-instance", "i-12345"),
        )
        mocker.patch(
            "remote.sg.get_instance_security_groups",
            return_value=[{"GroupId": "sg-12345", "GroupName": "my-sg"}],
        )
        mocker.patch("remote.sg.get_ip_rules_for_port", return_value=[])
        mock_add = mocker.patch("remote.sg.add_ip_to_security_group")

        result = runner.invoke(
            app, ["add-ip", "test-instance", "--ip", "10.0.0.1", "--port", "https"]
        )

        assert result.exit_code == 0
        mock_add.assert_called_once_with("sg-12345", "10.0.0.1", 443, "Added by remote.py")

    def test_adds_ip_with_multiple_ports(self, mocker, test_config):
        """Test that add-ip command works with multiple ports."""
        mocker.patch(
            "remote.sg.resolve_instance_or_exit",
            return_value=("test-instance", "i-12345"),
        )
        mocker.patch(
            "remote.sg.get_instance_security_groups",
            return_value=[{"GroupId": "sg-12345", "GroupName": "my-sg"}],
        )
        mocker.patch("remote.sg.get_ip_rules_for_port", return_value=[])
        mock_add = mocker.patch("remote.sg.add_ip_to_security_group")

        result = runner.invoke(
            app,
            ["add-ip", "test-instance", "--ip", "10.0.0.1", "--port", "ssh", "--port", "syncthing"],
        )

        assert result.exit_code == 0
        assert mock_add.call_count == 2


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
        mocker.patch("remote.sg.get_ip_rules_for_port", return_value=["203.0.113.1/32"])
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
        mocker.patch("remote.sg.get_ip_rules_for_port", return_value=["0.0.0.0/0"])
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

    def test_list_ips_all_flag(self, mocker, test_config):
        """Test that --all flag shows all inbound rules with port columns."""
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
                    "IpRanges": [{"CidrIp": "10.0.0.1/32", "Description": "SSH"}],
                },
                {
                    "FromPort": 443,
                    "ToPort": 443,
                    "IpProtocol": "tcp",
                    "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "HTTPS"}],
                },
            ],
        )

        result = runner.invoke(app, ["list-ips", "test-instance", "--all"])

        assert result.exit_code == 0
        assert "10.0.0.1/32" in result.stdout
        assert "0.0.0.0/0" in result.stdout
        assert "All Inbound IP Rules" in result.stdout

    def test_list_ips_with_service_name_port(self, mocker, test_config):
        """Test list-ips with service name port filter."""
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
                    "FromPort": 443,
                    "ToPort": 443,
                    "IpProtocol": "tcp",
                    "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "HTTPS"}],
                },
            ],
        )

        result = runner.invoke(app, ["list-ips", "test-instance", "--port", "https"])

        assert result.exit_code == 0
        assert "0.0.0.0/0" in result.stdout


class TestCreateSgCommand:
    """Tests for the sg create CLI command."""

    def test_creates_and_attaches_sg(self, mocker, test_config):
        """Test that sg create command creates and attaches a security group."""
        mocker.patch(
            "remote.sg.resolve_instance_or_exit",
            return_value=("test-instance", "i-12345"),
        )
        mock_vpc = mocker.patch("remote.sg.get_instance_vpc_id", return_value="vpc-12345")
        mock_create = mocker.patch(
            "remote.sg.create_instance_security_group", return_value="sg-new123"
        )
        mock_attach = mocker.patch("remote.sg.attach_security_group_to_instance")

        result = runner.invoke(app, ["create", "test-instance"])

        assert result.exit_code == 0
        assert "Created and attached" in result.stdout
        assert "remotepy-test-instance" in result.stdout
        mock_vpc.assert_called_once_with("i-12345")
        mock_create.assert_called_once_with("test-instance", "vpc-12345")
        mock_attach.assert_called_once_with("i-12345", "sg-new123")


class TestDeleteSgCommand:
    """Tests for the sg delete CLI command."""

    def test_deletes_sg(self, mocker, test_config):
        """Test that sg delete command detaches and deletes a security group."""
        mocker.patch(
            "remote.sg.resolve_instance_or_exit",
            return_value=("test-instance", "i-12345"),
        )
        mocker.patch("remote.sg.get_instance_vpc_id", return_value="vpc-12345")
        mock_ec2 = mocker.patch("remote.sg.get_ec2_client")
        mock_ec2.return_value.describe_security_groups.return_value = {
            "SecurityGroups": [{"GroupId": "sg-12345"}]
        }
        mock_detach = mocker.patch("remote.sg.detach_security_group_from_instance")
        mock_delete = mocker.patch(
            "remote.sg.delete_instance_security_group", return_value="sg-12345"
        )

        result = runner.invoke(app, ["delete", "test-instance", "--yes"])

        assert result.exit_code == 0
        assert "Deleted" in result.stdout
        mock_detach.assert_called_once_with("i-12345", "sg-12345")
        mock_delete.assert_called_once_with("test-instance", "vpc-12345")

    def test_delete_sg_not_found(self, mocker, test_config):
        """Test that sg delete handles missing SG gracefully."""
        mocker.patch(
            "remote.sg.resolve_instance_or_exit",
            return_value=("test-instance", "i-12345"),
        )
        mocker.patch("remote.sg.get_instance_vpc_id", return_value="vpc-12345")
        mock_ec2 = mocker.patch("remote.sg.get_ec2_client")
        mock_ec2.return_value.describe_security_groups.return_value = {"SecurityGroups": []}

        result = runner.invoke(app, ["delete", "test-instance", "--yes"])

        assert result.exit_code == 0
        assert "not found" in result.stdout


class TestMyIpCommand:
    """Tests for the my-ip CLI command."""

    def test_shows_public_ip(self, mocker, test_config):
        """Test that my-ip command shows the public IP."""
        mocker.patch("remote.sg.get_public_ip", return_value="203.0.113.1")

        result = runner.invoke(app, ["my-ip"])

        assert result.exit_code == 0
        assert "203.0.113.1" in result.stdout


class TestGetSecurityGroupDetails:
    """Tests for get_security_group_details function."""

    def test_returns_full_details(self, mocker):
        """Test that full SG details are returned."""
        mock_ec2 = mocker.patch("remote.sg.get_ec2_client")
        mock_ec2.return_value.describe_security_groups.return_value = {
            "SecurityGroups": [
                {
                    "GroupId": "sg-12345",
                    "GroupName": "my-sg",
                    "Description": "My security group",
                    "IpPermissions": [{"FromPort": 22, "ToPort": 22}],
                    "Tags": [{"Key": "ManagedBy", "Value": "remotepy"}],
                },
                {
                    "GroupId": "sg-67890",
                    "GroupName": "other-sg",
                    "Description": "Other group",
                    "IpPermissions": [],
                    "Tags": [],
                },
            ]
        }

        result = get_security_group_details(["sg-12345", "sg-67890"])

        assert len(result) == 2
        assert result[0]["GroupId"] == "sg-12345"
        assert result[0]["Description"] == "My security group"
        assert result[1]["GroupId"] == "sg-67890"
        mock_ec2.return_value.describe_security_groups.assert_called_once_with(
            GroupIds=["sg-12345", "sg-67890"]
        )

    def test_returns_empty_list_for_empty_input(self):
        """Test that empty input returns empty list without API call."""
        result = get_security_group_details([])
        assert result == []


class TestListSgsCommand:
    """Tests for the sg list CLI command."""

    def test_list_sgs_shows_table(self, mocker, test_config):
        """Test that list command shows a table with SG details."""
        mocker.patch(
            "remote.sg.resolve_instance_or_exit",
            return_value=("test-instance", "i-12345"),
        )
        mocker.patch(
            "remote.sg.get_instance_security_groups",
            return_value=[
                {"GroupId": "sg-12345", "GroupName": "my-sg"},
                {"GroupId": "sg-67890", "GroupName": "remotepy-test-instance"},
            ],
        )
        mocker.patch(
            "remote.sg.get_security_group_details",
            return_value=[
                {
                    "GroupId": "sg-12345",
                    "GroupName": "my-sg",
                    "Description": "Default SG",
                    "IpPermissions": [
                        {"FromPort": 22, "ToPort": 22, "IpProtocol": "tcp"},
                        {"FromPort": 443, "ToPort": 443, "IpProtocol": "tcp"},
                    ],
                    "Tags": [],
                },
                {
                    "GroupId": "sg-67890",
                    "GroupName": "remotepy-test-instance",
                    "Description": "Managed by remotepy for instance test-instance",
                    "IpPermissions": [
                        {"FromPort": 22, "ToPort": 22, "IpProtocol": "tcp"},
                    ],
                    "Tags": [
                        {"Key": "Name", "Value": "remotepy-test-instance"},
                        {"Key": "ManagedBy", "Value": "remotepy"},
                    ],
                },
            ],
        )

        result = runner.invoke(app, ["list", "test-instance"])

        assert result.exit_code == 0
        assert "my-sg" in result.stdout
        assert "sg-12345" in result.stdout
        assert "remotepy-test-instance" in result.stdout
        assert "sg-67890" in result.stdout
        assert "Yes" in result.stdout  # Managed column for remotepy SG
        assert "Security Groups for 'test-instance'" in result.stdout

    def test_list_sgs_no_security_groups(self, mocker, test_config):
        """Test that error is shown when instance has no security groups."""
        mocker.patch(
            "remote.sg.resolve_instance_or_exit",
            return_value=("test-instance", "i-12345"),
        )
        mocker.patch(
            "remote.sg.get_instance_security_groups",
            return_value=[],
        )

        result = runner.invoke(app, ["list", "test-instance"])

        assert result.exit_code == 1
        assert "No security groups found" in result.stdout

    def test_list_sgs_single_sg(self, mocker, test_config):
        """Test that list command works with a single security group."""
        mocker.patch(
            "remote.sg.resolve_instance_or_exit",
            return_value=("test-instance", "i-12345"),
        )
        mocker.patch(
            "remote.sg.get_instance_security_groups",
            return_value=[{"GroupId": "sg-12345", "GroupName": "my-sg"}],
        )
        mocker.patch(
            "remote.sg.get_security_group_details",
            return_value=[
                {
                    "GroupId": "sg-12345",
                    "GroupName": "my-sg",
                    "Description": "My only SG",
                    "IpPermissions": [],
                    "Tags": [],
                },
            ],
        )

        result = runner.invoke(app, ["list", "test-instance"])

        assert result.exit_code == 0
        assert "my-sg" in result.stdout
        assert "sg-12345" in result.stdout
        assert "0" in result.stdout  # Zero inbound rules
