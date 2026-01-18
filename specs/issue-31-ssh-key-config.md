# Issue 31: SSH Key Config Not Used by Connect Command

**Status:** Not started
**Priority:** Medium
**File:** `remotepy/instance.py`

## Problem

The `remote connect` command does not read the SSH key path from the config file. Users must always pass `--key` explicitly even if they have configured a default SSH key in their config.

The config system supports storing a default SSH key path, but the connect command doesn't check for it before requiring the `--key` option.

## Expected Behavior

```bash
# Set default SSH key in config
remote config set ssh_key ~/.ssh/my-key.pem

# Connect should use the configured key automatically
remote connect my-instance  # Should use ~/.ssh/my-key.pem
```

## Current Behavior

```bash
# Even with ssh_key configured, --key must be passed
remote connect my-instance --key ~/.ssh/my-key.pem
```

## Solution

Update the `connect` command to check for a configured SSH key if `--key` is not provided:

```python
@app.command()
def connect(
    instance_name: str | None = typer.Argument(None, help="Instance name"),
    ...
    key: str | None = typer.Option(None, "--key", "-k", help="Path to SSH private key file."),
    ...
) -> None:
    ...
    # Check for default key from config if not provided
    if not key:
        key = config_manager.get_value("ssh_key")

    # If SSH key is specified (from option or config), add the -i option
    if key:
        arguments.extend(["-i", key])
```

## Acceptance Criteria

- [ ] Check config for `ssh_key` value when `--key` is not provided
- [ ] Use configured SSH key path in SSH command
- [ ] Add test for connect using config SSH key
- [ ] Update help text to mention config fallback
