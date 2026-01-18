"""AWS EC2 instance pricing functionality.

This module provides functions to retrieve EC2 instance pricing information
using the AWS Pricing API.
"""

import json
from functools import lru_cache
from typing import Any

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

# AWS region to location name mapping for the Pricing API.
#
# IMPORTANT: The Pricing API uses human-readable location names, NOT region codes.
# These names must match EXACTLY what AWS accepts. Common mistakes:
#   - "Europe (Ireland)" - WRONG (AWS returns no results)
#   - "EU (Ireland)" - CORRECT
#
# Validated against AWS Pricing API: 2026-01-18
# To re-validate, run: pytest -m integration tests/test_api_contracts.py
# See: https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/price-list-query-api.html
#
# Test coverage for this mapping: tests/test_api_contracts.py::TestPricingApiContracts
REGION_TO_LOCATION: dict[str, str] = {
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

# Hours per month (for calculating monthly estimates)
HOURS_PER_MONTH = 730


@lru_cache(maxsize=1)
def get_pricing_client() -> Any:
    """Get or create the Pricing client.

    The Pricing API is only available in us-east-1 and ap-south-1.
    We use us-east-1 for consistency.

    Returns:
        boto3 Pricing client instance
    """
    return boto3.client("pricing", region_name="us-east-1")


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

    # Get location name for region
    location = REGION_TO_LOCATION.get(region)
    if not location:
        # Region not in our mapping, return None
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

    except ClientError:
        # Don't raise an exception for pricing errors - just return None
        # Pricing failures shouldn't block the main functionality
        return None
    except NoCredentialsError:
        return None
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
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

    # Check if region is in our mapping
    if region not in REGION_TO_LOCATION:
        # Fall back to us-east-1 pricing
        price = get_instance_price(instance_type, "us-east-1")
        return (price, True)

    price = get_instance_price(instance_type, region)
    return (price, False)


def get_monthly_estimate(hourly_price: float | None) -> float | None:
    """Calculate monthly cost estimate from hourly price.

    Args:
        hourly_price: The hourly price in USD

    Returns:
        The estimated monthly cost in USD, or None if hourly_price is None
    """
    if hourly_price is None:
        return None
    return hourly_price * HOURS_PER_MONTH


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
    """
    get_instance_price.cache_clear()
