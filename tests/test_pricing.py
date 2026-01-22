"""Tests for the pricing module."""

import json
from unittest.mock import MagicMock

from botocore.exceptions import ClientError, NoCredentialsError

from remote.pricing import (
    REGION_TO_LOCATION,
    clear_price_cache,
    clear_region_location_cache,
    format_price,
    get_current_region,
    get_instance_price,
    get_instance_price_with_fallback,
    get_pricing_client,
    get_region_location,
    get_ssm_client,
)


class TestGetPricingClient:
    """Test the get_pricing_client function."""

    def test_should_create_pricing_client_in_us_east_1(self, mocker):
        """Should create pricing client in us-east-1 region."""
        mock_boto3 = mocker.patch("remote.pricing.boto3")

        # Clear cache to ensure fresh client creation
        get_pricing_client.cache_clear()

        get_pricing_client()

        mock_boto3.client.assert_called_once_with("pricing", region_name="us-east-1")

    def test_should_cache_pricing_client(self, mocker):
        """Should return cached client on subsequent calls."""
        mock_boto3 = mocker.patch("remote.pricing.boto3")
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        # Clear cache first
        get_pricing_client.cache_clear()

        client1 = get_pricing_client()
        client2 = get_pricing_client()

        # Should only create once
        assert mock_boto3.client.call_count == 1
        assert client1 is client2


class TestGetCurrentRegion:
    """Test the get_current_region function."""

    def test_should_return_session_region(self, mocker):
        """Should return the region from the boto3 session."""
        mock_session = MagicMock()
        mock_session.region_name = "eu-west-1"
        mocker.patch("remote.pricing.boto3.session.Session", return_value=mock_session)

        result = get_current_region()

        assert result == "eu-west-1"

    def test_should_default_to_us_east_1_when_no_region(self, mocker):
        """Should return us-east-1 when session has no region."""
        mock_session = MagicMock()
        mock_session.region_name = None
        mocker.patch("remote.pricing.boto3.session.Session", return_value=mock_session)

        result = get_current_region()

        assert result == "us-east-1"


class TestGetSsmClient:
    """Test the get_ssm_client function."""

    def test_should_create_ssm_client_in_us_east_1(self, mocker):
        """Should create SSM client in us-east-1 region."""
        mock_boto3 = mocker.patch("remote.pricing.boto3")

        # Clear cache to ensure fresh client creation
        get_ssm_client.cache_clear()

        get_ssm_client()

        mock_boto3.client.assert_called_once_with("ssm", region_name="us-east-1")

    def test_should_cache_ssm_client(self, mocker):
        """Should return cached client on subsequent calls."""
        mock_boto3 = mocker.patch("remote.pricing.boto3")
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        # Clear cache first
        get_ssm_client.cache_clear()

        client1 = get_ssm_client()
        client2 = get_ssm_client()

        # Should only create once
        assert mock_boto3.client.call_count == 1
        assert client1 is client2


class TestGetRegionLocation:
    """Test the get_region_location function."""

    def setup_method(self):
        """Clear the cache before each test."""
        clear_region_location_cache()

    def test_should_return_location_for_known_region(self):
        """Should return location from static mapping for known regions."""
        result = get_region_location("us-east-1")

        assert result == "US East (N. Virginia)"

    def test_should_return_location_for_all_static_regions(self):
        """Should return correct location for all regions in static mapping."""
        expected_mappings = {
            "us-east-1": "US East (N. Virginia)",
            "us-east-2": "US East (Ohio)",
            "eu-west-1": "EU (Ireland)",
            "ap-northeast-1": "Asia Pacific (Tokyo)",
        }
        for region, expected_location in expected_mappings.items():
            result = get_region_location(region)
            assert result == expected_location, f"Failed for region {region}"

    def test_should_fetch_dynamically_for_unknown_region(self, mocker):
        """Should fetch location from SSM for regions not in static mapping."""
        mock_client = MagicMock()
        mock_client.get_parameter.return_value = {"Parameter": {"Value": "Middle East (Bahrain)"}}
        mocker.patch("remote.pricing.get_ssm_client", return_value=mock_client)

        result = get_region_location("me-south-1")

        assert result == "Middle East (Bahrain)"
        mock_client.get_parameter.assert_called_once_with(
            Name="/aws/service/global-infrastructure/regions/me-south-1/longName"
        )

    def test_should_return_none_for_ssm_parameter_not_found(self, mocker):
        """Should return None when SSM parameter is not found."""
        mock_client = MagicMock()
        mock_client.get_parameter.side_effect = ClientError(
            {"Error": {"Code": "ParameterNotFound", "Message": "Not found"}},
            "GetParameter",
        )
        mocker.patch("remote.pricing.get_ssm_client", return_value=mock_client)

        result = get_region_location("invalid-region")

        assert result is None

    def test_should_return_none_for_ssm_client_error(self, mocker):
        """Should return None on SSM client error."""
        mock_client = MagicMock()
        mock_client.get_parameter.side_effect = ClientError(
            {"Error": {"Code": "ServiceException", "Message": "Error"}},
            "GetParameter",
        )
        mocker.patch("remote.pricing.get_ssm_client", return_value=mock_client)

        result = get_region_location("some-region")

        assert result is None

    def test_should_return_none_for_no_credentials(self, mocker):
        """Should return None when AWS credentials are missing."""
        mock_client = MagicMock()
        mock_client.get_parameter.side_effect = NoCredentialsError()
        mocker.patch("remote.pricing.get_ssm_client", return_value=mock_client)

        result = get_region_location("some-region")

        assert result is None

    def test_should_return_none_for_malformed_response(self, mocker):
        """Should return None for unexpected SSM response format."""
        mock_client = MagicMock()
        mock_client.get_parameter.return_value = {"unexpected": "format"}
        mocker.patch("remote.pricing.get_ssm_client", return_value=mock_client)

        result = get_region_location("some-region")

        assert result is None

    def test_should_cache_dynamic_results(self, mocker):
        """Should cache results from dynamic SSM lookup."""
        mock_client = MagicMock()
        mock_client.get_parameter.return_value = {"Parameter": {"Value": "Middle East (Bahrain)"}}
        mocker.patch("remote.pricing.get_ssm_client", return_value=mock_client)

        # Call twice with same region
        result1 = get_region_location("me-south-1")
        result2 = get_region_location("me-south-1")

        # Should only call SSM once due to caching
        assert mock_client.get_parameter.call_count == 1
        assert result1 == result2 == "Middle East (Bahrain)"

    def test_should_not_call_ssm_for_known_regions(self, mocker):
        """Should not call SSM for regions in static mapping."""
        mock_client = MagicMock()
        mocker.patch("remote.pricing.get_ssm_client", return_value=mock_client)

        get_region_location("us-east-1")

        mock_client.get_parameter.assert_not_called()


class TestClearRegionLocationCache:
    """Test the clear_region_location_cache function."""

    def setup_method(self):
        """Clear the cache before each test."""
        clear_region_location_cache()

    def test_should_clear_cache(self, mocker):
        """Should clear the region location cache."""
        mock_client = MagicMock()
        mock_client.get_parameter.return_value = {"Parameter": {"Value": "Middle East (Bahrain)"}}
        mocker.patch("remote.pricing.get_ssm_client", return_value=mock_client)

        # First call
        get_region_location("me-south-1")
        assert mock_client.get_parameter.call_count == 1

        # Clear cache
        clear_region_location_cache()

        # Second call should hit SSM again
        get_region_location("me-south-1")
        assert mock_client.get_parameter.call_count == 2


class TestGetInstancePrice:
    """Test the get_instance_price function."""

    def setup_method(self):
        """Clear the price cache before each test."""
        clear_price_cache()

    def test_should_return_price_for_valid_instance_type(self, mocker):
        """Should return hourly price for a valid instance type."""
        # Create mock pricing response
        price_data = {
            "terms": {
                "OnDemand": {
                    "term1": {"priceDimensions": {"dim1": {"pricePerUnit": {"USD": "0.0104"}}}}
                }
            }
        }

        mock_client = MagicMock()
        mock_client.get_products.return_value = {"PriceList": [json.dumps(price_data)]}
        mocker.patch("remote.pricing.get_pricing_client", return_value=mock_client)

        result = get_instance_price("t3.micro", "us-east-1")

        assert result == 0.0104
        mock_client.get_products.assert_called_once()

    def test_should_return_none_for_unknown_region(self, mocker):
        """Should return None for regions not found in static mapping or SSM."""
        # Mock SSM to return ParameterNotFound for unknown region
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.side_effect = ClientError(
            {"Error": {"Code": "ParameterNotFound", "Message": "Not found"}},
            "GetParameter",
        )
        mocker.patch("remote.pricing.get_ssm_client", return_value=mock_ssm)

        result = get_instance_price("t3.micro", "unknown-region")

        assert result is None

    def test_should_return_none_for_empty_price_list(self, mocker):
        """Should return None when no pricing data is found."""
        mock_client = MagicMock()
        mock_client.get_products.return_value = {"PriceList": []}
        mocker.patch("remote.pricing.get_pricing_client", return_value=mock_client)

        result = get_instance_price("invalid-type", "us-east-1")

        assert result is None

    def test_should_return_none_on_client_error(self, mocker):
        """Should return None when AWS API returns an error."""
        mock_client = MagicMock()
        mock_client.get_products.side_effect = ClientError(
            {"Error": {"Code": "ServiceException", "Message": "Error"}}, "GetProducts"
        )
        mocker.patch("remote.pricing.get_pricing_client", return_value=mock_client)

        result = get_instance_price("t3.micro", "us-east-1")

        assert result is None

    def test_should_return_none_on_no_credentials(self, mocker):
        """Should return None when AWS credentials are missing."""
        mock_client = MagicMock()
        mock_client.get_products.side_effect = NoCredentialsError()
        mocker.patch("remote.pricing.get_pricing_client", return_value=mock_client)

        result = get_instance_price("t3.micro", "us-east-1")

        assert result is None

    def test_should_return_none_on_json_decode_error(self, mocker):
        """Should return None when price data is malformed."""
        mock_client = MagicMock()
        mock_client.get_products.return_value = {"PriceList": ["not-valid-json"]}
        mocker.patch("remote.pricing.get_pricing_client", return_value=mock_client)

        result = get_instance_price("t3.micro", "us-east-1")

        assert result is None

    def test_should_return_none_when_on_demand_terms_missing(self, mocker):
        """Should return None when OnDemand terms are missing."""
        price_data = {"terms": {}}
        mock_client = MagicMock()
        mock_client.get_products.return_value = {"PriceList": [json.dumps(price_data)]}
        mocker.patch("remote.pricing.get_pricing_client", return_value=mock_client)

        result = get_instance_price("t3.micro", "us-east-1")

        assert result is None

    def test_should_use_current_region_when_not_specified(self, mocker):
        """Should use current session region when region is not specified."""
        mock_session = MagicMock()
        mock_session.region_name = "eu-west-1"
        mocker.patch("remote.pricing.boto3.session.Session", return_value=mock_session)

        price_data = {
            "terms": {
                "OnDemand": {
                    "term1": {"priceDimensions": {"dim1": {"pricePerUnit": {"USD": "0.0120"}}}}
                }
            }
        }
        mock_client = MagicMock()
        mock_client.get_products.return_value = {"PriceList": [json.dumps(price_data)]}
        mocker.patch("remote.pricing.get_pricing_client", return_value=mock_client)

        result = get_instance_price("t3.micro")

        assert result == 0.0120
        # Verify the location filter was for EU (Ireland)
        call_args = mock_client.get_products.call_args
        filters = call_args.kwargs["Filters"]
        location_filter = next(f for f in filters if f["Field"] == "location")
        assert location_filter["Value"] == "EU (Ireland)"

    def test_should_cache_results(self, mocker):
        """Should cache pricing results to reduce API calls."""
        price_data = {
            "terms": {
                "OnDemand": {
                    "term1": {"priceDimensions": {"dim1": {"pricePerUnit": {"USD": "0.0104"}}}}
                }
            }
        }
        mock_client = MagicMock()
        mock_client.get_products.return_value = {"PriceList": [json.dumps(price_data)]}
        mocker.patch("remote.pricing.get_pricing_client", return_value=mock_client)

        # Call twice with same parameters
        result1 = get_instance_price("t3.micro", "us-east-1")
        result2 = get_instance_price("t3.micro", "us-east-1")

        # Should only call API once due to caching
        assert mock_client.get_products.call_count == 1
        assert result1 == result2 == 0.0104


class TestFormatPrice:
    """Test the format_price function."""

    def test_should_format_regular_price(self):
        """Should format price with two decimal places."""
        result = format_price(10.50)

        assert result == "$10.50"

    def test_should_format_small_price_with_more_precision(self):
        """Should use more decimal places for very small prices."""
        result = format_price(0.0052)

        assert result == "$0.0052"

    def test_should_return_dash_for_none(self):
        """Should return dash for None price."""
        result = format_price(None)

        assert result == "-"

    def test_should_use_custom_prefix(self):
        """Should use custom currency prefix."""
        result = format_price(10.50, prefix="EUR ")

        assert result == "EUR 10.50"


class TestGetInstancePriceWithFallback:
    """Test the get_instance_price_with_fallback function."""

    def setup_method(self):
        """Clear the price cache before each test."""
        clear_price_cache()

    def test_should_return_price_without_fallback_for_known_region(self, mocker):
        """Should return price and False when region is in mapping."""
        price_data = {
            "terms": {
                "OnDemand": {
                    "term1": {"priceDimensions": {"dim1": {"pricePerUnit": {"USD": "0.0104"}}}}
                }
            }
        }
        mock_client = MagicMock()
        mock_client.get_products.return_value = {"PriceList": [json.dumps(price_data)]}
        mocker.patch("remote.pricing.get_pricing_client", return_value=mock_client)

        price, fallback_used = get_instance_price_with_fallback("t3.micro", "us-east-1")

        assert price == 0.0104
        assert fallback_used is False

    def test_should_fallback_to_us_east_1_for_unknown_region(self, mocker):
        """Should return us-east-1 price and True for regions not found in SSM."""
        # Mock SSM to return ParameterNotFound for unknown region
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.side_effect = ClientError(
            {"Error": {"Code": "ParameterNotFound", "Message": "Not found"}},
            "GetParameter",
        )
        mocker.patch("remote.pricing.get_ssm_client", return_value=mock_ssm)

        price_data = {
            "terms": {
                "OnDemand": {
                    "term1": {"priceDimensions": {"dim1": {"pricePerUnit": {"USD": "0.0104"}}}}
                }
            }
        }
        mock_client = MagicMock()
        mock_client.get_products.return_value = {"PriceList": [json.dumps(price_data)]}
        mocker.patch("remote.pricing.get_pricing_client", return_value=mock_client)

        price, fallback_used = get_instance_price_with_fallback("t3.micro", "unknown-region")

        assert price == 0.0104
        assert fallback_used is True
        # Verify the location filter was for us-east-1
        call_args = mock_client.get_products.call_args
        filters = call_args.kwargs["Filters"]
        location_filter = next(f for f in filters if f["Field"] == "location")
        assert location_filter["Value"] == "US East (N. Virginia)"

    def test_should_use_current_region_when_not_specified(self, mocker):
        """Should use current session region when region is not specified."""
        mock_session = MagicMock()
        mock_session.region_name = "eu-west-1"
        mocker.patch("remote.pricing.boto3.session.Session", return_value=mock_session)

        price_data = {
            "terms": {
                "OnDemand": {
                    "term1": {"priceDimensions": {"dim1": {"pricePerUnit": {"USD": "0.0120"}}}}
                }
            }
        }
        mock_client = MagicMock()
        mock_client.get_products.return_value = {"PriceList": [json.dumps(price_data)]}
        mocker.patch("remote.pricing.get_pricing_client", return_value=mock_client)

        price, fallback_used = get_instance_price_with_fallback("t3.micro")

        assert price == 0.0120
        assert fallback_used is False

    def test_should_return_none_with_fallback_when_pricing_unavailable(self, mocker):
        """Should return None and True when fallback pricing is also unavailable."""
        # Mock SSM to return ParameterNotFound for unknown region
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.side_effect = ClientError(
            {"Error": {"Code": "ParameterNotFound", "Message": "Not found"}},
            "GetParameter",
        )
        mocker.patch("remote.pricing.get_ssm_client", return_value=mock_ssm)

        mock_client = MagicMock()
        mock_client.get_products.return_value = {"PriceList": []}
        mocker.patch("remote.pricing.get_pricing_client", return_value=mock_client)

        price, fallback_used = get_instance_price_with_fallback("unknown-type", "unknown-region")

        assert price is None
        assert fallback_used is True

    def test_should_use_dynamic_region_without_fallback(self, mocker):
        """Should use dynamically fetched region without fallback."""
        # Mock SSM to return location for a new region
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "Middle East (Bahrain)"}}
        mocker.patch("remote.pricing.get_ssm_client", return_value=mock_ssm)

        price_data = {
            "terms": {
                "OnDemand": {
                    "term1": {"priceDimensions": {"dim1": {"pricePerUnit": {"USD": "0.0150"}}}}
                }
            }
        }
        mock_client = MagicMock()
        mock_client.get_products.return_value = {"PriceList": [json.dumps(price_data)]}
        mocker.patch("remote.pricing.get_pricing_client", return_value=mock_client)

        price, fallback_used = get_instance_price_with_fallback("t3.micro", "me-south-1")

        assert price == 0.0150
        assert fallback_used is False
        # Verify the location filter was for the dynamically fetched location
        call_args = mock_client.get_products.call_args
        filters = call_args.kwargs["Filters"]
        location_filter = next(f for f in filters if f["Field"] == "location")
        assert location_filter["Value"] == "Middle East (Bahrain)"


class TestClearPriceCache:
    """Test the clear_price_cache function."""

    def setup_method(self):
        """Clear the price cache before each test."""
        clear_price_cache()

    def test_should_clear_cache(self, mocker):
        """Should clear the pricing cache."""
        price_data = {
            "terms": {
                "OnDemand": {
                    "term1": {"priceDimensions": {"dim1": {"pricePerUnit": {"USD": "0.10"}}}}
                }
            }
        }
        mock_client = MagicMock()
        mock_client.get_products.return_value = {"PriceList": [json.dumps(price_data)]}
        mocker.patch("remote.pricing.get_pricing_client", return_value=mock_client)

        # First call
        get_instance_price("t3.micro", "us-east-1")
        assert mock_client.get_products.call_count == 1

        # Clear cache
        clear_price_cache()

        # Second call should hit API again
        get_instance_price("t3.micro", "us-east-1")
        assert mock_client.get_products.call_count == 2


class TestRegionToLocationMapping:
    """Test the region to location mapping."""

    def test_should_have_common_regions(self):
        """Should contain mappings for common AWS regions."""
        assert "us-east-1" in REGION_TO_LOCATION
        assert "us-west-2" in REGION_TO_LOCATION
        assert "eu-west-1" in REGION_TO_LOCATION
        assert "ap-northeast-1" in REGION_TO_LOCATION

    def test_location_names_should_be_proper_format(self):
        """Location names should match AWS Pricing API format."""
        for _region, location in REGION_TO_LOCATION.items():
            assert "(" in location
            assert ")" in location
