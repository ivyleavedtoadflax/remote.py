# Issue 22: Add Instance Pricing

**Status:** COMPLETED
**Priority:** Low (v0.5.0)
**GitHub Issue:** #32

## Problem

Users cannot see the cost of running instances when listing them. This makes it difficult to identify expensive resources.

## Solution

Integrate AWS Pricing API to show hourly/monthly costs in `remote list` output.

## Implementation Approach

### Option A: AWS Price List API (Recommended)

```python
import boto3

pricing_client = boto3.client('pricing', region_name='us-east-1')

def get_instance_price(instance_type: str, region: str) -> float:
    """Get hourly price for an instance type."""
    response = pricing_client.get_products(
        ServiceCode='AmazonEC2',
        Filters=[
            {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
            {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': region_name},
            {'Type': 'TERM_MATCH', 'Field': 'operatingSystem', 'Value': 'Linux'},
            {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'Shared'},
            {'Type': 'TERM_MATCH', 'Field': 'preInstalledSw', 'Value': 'NA'},
        ]
    )
    # Parse pricing from response...
```

### Option B: Static Price Table

Maintain a local JSON file with common instance prices, updated periodically.

## Table Output Enhancement

```
Name          InstanceId           Status   Type      $/hr    $/month
────────────────────────────────────────────────────────────────────────
web-server    i-0123456789abcdef0  running  t3.micro  $0.0104  $7.49
db-server     i-0123456789abcdef1  running  r5.large  $0.126   $90.72
```

## Considerations

- Pricing API only available in us-east-1
- Cache prices to avoid repeated API calls
- Handle spot instances differently
- Consider showing monthly estimate based on uptime

## Acceptance Criteria

- [x] Add pricing column to `remote list` output
- [x] Cache pricing data to reduce API calls
- [x] Handle missing/unavailable pricing gracefully
- [x] Add `--no-pricing` flag to skip pricing lookup
- [x] Add tests with mocked pricing responses
