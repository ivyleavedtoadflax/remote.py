# Issue 41: Fix Instance Cost Integration

**Status:** COMPLETED
**Priority:** Medium
**Target Version:** v1.2.0
**Files:** `remote/pricing.py`, `remote/instance.py`

## Problem

The `instance cost` command has several issues:

1. **Cost not displaying**: Hourly rate and estimated cost show "-" instead of actual values
2. **Panel too wide**: Output panel stretches beyond reasonable console width
3. **Unnecessary separate command**: Cost information should be integrated into `instance ls` rather than requiring a separate command

## Root Cause Found

The `REGION_TO_LOCATION` mapping in `pricing.py` used incorrect location names for EU regions. The AWS Pricing API uses `"EU (...)"` format, not `"Europe (...)"`.

Incorrect mappings:
- `eu-west-1`: "Europe (Ireland)" -> Should be "EU (Ireland)"
- `eu-west-2`: "Europe (London)" -> Should be "EU (London)"
- etc.

This caused the Pricing API to return empty results for all EU regions.

## Current Behavior

```
╭─────────────────────────────────────────────── Instance Cost: remote-py-test ───────────────────────────────────────────────╮
│ Instance ID:    i-0da650323b6167dbc                                                                                         │
│ Instance Type:  t3.large                                                                                                    │
│ Status:         running                                                                                                     │
│ Launch Time:    2026-01-18 10:29:21 UTC                                                                                     │
│ Uptime:         2h 45m                                                                                                      │
│ Hourly Rate:    -                                                                                                           │
│ Estimated Cost: -                                                                                                           │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## Solution

1. **Fix pricing lookup**: Investigate why cost is not being retrieved (likely related to issue 37 pricing API region fallback)
2. **Constrain panel width**: Limit panel to reasonable width (e.g., 80 chars or terminal width)
3. **Integrate into `instance ls`**: Add cost column to `instance ls` output and deprecate/remove the separate `instance cost` command

## Proposed Output

`instance ls` with integrated cost:

```
┏━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━┓
┃ Name           ┃ Instance ID         ┃ Type      ┃ Status     ┃ Uptime   ┃ Est. Cost   ┃
┡━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━┩
│ remote-py-test │ i-0da650323b6167dbc │ t3.large  │ running    │ 2h 45m   │ $0.23       │
└────────────────┴─────────────────────┴───────────┴────────────┴──────────┴─────────────┘
```

## Acceptance Criteria

- [x] Fix pricing lookup so cost actually displays
- [x] Add cost column to `instance ls` output
- [x] Add `--cost` / `-c` flag to `instance ls` to optionally show cost
- [x] Deprecate or remove `instance cost` command
- [x] Verify cost displays with real AWS credentials

## Fix Applied

Fixed `REGION_TO_LOCATION` mapping in `remote/pricing.py`:
- `eu-west-1`: "Europe (Ireland)" → "EU (Ireland)"
- `eu-west-2`: "Europe (London)" → "EU (London)"
- `eu-west-3`: "Europe (Paris)" → "EU (Paris)"
- `eu-central-1`: "Europe (Frankfurt)" → "EU (Frankfurt)"
- `eu-north-1`: "Europe (Stockholm)" → "EU (Stockholm)"
- Added `eu-south-1`: "EU (Milan)"

## Lesson Learned

The mocked tests were passing because they didn't validate the actual AWS Pricing API response format. The location names in the mock matched what the code expected, but didn't match what AWS actually returns. Future tests should consider validating against actual API response formats.
