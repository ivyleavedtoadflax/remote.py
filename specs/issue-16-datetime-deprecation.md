# Issue 16: Deprecated datetime.utcfromtimestamp() Usage

**Status:** COMPLETED
**Priority:** Medium
**File:** `remotepy/utils.py:353`

## Problem

`datetime.utcfromtimestamp()` is deprecated in Python 3.12+ and will be removed in a future version.

## Solution

Replace with timezone-aware alternative:

```python
# Before
from datetime import datetime
launch_time = datetime.utcfromtimestamp(timestamp)

# After
from datetime import datetime, timezone
launch_time = datetime.fromtimestamp(timestamp, tz=timezone.utc)
```

## Acceptance Criteria

- [x] Replace deprecated datetime call
- [x] Ensure tests pass with Python 3.12+
- [x] Verify no deprecation warnings in test output
