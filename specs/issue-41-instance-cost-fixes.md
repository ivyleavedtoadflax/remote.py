# Issue 41: Fix Instance Cost Integration

**Status:** COMPLETED
**Priority:** Medium
**Target Version:** v1.2.0
**Files:** `remotepy/instance.py`

## Problem

The `instance cost` command has several issues:

1. **Cost not displaying**: Hourly rate and estimated cost show "-" instead of actual values
2. **Panel too wide**: Output panel stretches beyond reasonable console width
3. **Unnecessary separate command**: Cost information should be integrated into `instance ls` rather than requiring a separate command

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
- [x] Add `--cost` flag to `instance ls` to optionally show cost (may slow down due to pricing API)
- [x] Deprecate or remove `instance cost` command
- [x] Add tests for cost display in `instance ls`

## Testing Requirements

**Important**: Add comprehensive Typer CLI tests to verify cost functionality end-to-end. Previous testing gaps have allowed cost display issues to slip through.

- [x] Add Typer `CliRunner` tests for `instance ls --cost` flag
- [x] Test that cost values appear in output (not "-")
- [x] Test cost formatting (currency symbol, decimal places)
- [x] Test behavior when pricing API is unavailable (graceful fallback)
- [x] Test cost calculation accuracy (uptime * hourly rate)
- [x] Add integration test that mocks boto3 and pricing API together
