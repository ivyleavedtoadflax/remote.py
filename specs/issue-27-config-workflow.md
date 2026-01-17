# Issue 27: Improve Config Workflow

**Status:** Not started
**Priority:** Medium
**Files:** `remotepy/config.py`, `remotepy/settings.py`

## Current Problems

### 1. Limited to instance_name Only
The `add` command only sets `instance_name`. There's no general way to set other config values.

```bash
# Can only do this:
$ remote config add my-instance

# Can't do this:
$ remote config set ssh_user ubuntu
$ remote config set ssh_key_path ~/.ssh/my-key.pem
```

### 2. Confusing Command Names
- `add` sounds like adding a new config file or section, not setting a value
- No `set`, `get`, `unset` commands which are standard for config management

### 3. No Single Value Access
Must use `show` to see all config; can't query a single value.

```bash
# Current: must parse table output
$ remote config show
┌─────────┬───────────────┬─────────────┐
│ Section │ Name          │ Value       │
├─────────┼───────────────┼─────────────┤
│ DEFAULT │ instance_name │ my-instance │
└─────────┴───────────────┴─────────────┘

# Desired: get single value (useful for scripts)
$ remote config get instance_name
my-instance
```

### 4. No Unset/Remove Capability
Can't remove a config value once set.

### 5. No First-Time Setup Wizard
New users must know about config manually. No guided setup.

### 6. Single Section Only
Hardcoded to DEFAULT section. Can't have named profiles like AWS CLI.

```ini
# AWS CLI allows this:
[default]
region = us-east-1

[profile dev]
region = eu-west-1
```

### 7. Limited Config Options
Only `instance_name` is supported. Missing:
- `ssh_user` - SSH username (defaults to ubuntu)
- `ssh_key_path` - Path to SSH key
- `aws_region` - AWS region override
- `default_launch_template` - Default template for launching (issue-26)

### 8. No Config Validation
Setting an invalid instance name doesn't warn the user.

## Proposed Improvements

### 1. Generic Set/Get/Unset Commands

```python
@app.command()
def set(
    key: str = typer.Argument(..., help="Config key to set"),
    value: str = typer.Argument(..., help="Value to set"),
    config_path: str = typer.Option(CONFIG_PATH, "--config", "-c"),
) -> None:
    """Set a configuration value."""
    valid_keys = ["instance_name", "ssh_user", "ssh_key_path", "aws_region", "default_launch_template"]
    if key not in valid_keys:
        typer.secho(f"Unknown config key: {key}", fg="red")
        typer.secho(f"Valid keys: {', '.join(valid_keys)}", fg="yellow")
        raise typer.Exit(1)

    config_manager.set_value(key, value, config_path)
    typer.secho(f"Set {key} = {value}", fg="green")


@app.command()
def get(
    key: str = typer.Argument(..., help="Config key to get"),
    config_path: str = typer.Option(CONFIG_PATH, "--config", "-c"),
) -> None:
    """Get a configuration value."""
    value = config_manager.get_value(key)
    if value is None:
        raise typer.Exit(1)
    typer.echo(value)  # Just the value, for scripting


@app.command()
def unset(
    key: str = typer.Argument(..., help="Config key to remove"),
    config_path: str = typer.Option(CONFIG_PATH, "--config", "-c"),
) -> None:
    """Remove a configuration value."""
    config_manager.remove_value(key, config_path)
    typer.secho(f"Removed {key}", fg="green")
```

### 2. Keep `add` as Alias for Interactive Instance Selection

Rename internal behavior but keep `add` working for backwards compatibility:

```python
@app.command("add")
@app.command("select-instance", hidden=True)  # New name
def add_instance(
    instance_name: str | None = typer.Argument(None),
    config_path: str = typer.Option(CONFIG_PATH, "--config", "-c"),
) -> None:
    """Interactively select a default instance."""
    # Existing implementation
```

### 3. Init Command for First-Time Setup

```python
@app.command()
def init(
    config_path: str = typer.Option(CONFIG_PATH, "--config", "-c"),
) -> None:
    """Initialize configuration with guided setup."""
    typer.secho("Remote.py Configuration Setup", fg="blue", bold=True)
    typer.echo()

    # Check if config exists
    if os.path.exists(config_path):
        if not typer.confirm("Config already exists. Overwrite?"):
            raise typer.Exit(0)

    # Guided prompts
    instance_name = typer.prompt("Default instance name (optional)", default="", show_default=False)
    ssh_user = typer.prompt("SSH username", default="ubuntu")
    ssh_key = typer.prompt("SSH key path (optional)", default="", show_default=False)

    # Write config
    config = configparser.ConfigParser()
    if instance_name:
        config.set("DEFAULT", "instance_name", instance_name)
    config.set("DEFAULT", "ssh_user", ssh_user)
    if ssh_key:
        config.set("DEFAULT", "ssh_key_path", ssh_key)

    write_config(config, config_path)
    typer.secho(f"\nConfig written to {config_path}", fg="green")
```

### 4. Profile Support (Future)

```bash
# Create a profile
$ remote config set instance_name dev-server --profile dev
$ remote config set instance_name prod-server --profile prod

# Use a profile
$ remote start --profile dev
$ remote connect --profile prod

# List profiles
$ remote config profiles
default
dev
prod
```

### 5. Config Validation Command

```python
@app.command()
def validate(
    config_path: str = typer.Option(CONFIG_PATH, "--config", "-c"),
) -> None:
    """Validate configuration file."""
    errors = []
    warnings = []

    cfg = read_config(config_path)

    # Check instance_name exists in AWS
    instance_name = cfg.get("DEFAULT", "instance_name", fallback=None)
    if instance_name:
        try:
            instance = get_instance_by_name(instance_name)
            if not instance:
                warnings.append(f"Instance '{instance_name}' not found in AWS")
        except Exception as e:
            warnings.append(f"Could not verify instance: {e}")

    # Check SSH key exists
    ssh_key = cfg.get("DEFAULT", "ssh_key_path", fallback=None)
    if ssh_key and not os.path.exists(os.path.expanduser(ssh_key)):
        errors.append(f"SSH key not found: {ssh_key}")

    # Report results
    if errors:
        for error in errors:
            typer.secho(f"ERROR: {error}", fg="red")
        raise typer.Exit(1)
    elif warnings:
        for warning in warnings:
            typer.secho(f"WARNING: {warning}", fg="yellow")
    else:
        typer.secho("Config is valid", fg="green")
```

### 6. List Valid Keys

```python
@app.command("keys")
def list_keys() -> None:
    """List all valid configuration keys."""
    keys = {
        "instance_name": "Default EC2 instance name",
        "ssh_user": "SSH username (default: ubuntu)",
        "ssh_key_path": "Path to SSH private key",
        "aws_region": "AWS region override",
        "default_launch_template": "Default launch template name",
    }

    for key, description in keys.items():
        typer.echo(f"  {key:<25} {description}")
```

## New Commands Summary

| Command | Description |
|---------|-------------|
| `remote config set <key> <value>` | Set a config value |
| `remote config get <key>` | Get a config value (script-friendly) |
| `remote config unset <key>` | Remove a config value |
| `remote config init` | Guided first-time setup |
| `remote config validate` | Validate config file |
| `remote config keys` | List valid config keys |
| `remote config show` | Show all config (existing) |
| `remote config add [name]` | Interactive instance selection (existing) |

## Example Workflow

### New User Setup
```bash
$ remote config init
Remote.py Configuration Setup

Default instance name (optional): my-dev-server
SSH username [ubuntu]:
SSH key path (optional): ~/.ssh/aws-key.pem

Config written to ~/.config/remote.py/config.ini
```

### Setting Individual Values
```bash
$ remote config set ssh_user ec2-user
Set ssh_user = ec2-user

$ remote config get ssh_user
ec2-user
```

### Scripting
```bash
# Get value for use in scripts
INSTANCE=$(remote config get instance_name)
echo "Default instance: $INSTANCE"
```

## Acceptance Criteria

- [ ] Add `remote config set <key> <value>` command
- [ ] Add `remote config get <key>` command (returns just value, no formatting)
- [ ] Add `remote config unset <key>` command
- [ ] Add `remote config init` guided setup wizard
- [ ] Add `remote config validate` command
- [ ] Add `remote config keys` command to list valid keys
- [ ] Update ConfigManager to support additional keys
- [ ] Keep `add` command working for backwards compatibility
- [ ] Add validation for known config keys
- [ ] Add tests for new commands
