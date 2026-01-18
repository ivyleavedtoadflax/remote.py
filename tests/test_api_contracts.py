"""Tests for AWS API contract validation.

These tests ensure that our mocked tests use values that would be accepted
by the real AWS APIs, preventing situations where tests pass but real API
calls fail due to parameter mismatches.

Issue #44: This was identified when tests used "Europe (Ireland)" for the
Pricing API location, but AWS actually expects "EU (Ireland)".
"""

import json
from unittest.mock import MagicMock

import pytest

from remote.pricing import REGION_TO_LOCATION, get_instance_price
from tests.fixtures.aws_api_contracts import (
    EC2_INSTANCE_STATE_CODES,
    REGION_TO_LOCATION_EXPECTED,
    VALID_AMI_STATES,
    VALID_AWS_PRICING_LOCATIONS,
    VALID_CAPACITY_STATUS,
    VALID_EBS_SNAPSHOT_STATES,
    VALID_EBS_VOLUME_STATES,
    VALID_EC2_INSTANCE_STATES,
    VALID_OPERATING_SYSTEMS,
    VALID_PRE_INSTALLED_SW,
    VALID_TENANCIES,
    validate_pricing_location,
    validate_region_to_location_mapping,
)

# ============================================================================
# Pricing API Contract Tests
# ============================================================================


class TestPricingApiContracts:
    """Tests ensuring Pricing API parameters match what AWS accepts."""

    def test_region_to_location_mapping_uses_valid_locations(self):
        """All locations in REGION_TO_LOCATION must be valid AWS Pricing API locations.

        This test prevents the issue where mocked tests pass but real API calls
        fail because we used location names that AWS doesn't accept.
        """
        invalid = validate_region_to_location_mapping(REGION_TO_LOCATION)
        assert not invalid, (
            f"REGION_TO_LOCATION contains invalid AWS Pricing API location names:\n"
            f"  {invalid}\n"
            f"Valid locations include: {sorted(list(VALID_AWS_PRICING_LOCATIONS)[:5])}..."
        )

    def test_region_to_location_matches_expected_mapping(self):
        """REGION_TO_LOCATION should match our known-good expected mapping.

        This catches cases where the mapping might have been accidentally changed.
        """
        for region, expected_location in REGION_TO_LOCATION_EXPECTED.items():
            actual_location = REGION_TO_LOCATION.get(region)
            assert actual_location == expected_location, (
                f"Region {region} has incorrect location mapping.\n"
                f"Expected: {expected_location}\n"
                f"Actual: {actual_location}"
            )

    def test_all_expected_regions_are_mapped(self):
        """All expected regions should be present in REGION_TO_LOCATION."""
        missing_regions = set(REGION_TO_LOCATION_EXPECTED.keys()) - set(REGION_TO_LOCATION.keys())
        assert not missing_regions, f"Missing regions in REGION_TO_LOCATION: {missing_regions}"

    def test_pricing_api_request_uses_valid_location(self, mocker):
        """Verify get_instance_price uses valid location names in API requests.

        This test captures the actual API request and validates that the
        location filter value is in our known-good list.
        """
        from remote.pricing import clear_price_cache

        clear_price_cache()

        # Create mock that captures the API request
        mock_client = MagicMock()
        price_data = {
            "terms": {
                "OnDemand": {
                    "term1": {"priceDimensions": {"dim1": {"pricePerUnit": {"USD": "0.0104"}}}}
                }
            }
        }
        mock_client.get_products.return_value = {"PriceList": [json.dumps(price_data)]}
        mocker.patch("remote.pricing.get_pricing_client", return_value=mock_client)

        # Make the API call
        get_instance_price("t3.micro", "eu-west-1")

        # Extract and validate the location filter
        call_args = mock_client.get_products.call_args
        filters = call_args.kwargs["Filters"]
        location_filter = next(f for f in filters if f["Field"] == "location")
        location_value = location_filter["Value"]

        assert validate_pricing_location(location_value), (
            f"get_instance_price used invalid location '{location_value}' for region 'eu-west-1'.\n"
            f"This would cause the real AWS Pricing API to return no results.\n"
            f"Valid locations include: {sorted(list(VALID_AWS_PRICING_LOCATIONS)[:5])}..."
        )

    def test_pricing_api_uses_valid_operating_system(self, mocker):
        """Verify get_instance_price uses valid operatingSystem values."""
        from remote.pricing import clear_price_cache

        clear_price_cache()

        mock_client = MagicMock()
        price_data = {
            "terms": {
                "OnDemand": {
                    "term1": {"priceDimensions": {"dim1": {"pricePerUnit": {"USD": "0.0104"}}}}
                }
            }
        }
        mock_client.get_products.return_value = {"PriceList": [json.dumps(price_data)]}
        mocker.patch("remote.pricing.get_pricing_client", return_value=mock_client)

        get_instance_price("t3.micro", "us-east-1")

        call_args = mock_client.get_products.call_args
        filters = call_args.kwargs["Filters"]
        os_filter = next(f for f in filters if f["Field"] == "operatingSystem")
        os_value = os_filter["Value"]

        assert os_value in VALID_OPERATING_SYSTEMS, (
            f"get_instance_price used invalid operatingSystem '{os_value}'.\n"
            f"Valid values: {VALID_OPERATING_SYSTEMS}"
        )

    def test_pricing_api_uses_valid_tenancy(self, mocker):
        """Verify get_instance_price uses valid tenancy values."""
        from remote.pricing import clear_price_cache

        clear_price_cache()

        mock_client = MagicMock()
        price_data = {
            "terms": {
                "OnDemand": {
                    "term1": {"priceDimensions": {"dim1": {"pricePerUnit": {"USD": "0.0104"}}}}
                }
            }
        }
        mock_client.get_products.return_value = {"PriceList": [json.dumps(price_data)]}
        mocker.patch("remote.pricing.get_pricing_client", return_value=mock_client)

        get_instance_price("t3.micro", "us-east-1")

        call_args = mock_client.get_products.call_args
        filters = call_args.kwargs["Filters"]
        tenancy_filter = next(f for f in filters if f["Field"] == "tenancy")
        tenancy_value = tenancy_filter["Value"]

        assert tenancy_value in VALID_TENANCIES, (
            f"get_instance_price used invalid tenancy '{tenancy_value}'.\n"
            f"Valid values: {VALID_TENANCIES}"
        )

    def test_pricing_api_uses_valid_pre_installed_sw(self, mocker):
        """Verify get_instance_price uses valid preInstalledSw values."""
        from remote.pricing import clear_price_cache

        clear_price_cache()

        mock_client = MagicMock()
        price_data = {
            "terms": {
                "OnDemand": {
                    "term1": {"priceDimensions": {"dim1": {"pricePerUnit": {"USD": "0.0104"}}}}
                }
            }
        }
        mock_client.get_products.return_value = {"PriceList": [json.dumps(price_data)]}
        mocker.patch("remote.pricing.get_pricing_client", return_value=mock_client)

        get_instance_price("t3.micro", "us-east-1")

        call_args = mock_client.get_products.call_args
        filters = call_args.kwargs["Filters"]
        sw_filter = next(f for f in filters if f["Field"] == "preInstalledSw")
        sw_value = sw_filter["Value"]

        assert sw_value in VALID_PRE_INSTALLED_SW, (
            f"get_instance_price used invalid preInstalledSw '{sw_value}'.\n"
            f"Valid values: {VALID_PRE_INSTALLED_SW}"
        )

    def test_pricing_api_uses_valid_capacity_status(self, mocker):
        """Verify get_instance_price uses valid capacitystatus values."""
        from remote.pricing import clear_price_cache

        clear_price_cache()

        mock_client = MagicMock()
        price_data = {
            "terms": {
                "OnDemand": {
                    "term1": {"priceDimensions": {"dim1": {"pricePerUnit": {"USD": "0.0104"}}}}
                }
            }
        }
        mock_client.get_products.return_value = {"PriceList": [json.dumps(price_data)]}
        mocker.patch("remote.pricing.get_pricing_client", return_value=mock_client)

        get_instance_price("t3.micro", "us-east-1")

        call_args = mock_client.get_products.call_args
        filters = call_args.kwargs["Filters"]
        capacity_filter = next(f for f in filters if f["Field"] == "capacitystatus")
        capacity_value = capacity_filter["Value"]

        assert capacity_value in VALID_CAPACITY_STATUS, (
            f"get_instance_price used invalid capacitystatus '{capacity_value}'.\n"
            f"Valid values: {VALID_CAPACITY_STATUS}"
        )


# ============================================================================
# EC2 API Contract Tests
# ============================================================================


class TestEc2ApiContracts:
    """Tests ensuring EC2 API mock data matches real API formats."""

    def test_mock_instance_states_are_valid(self):
        """Mock instance states in test fixtures must be valid EC2 states."""
        from tests.conftest import get_mock_instance

        instance = get_mock_instance()
        state = instance.State.Name

        assert state in VALID_EC2_INSTANCE_STATES, (
            f"Mock instance uses invalid state '{state}'.\n"
            f"Valid EC2 instance states: {VALID_EC2_INSTANCE_STATES}"
        )

    def test_mock_instance_state_codes_are_correct(self):
        """Mock instance state codes must match the actual EC2 state code mapping."""
        from tests.conftest import get_mock_instance

        instance = get_mock_instance()
        state_name = instance.State.Name
        state_code = instance.State.Code

        expected_code = EC2_INSTANCE_STATE_CODES.get(state_name)
        assert state_code == expected_code, (
            f"Mock instance state code mismatch for '{state_name}'.\n"
            f"Expected code: {expected_code}, Actual code: {state_code}"
        )

    def test_all_state_codes_are_documented(self):
        """All valid EC2 states should have documented state codes."""
        for state in VALID_EC2_INSTANCE_STATES:
            assert state in EC2_INSTANCE_STATE_CODES, (
                f"Missing state code mapping for EC2 state '{state}'"
            )

    def test_mock_volumes_response_uses_valid_states(self):
        """Mock volume responses must use valid EBS volume states."""
        from tests.conftest import get_mock_volumes_response

        response = get_mock_volumes_response()
        for volume in response["Volumes"]:
            state = volume["State"]
            assert state in VALID_EBS_VOLUME_STATES, (
                f"Mock volume uses invalid state '{state}'.\n"
                f"Valid EBS volume states: {VALID_EBS_VOLUME_STATES}"
            )

    def test_mock_snapshots_response_uses_valid_states(self):
        """Mock snapshot responses must use valid EBS snapshot states."""
        from tests.conftest import get_mock_snapshots_response

        response = get_mock_snapshots_response()
        for snapshot in response["Snapshots"]:
            state = snapshot["State"]
            assert state in VALID_EBS_SNAPSHOT_STATES, (
                f"Mock snapshot uses invalid state '{state}'.\n"
                f"Valid EBS snapshot states: {VALID_EBS_SNAPSHOT_STATES}"
            )

    def test_mock_amis_response_uses_valid_states(self):
        """Mock AMI responses must use valid AMI states."""
        from tests.conftest import get_mock_amis_response

        response = get_mock_amis_response()
        for ami in response["Images"]:
            state = ami["State"]
            assert state in VALID_AMI_STATES, (
                f"Mock AMI uses invalid state '{state}'.\nValid AMI states: {VALID_AMI_STATES}"
            )


# ============================================================================
# Test Fixture Validation Tests
# ============================================================================


class TestFixtureApiValidation:
    """Meta-tests ensuring test fixtures produce valid API mock data."""

    def test_mock_ec2_instances_fixture_is_valid(self, mock_ec2_instances):
        """The mock_ec2_instances fixture should produce valid API response format."""
        assert "Reservations" in mock_ec2_instances
        for reservation in mock_ec2_instances["Reservations"]:
            assert "Instances" in reservation
            for instance in reservation["Instances"]:
                # Validate required fields exist
                assert "InstanceId" in instance
                assert "State" in instance
                assert "Name" in instance["State"]
                # Validate state is valid
                assert instance["State"]["Name"] in VALID_EC2_INSTANCE_STATES

    def test_mock_ebs_volumes_fixture_is_valid(self, mock_ebs_volumes):
        """The mock_ebs_volumes fixture should produce valid API response format."""
        assert "Volumes" in mock_ebs_volumes
        for volume in mock_ebs_volumes["Volumes"]:
            assert "VolumeId" in volume
            assert "State" in volume
            assert volume["State"] in VALID_EBS_VOLUME_STATES

    def test_mock_ebs_snapshots_fixture_is_valid(self, mock_ebs_snapshots):
        """The mock_ebs_snapshots fixture should produce valid API response format."""
        assert "Snapshots" in mock_ebs_snapshots
        for snapshot in mock_ebs_snapshots["Snapshots"]:
            assert "SnapshotId" in snapshot
            assert "State" in snapshot
            assert snapshot["State"] in VALID_EBS_SNAPSHOT_STATES

    def test_mock_amis_fixture_is_valid(self, mock_amis):
        """The mock_amis fixture should produce valid API response format."""
        assert "Images" in mock_amis
        for ami in mock_amis["Images"]:
            assert "ImageId" in ami
            assert "State" in ami
            assert ami["State"] in VALID_AMI_STATES


# ============================================================================
# Integration Tests (Optional - Require Real AWS Credentials)
# ============================================================================


@pytest.mark.integration
class TestRealAwsApiContracts:
    """Tests that validate against real AWS APIs.

    These tests require AWS credentials and should be run sparingly
    (e.g., weekly in CI, not on every PR).

    Run with: pytest -m integration
    """

    @pytest.mark.skip(reason="Requires real AWS credentials - run manually")
    def test_pricing_api_accepts_our_location_names(self):
        """Validate that AWS Pricing API accepts all our location names.

        This test actually calls the AWS Pricing API to verify that
        the location names we use are accepted.
        """
        import boto3

        pricing = boto3.client("pricing", region_name="us-east-1")

        # Get valid location names from AWS
        response = pricing.get_attribute_values(
            ServiceCode="AmazonEC2",
            AttributeName="location",
        )
        valid_aws_locations = {v["Value"] for v in response["AttributeValues"]}

        # Check each of our locations
        invalid = []
        for region, location in REGION_TO_LOCATION.items():
            if location not in valid_aws_locations:
                invalid.append(f"{region} -> {location}")

        assert not invalid, (
            f"The following location mappings are not accepted by AWS:\n"
            f"  {invalid}\n"
            f"Run this test periodically to catch AWS API changes."
        )
