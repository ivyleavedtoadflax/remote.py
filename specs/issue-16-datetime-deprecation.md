# Issue 16: Deprecated datetime.utcfromtimestamp() Usage

**Status:** Not started
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

- [ ] Replace deprecated datetime call
- [ ] Ensure tests pass with Python 3.12+
- [ ] Verify no deprecation warnings in test output
