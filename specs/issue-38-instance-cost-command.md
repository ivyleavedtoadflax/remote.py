# Issue 38: Instance Cost Command

**Status:** COMPLETED
**Priority:** Low (post v1.0.0)
**Related:** Issue 22 (Instance Pricing), Issue 37 (Pricing Region Fallback)

## Problem

Users want to see the estimated cost of running an instance based on its uptime. While `remote instance ls` shows hourly/monthly pricing, users need a command to see the actual cost incurred for a specific instance based on how long it has been running.

## Solution

Add a new `remote instance cost` command that:
1. Gets the instance's launch time (for running instances)
2. Calculates the uptime in hours
3. Uses the pricing API to get the hourly rate
4. Calculates and displays the estimated cost

## Implementation

### New Command: `cost`

```python
@app.command()
def cost(
    instance_name: str | None = typer.Argument(None, help="Instance name"),
) -> None:
    """
    Show estimated cost of a running instance based on uptime.

    Calculates cost from launch time to now using the instance's hourly rate.
    Uses the default instance from config if no name is provided.

    Examples:
        remote instance cost                    # Show cost of default instance
        remote instance cost my-server          # Show cost of specific instance
    """
```

### Output Format

Use a Rich Panel similar to other commands:

```
┌─ Instance Cost: my-server ──────────────────────┐
│ Instance ID:   i-0123456789abcdef0              │
│ Instance Type: t3.micro                         │
│ Status:        running                          │
│ Launch Time:   2024-01-15 10:30:00 UTC          │
│ Uptime:        2h 45m                           │
│ Hourly Rate:   $0.0104                          │
│ Estimated Cost: $0.03                           │
└─────────────────────────────────────────────────┘
```

### Edge Cases

1. Instance not running: Show message that cost calculation requires running instance
2. Pricing unavailable: Show uptime but indicate pricing is unavailable
3. Region fallback: Use us-east-1 pricing for unsupported regions (via existing fallback)

## Acceptance Criteria

- [x] Add `cost` command to instance module
- [x] Display uptime in human-readable format
- [x] Calculate estimated cost from hourly rate and uptime
- [x] Handle non-running instances gracefully
- [x] Handle pricing API failures gracefully
- [x] Add tests with mocked AWS responses
