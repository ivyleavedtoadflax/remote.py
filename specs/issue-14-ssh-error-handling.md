# Issue 14: SSH Subprocess Error Handling

**Status:** COMPLETED
**Priority:** High
**File:** `remotepy/instance.py:309`

## Problem

The `subprocess.run()` call for SSH has no error handling. If SSH fails (connection refused, host unreachable, timeout), the error is not caught or reported properly.

```python
subprocess.run(ssh_command)  # No error handling
```

## Solution

Add error handling around the subprocess call:

```python
try:
    result = subprocess.run(ssh_command)
    if result.returncode != 0:
        typer.secho(f"SSH connection failed with exit code {result.returncode}", fg=typer.colors.RED)
        raise typer.Exit(result.returncode)
except FileNotFoundError:
    typer.secho("SSH client not found. Please install OpenSSH.", fg=typer.colors.RED)
    raise typer.Exit(1)
except Exception as e:
    typer.secho(f"SSH connection error: {e}", fg=typer.colors.RED)
    raise typer.Exit(1)
```

## Acceptance Criteria

- [x] Catch subprocess errors and provide helpful message
- [x] Exit with appropriate code on SSH failure
- [x] Handle missing SSH client gracefully
- [x] Add test for SSH failure scenarios
