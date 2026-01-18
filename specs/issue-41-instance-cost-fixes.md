# Issue 41: Fix Instance Cost Integration

**Status:** TODO
**Priority:** Medium
**Target Version:** v1.2.0
**Files:** `remotepy/instance.py`

## Problem

The `instance cost` command has several issues:

1. **Cost not displaying**: Hourly rate and estimated cost show "-" instead of actual values
2. **Panel too wide**: Output panel stretches beyond reasonable console width
3. **Unnecessary separate command**: Cost information should be integrated into `instance ls` rather than requiring a separate command

## Previous Attempt (PR #26)

PR #26 attempted to fix this but cost still shows "-" in production:

```
│ remote-py-test │ i-0da650323b6167dbc │ ... │ running │ t3.large │ ... │ 3h │ - │ - │
```

**Investigation needed**: Why is pricing lookup failing in real usage but possibly passing in tests?

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

- [ ] Fix pricing lookup so cost actually displays (PR #26 did not fix this)
- [x] Add cost column to `instance ls` output
- [x] Add `--cost` / `-c` flag to `instance ls` to optionally show cost
- [x] Deprecate or remove `instance cost` command
- [ ] Verify cost displays with real AWS credentials (not just mocked tests)

## Testing Requirements

**Important**: Add comprehensive Typer CLI tests to verify cost functionality end-to-end. Previous testing gaps have allowed cost display issues to slip through.

- [x] Add Typer `CliRunner` tests for `instance ls --cost` flag
- [ ] Test that cost values appear in output (not "-") - **tests pass but real usage fails**
- [ ] Test cost formatting (currency symbol, decimal places)
- [x] Test behavior when pricing API is unavailable (graceful fallback)
- [ ] Test cost calculation accuracy (uptime * hourly rate)
- [ ] Add integration test that mocks boto3 and pricing API together - **mock may not match real API behavior**

## Next Steps

1. Debug why pricing lookup returns None/"-" in real usage
2. Check if pricing API client is configured correctly for eu-west-1 region
3. Verify issue 37 (pricing region fallback) is actually working
4. Add logging/debug output to trace pricing lookup flow
5. Consider if mocked tests are masking the real issue
