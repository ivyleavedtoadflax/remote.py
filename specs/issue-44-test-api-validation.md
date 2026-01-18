# Issue 44: Validate Tests Against Real API Formats

**Status:** COMPLETED
**Priority:** Medium
**Target Version:** v1.2.0
**Files:** `tests/`

## Problem

Mocked tests can pass while real API calls fail. This was demonstrated in issue 41 where:

- Tests mocked the AWS Pricing API with `"Europe (Ireland)"` as the location
- The mock returned valid pricing data
- Tests passed
- Real API calls failed because AWS expects `"EU (Ireland)"`

The mocks didn't validate that the input parameters matched what AWS actually accepts.

## Root Cause

When mocking external APIs, we only validate that:
1. The mock is called
2. The response is processed correctly

We don't validate that:
1. The request parameters would be accepted by the real API
2. The mocked response format matches the real API response

## Solution

Add validation layers to ensure tests catch API contract mismatches:

### 1. Capture Real API Responses as Fixtures

Record actual AWS API responses and use them as test fixtures:

```python
# tests/fixtures/pricing_api_responses.py
REAL_EU_IRELAND_PRICING_RESPONSE = {
    # Captured from actual AWS Pricing API call
    "PriceList": [...]
}
```

### 2. Validate Request Parameters Against Known-Good Values

```python
def test_pricing_uses_correct_location_name(mocker):
    """Ensure we use location names that AWS actually accepts."""
    # Known-good location names from AWS API
    VALID_LOCATIONS = ["EU (Ireland)", "EU (London)", "US East (N. Virginia)", ...]

    mock_client = mocker.patch(...)
    get_instance_price("t3.micro", "eu-west-1")

    call_args = mock_client.get_products.call_args
    location = next(f["Value"] for f in call_args.kwargs["Filters"] if f["Field"] == "location")

    assert location in VALID_LOCATIONS, f"Location '{location}' not in known-good AWS locations"
```

### 3. Add Contract Tests

Tests that validate our assumptions about external APIs:

```python
@pytest.mark.integration
def test_aws_pricing_api_accepts_our_location_names():
    """Validate our location names against real AWS API."""
    for region, location in REGION_TO_LOCATION.items():
        # This test actually calls AWS (run sparingly)
        response = pricing_client.get_attribute_values(
            ServiceCode="AmazonEC2",
            AttributeName="location",
        )
        valid_locations = [v["Value"] for v in response["AttributeValues"]]
        assert location in valid_locations, f"{location} not accepted by AWS"
```

### 4. Document API Contracts

Add comments documenting where API formats come from:

```python
# AWS Pricing API location names (verified 2026-01-18)
# See: https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/price-list-query-api.html
REGION_TO_LOCATION = {
    "eu-west-1": "EU (Ireland)",  # NOT "Europe (Ireland)"
    ...
}
```

## Acceptance Criteria

- [x] Add known-good AWS location names as test constants
- [x] Add validation that request parameters use known-good values
- [x] Add optional integration test that validates against real AWS API
- [x] Document where API format assumptions come from
- [x] Review other AWS API interactions for similar issues

## Areas to Review

- Pricing API location names (fixed in issue 41)
- EC2 API filter parameters
- ECS API parameters
- Any other boto3 client calls with string parameters

## Testing Strategy

1. **Unit tests**: Validate against known-good constants
2. **Integration tests** (optional, marked): Validate against real AWS APIs
3. **CI pipeline**: Run integration tests periodically (not on every PR)

## Implementation Summary

### Files Created
- `tests/fixtures/__init__.py` - Package init for fixtures
- `tests/fixtures/aws_api_contracts.py` - Known-good AWS API values and validation functions
- `tests/test_api_contracts.py` - Contract validation tests

### Files Modified
- `remote/pricing.py` - Added documentation about API contract validation
- `pyproject.toml` - Added `integration` marker for optional integration tests

### Test Coverage
- 18 passing tests validate:
  - REGION_TO_LOCATION uses valid AWS Pricing API location names
  - Pricing API requests use valid parameter values (operatingSystem, tenancy, etc.)
  - Mock EC2 instance states match valid AWS states
  - Mock EBS volume/snapshot/AMI states are valid
  - Test fixtures produce valid API response structures

### Integration Test
- `TestRealAwsApiContracts::test_pricing_api_accepts_our_location_names` can validate
  against the real AWS API (skipped by default, run with `pytest -m integration`)
