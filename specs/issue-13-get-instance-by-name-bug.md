# Issue 13: Logic Bug in get_instance_by_name()

**Status:** Not started
**Priority:** High
**File:** `remotepy/utils.py:333`

## Problem

When iterating through reservations to find an instance by name, if the first instance is terminated, the loop breaks entirely instead of continuing to check other instances.

```python
if instance_state == "terminated":
    break  # BUG: Should be 'continue' to check other instances
```

## Solution

Change `break` to `continue` so the loop continues checking remaining instances.

## Acceptance Criteria

- [ ] Change `break` to `continue` on line 333
- [ ] Add test case verifying terminated instances don't block finding valid instances
