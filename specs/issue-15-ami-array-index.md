# Issue 15: Unvalidated Array Index in AMI Launch

**Status:** COMPLETED
**Priority:** High
**File:** `remotepy/ami.py:186`

## Problem

Direct array indexing without bounds checking could cause IndexError if the list is empty.

```python
instance_ids[0]  # Potential IndexError
```

## Solution

Use `safe_get_array_item()` from validation module or check list length first:

```python
from remotepy.validation import safe_get_array_item

instance_id = safe_get_array_item(instance_ids, 0, "launched instances")
```

Or:

```python
if not instance_ids:
    typer.secho("Error: No instances were launched", fg=typer.colors.RED)
    raise typer.Exit(1)
instance_id = instance_ids[0]
```

## Acceptance Criteria

- [x] Add bounds checking before array access
- [x] Provide helpful error if no instances returned
- [x] Add test for empty instance list scenario
