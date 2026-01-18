"""AWS API contract validation fixtures.

This module provides known-good values for AWS API parameters and response formats,
ensuring that mocked tests use values that would be accepted by the real AWS APIs.

Validated: 2026-01-18
See: https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/price-list-query-api.html
See: https://docs.aws.amazon.com/AWSEC2/latest/APIReference/
"""

# ============================================================================
# AWS Pricing API Location Names
# ============================================================================
#
# The AWS Pricing API uses human-readable location names, NOT region codes.
# These names must match exactly what AWS accepts.
#
# Common mistakes:
#   - "Europe (Ireland)" - WRONG
#   - "EU (Ireland)" - CORRECT
#
#   - "US-East-1" - WRONG
#   - "US East (N. Virginia)" - CORRECT

# Known-good AWS Pricing API location names (verified against real API)
VALID_AWS_PRICING_LOCATIONS: frozenset[str] = frozenset(
    [
        # US regions
        "US East (N. Virginia)",
        "US East (Ohio)",
        "US West (N. California)",
        "US West (Oregon)",
        # EU regions
        "EU (Ireland)",
        "EU (London)",
        "EU (Frankfurt)",
        "EU (Paris)",
        "EU (Stockholm)",
        "EU (Milan)",
        # Asia Pacific regions
        "Asia Pacific (Tokyo)",
        "Asia Pacific (Seoul)",
        "Asia Pacific (Osaka)",
        "Asia Pacific (Singapore)",
        "Asia Pacific (Sydney)",
        "Asia Pacific (Mumbai)",
        # Other regions
        "South America (Sao Paulo)",
        "Canada (Central)",
        # Note: This list may need to be updated as AWS adds new regions
    ]
)

# Mapping of AWS region codes to Pricing API location names
# This should match remote/pricing.py REGION_TO_LOCATION
REGION_TO_LOCATION_EXPECTED: dict[str, str] = {
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


# ============================================================================
# AWS Pricing API Filter Fields
# ============================================================================

# Valid filter fields for EC2 Pricing API get_products
VALID_EC2_PRICING_FILTER_FIELDS: frozenset[str] = frozenset(
    [
        "instanceType",
        "location",
        "operatingSystem",
        "tenancy",
        "preInstalledSw",
        "capacitystatus",
        "licenseModel",
        "marketoption",
        "usagetype",
    ]
)

# Valid operating system values
VALID_OPERATING_SYSTEMS: frozenset[str] = frozenset(
    [
        "Linux",
        "RHEL",
        "SUSE",
        "Windows",
    ]
)

# Valid tenancy values
VALID_TENANCIES: frozenset[str] = frozenset(
    [
        "Shared",
        "Dedicated",
        "Host",
    ]
)

# Valid preInstalledSw values
VALID_PRE_INSTALLED_SW: frozenset[str] = frozenset(
    [
        "NA",
        "SQL Ent",
        "SQL Std",
        "SQL Web",
    ]
)

# Valid capacitystatus values
VALID_CAPACITY_STATUS: frozenset[str] = frozenset(
    [
        "Used",
        "UnusedCapacityReservation",
        "AllocatedCapacityReservation",
    ]
)


# ============================================================================
# EC2 API Response Structures
# ============================================================================

# Valid EC2 instance states
VALID_EC2_INSTANCE_STATES: frozenset[str] = frozenset(
    [
        "pending",
        "running",
        "shutting-down",
        "terminated",
        "stopping",
        "stopped",
    ]
)

# EC2 instance state codes (mapping of state to numeric code)
EC2_INSTANCE_STATE_CODES: dict[str, int] = {
    "pending": 0,
    "running": 16,
    "shutting-down": 32,
    "terminated": 48,
    "stopping": 64,
    "stopped": 80,
}

# Valid EBS volume states
VALID_EBS_VOLUME_STATES: frozenset[str] = frozenset(
    [
        "creating",
        "available",
        "in-use",
        "deleting",
        "deleted",
        "error",
    ]
)

# Valid EBS snapshot states
VALID_EBS_SNAPSHOT_STATES: frozenset[str] = frozenset(
    [
        "pending",
        "completed",
        "error",
        "recoverable",
        "recovering",
    ]
)

# Valid AMI states
VALID_AMI_STATES: frozenset[str] = frozenset(
    [
        "pending",
        "available",
        "invalid",
        "deregistered",
        "transient",
        "failed",
        "error",
    ]
)


# ============================================================================
# EC2 Instance Type Validation
# ============================================================================

# Common instance type prefixes (not exhaustive)
VALID_INSTANCE_TYPE_PREFIXES: frozenset[str] = frozenset(
    [
        "t2",
        "t3",
        "t3a",
        "t4g",
        "m5",
        "m5a",
        "m5n",
        "m5zn",
        "m6i",
        "m6a",
        "m6g",
        "m7i",
        "m7g",
        "c5",
        "c5a",
        "c5n",
        "c6i",
        "c6a",
        "c6g",
        "c7i",
        "c7g",
        "r5",
        "r5a",
        "r5n",
        "r6i",
        "r6a",
        "r6g",
        "r7i",
        "r7g",
        "p3",
        "p4d",
        "p5",
        "g4dn",
        "g5",
        "i3",
        "i3en",
        "i4i",
        "d2",
        "d3",
        "d3en",
        "x1",
        "x1e",
        "x2idn",
        "x2iedn",
    ]
)


# ============================================================================
# ECS API Response Structures
# ============================================================================

# Valid ECS service status values
VALID_ECS_SERVICE_STATUSES: frozenset[str] = frozenset(
    [
        "ACTIVE",
        "DRAINING",
        "INACTIVE",
    ]
)


# ============================================================================
# Validation Functions
# ============================================================================


def validate_pricing_location(location: str) -> bool:
    """Validate that a location name is accepted by the AWS Pricing API.

    Args:
        location: The location name to validate

    Returns:
        True if the location is valid, False otherwise
    """
    return location in VALID_AWS_PRICING_LOCATIONS


def validate_ec2_instance_state(state: str) -> bool:
    """Validate that an instance state is a valid EC2 state.

    Args:
        state: The state name to validate

    Returns:
        True if the state is valid, False otherwise
    """
    return state in VALID_EC2_INSTANCE_STATES


def validate_region_to_location_mapping(mapping: dict[str, str]) -> list[str]:
    """Validate that all locations in a region-to-location mapping are valid.

    Args:
        mapping: Dictionary mapping region codes to location names

    Returns:
        List of invalid location names (empty if all valid)
    """
    invalid = []
    for region, location in mapping.items():
        if location not in VALID_AWS_PRICING_LOCATIONS:
            invalid.append(f"{region} -> {location}")
    return invalid
