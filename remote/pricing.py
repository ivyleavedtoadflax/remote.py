"""AWS EC2 instance pricing functionality.

This module provides functions to retrieve EC2 instance pricing information
using the AWS Pricing API.
"""

import json
import logging
from functools import lru_cache
from typing import Any

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)

# Static fallback mapping of AWS region codes to Pricing API location names.
#
# IMPORTANT: The Pricing API uses human-readable location names, NOT region codes.
# These names must match EXACTLY what AWS accepts. Common mistakes:
#   - "Europe (Ireland)" - WRONG (AWS returns no results)
#   - "EU (Ireland)" - CORRECT
#
# This static mapping is used as a fallback when dynamic lookup fails.
# For new regions, the dynamic lookup via get_region_location() will fetch
# the location name from AWS SSM Parameter Store.
#
# See: https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/price-list-query-api.html
_STATIC_REGION_TO_LOCATION: dict[str, str] = {
    "us-east-1": "US East (N. Virginia)",
    "us-east-2": "US East (Ohio)",
    "us-west-1": "US West (N. California)",
    "us-west-2": "US West (Oregon)",
    "eu-west-1": "EU (Ireland)",
    "eu-west-2": "EU (London)",
    "eu-west-3": "EU (Paris)",
    "eu-central-1": "EU (Frankfurt)",
    "eu-north-1": "EU (Stockholm)",
    "eu-south-1": "EU (Milan)",
    "ap-northeast-1": "Asia Pacific (Tokyo)",
    "ap-northeast-2": "Asia Pacific (Seoul)",
    "ap-northeast-3": "Asia Pacific (Osaka)",
    "ap-southeast-1": "Asia Pacific (Singapore)",
    "ap-southeast-2": "Asia Pacific (Sydney)",
    "ap-south-1": "Asia Pacific (Mumbai)",
    "sa-east-1": "South America (Sao Paulo)",
    "ca-central-1": "Canada (Central)",
}

# Public reference to the static mapping for backwards compatibility
# and for test validation against known-good values
REGION_TO_LOCATION: dict[str, str] = _STATIC_REGION_TO_LOCATION


@lru_cache(maxsize=1)
def get_pricing_client() -> Any:
    """Get or create the Pricing client.

    The Pricing API is only available in us-east-1 and ap-south-1.
    We use us-east-1 for consistency.

    Returns:
        boto3 Pricing client instance
    """
    return boto3.client("pricing", region_name="us-east-1")


@lru_cache(maxsize=1)
def get_ssm_client() -> Any:
    """Get or create the SSM client for region lookup.

    Uses us-east-1 as the SSM endpoint for global infrastructure parameters.

    Returns:
        boto3 SSM client instance
    """
    return boto3.client("ssm", region_name="us-east-1")


@lru_cache(maxsize=256)
def get_region_location(region_code: str) -> str | None:
    """Get the Pricing API location name for an AWS region code.

    This function dynamically fetches the location name from AWS SSM Parameter Store,
    which provides authoritative region information. Results are cached to minimize
    API calls.

    If the dynamic lookup fails, falls back to the static mapping.

    Args:
        region_code: The AWS region code (e.g., 'us-east-1', 'eu-west-1')

    Returns:
        The location name for the Pricing API (e.g., 'US East (N. Virginia)'),
        or None if the region is not found.

    Example:
        >>> get_region_location('us-east-1')
        'US East (N. Virginia)'
        >>> get_region_location('eu-west-1')
        'EU (Ireland)'
    """
    # First, try the static mapping for known regions (faster, no API call)
    if region_code in _STATIC_REGION_TO_LOCATION:
        return _STATIC_REGION_TO_LOCATION[region_code]

    # For unknown regions, try dynamic lookup from AWS SSM
    try:
        ssm_client = get_ssm_client()
        param_name = f"/aws/service/global-infrastructure/regions/{region_code}/longName"
        response = ssm_client.get_parameter(Name=param_name)
        location: str = response["Parameter"]["Value"]
        logger.debug(f"Dynamically fetched location for {region_code}: {location}")
        return location
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "ParameterNotFound":
            logger.debug(f"Region {region_code} not found in AWS SSM")
        else:
            logger.debug(f"SSM lookup failed for {region_code}: {e}")
        return None
    except NoCredentialsError:
        logger.debug(f"No credentials for SSM lookup of {region_code}")
        return None
    except (KeyError, TypeError):
        logger.debug(f"Unexpected SSM response format for {region_code}")
        return None


def clear_region_location_cache() -> None:
    """Clear the region location cache.

    Useful for testing or when you want to refresh region data.
    """
    get_region_location.cache_clear()
    get_ssm_client.cache_clear()


def get_current_region() -> str:
    """Get the current AWS region from the session.

    Returns:
        The current AWS region code
    """
    session = boto3.session.Session()
    return session.region_name or "us-east-1"


@lru_cache(maxsize=256)
def get_instance_price(instance_type: str, region: str | None = None) -> float | None:
    """Get the hourly on-demand price for an EC2 instance type.

    Args:
        instance_type: The EC2 instance type (e.g., 't3.micro', 'm5.large')
        region: AWS region code. If None, uses the current session region.

    Returns:
        The hourly price in USD, or None if pricing is unavailable.

    Note:
        This function caches results to reduce API calls.
        Prices are for Linux on-demand instances with shared tenancy.
    """
    if region is None:
        region = get_current_region()

    # Get location name for region (uses dynamic lookup with static fallback)
    location = get_region_location(region)
    if not location:
        # Region not found in static mapping or via dynamic lookup
        return None

    try:
        pricing_client = get_pricing_client()
        response = pricing_client.get_products(
            ServiceCode="AmazonEC2",
            Filters=[
                {"Type": "TERM_MATCH", "Field": "instanceType", "Value": instance_type},
                {"Type": "TERM_MATCH", "Field": "location", "Value": location},
                {"Type": "TERM_MATCH", "Field": "operatingSystem", "Value": "Linux"},
                {"Type": "TERM_MATCH", "Field": "tenancy", "Value": "Shared"},
                {"Type": "TERM_MATCH", "Field": "preInstalledSw", "Value": "NA"},
                {"Type": "TERM_MATCH", "Field": "capacitystatus", "Value": "Used"},
            ],
            MaxResults=1,
        )

        price_list = response.get("PriceList", [])
        if not price_list:
            return None

        # Parse the price from the response
        price_data = json.loads(price_list[0])
        terms = price_data.get("terms", {}).get("OnDemand", {})

        if not terms:
            return None

        # Get the first term and its price dimension
        for term in terms.values():
            price_dimensions = term.get("priceDimensions", {})
            for dimension in price_dimensions.values():
                price_per_unit = dimension.get("pricePerUnit", {}).get("USD")
                if price_per_unit:
                    return float(price_per_unit)

        return None

    except ClientError as e:
        # Don't raise an exception for pricing errors - just return None
        # Pricing failures shouldn't block the main functionality
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.debug(f"Pricing API error for {instance_type} in {region}: {error_code}")
        return None
    except NoCredentialsError:
        logger.debug(f"No credentials for pricing lookup of {instance_type}")
        return None
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
        logger.debug(f"Could not parse pricing data for {instance_type}: {e}")
        return None


def get_instance_price_with_fallback(
    instance_type: str, region: str | None = None
) -> tuple[float | None, bool]:
    """Get the hourly on-demand price with region fallback.

    If the requested region is not in our region-to-location mapping,
    falls back to us-east-1 pricing as an estimate.

    Args:
        instance_type: The EC2 instance type (e.g., 't3.micro', 'm5.large')
        region: AWS region code. If None, uses the current session region.

    Returns:
        Tuple of (price, used_fallback) where:
        - price: The hourly price in USD, or None if pricing is unavailable
        - used_fallback: True if us-east-1 pricing was used as a fallback
    """
    if region is None:
        region = get_current_region()

    # Check if region has a valid location mapping (static or dynamic)
    location = get_region_location(region)
    if not location:
        # Fall back to us-east-1 pricing
        price = get_instance_price(instance_type, "us-east-1")
        return (price, True)

    price = get_instance_price(instance_type, region)
    return (price, False)


def format_price(price: float | None, prefix: str = "$") -> str:
    """Format a price for display.

    Args:
        price: The price to format
        prefix: Currency prefix (default: "$")

    Returns:
        Formatted price string, or "-" if price is None
    """
    if price is None:
        return "-"
    if price < 0.01:
        return f"{prefix}{price:.4f}"
    return f"{prefix}{price:.2f}"


def clear_price_cache() -> None:
    """Clear the pricing cache.

    Useful for testing or when you want to refresh pricing data.
    Also clears the region location cache.
    """
    get_instance_price.cache_clear()
    clear_region_location_cache()
