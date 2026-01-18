# Issue 37: Pricing API Region Fallback

**Status:** COMPLETED
**Priority:** Low (Post-v1.0.0)
**GitHub Issue:** #37

## Problem

The AWS Pricing API is only available in us-east-1 and ap-south-1 regions. When users query pricing for instances in regions not in the `REGION_TO_LOCATION` mapping, the `get_instance_price()` function returns `None` silently, making pricing data unavailable for those regions.

Additionally, even though the Pricing API endpoint in us-east-1 can return pricing data for all regions, if a user's region is missing from the mapping, they see no pricing at all.

## Solution

Add fallback logic to the pricing module so that when pricing for a specific region is unavailable (region not in mapping), it falls back to us-east-1 pricing with a clear indication that it's an estimate.

## Implementation Approach

### Changes to `remote/pricing.py`

1. Add a new function `get_instance_price_with_fallback()` that:
   - First tries to get pricing for the requested region
   - If the region is not in `REGION_TO_LOCATION`, falls back to us-east-1
   - Returns a tuple of (price, used_fallback) to indicate if fallback was used

2. Update `get_instance_pricing_info()` to use the new function and include fallback indicator

### Example Implementation

```python
def get_instance_price_with_fallback(
    instance_type: str, region: str | None = None
) -> tuple[float | None, bool]:
    """Get the hourly price with region fallback.

    Args:
        instance_type: The EC2 instance type
        region: AWS region code. If None, uses current session region.

    Returns:
        Tuple of (price, used_fallback) where used_fallback is True
        if the price was retrieved using us-east-1 as fallback.
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
```

## Acceptance Criteria

- [x] Add `get_instance_price_with_fallback()` function
- [x] Update `get_instance_pricing_info()` to include `fallback_used` field
- [x] Add tests for regions not in mapping falling back to us-east-1
- [x] Add tests verifying fallback indicator is correctly set
- [x] Update instance list command to use fallback pricing
