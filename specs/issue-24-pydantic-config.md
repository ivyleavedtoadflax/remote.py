# Issue 24: Pydantic Config Validation

**Status:** Not started
**Priority:** Low (v0.5.0)
**GitHub Issue:** #51 (partial)

## Problem

Current configuration uses raw `configparser` with no validation. Invalid config values are only caught at runtime when used.

## Current State

```python
# remotepy/config.py
cfg = configparser.ConfigParser()
cfg.read(config_path)
instance_name = cfg.get("DEFAULT", "instance_name", fallback=None)
```

## Proposed Solution

Use Pydantic for config validation with clear error messages.

```python
from pydantic import BaseModel, Field, validator
from pathlib import Path

class RemoteConfig(BaseModel):
    instance_name: str | None = Field(None, description="Default instance name")
    ssh_key_path: Path | None = Field(None, description="Path to SSH private key")
    ssh_user: str = Field("ubuntu", description="SSH username")
    aws_region: str | None = Field(None, description="AWS region override")

    @validator('ssh_key_path')
    def validate_key_exists(cls, v):
        if v and not v.exists():
            raise ValueError(f"SSH key not found: {v}")
        return v

    @validator('instance_name')
    def validate_instance_name(cls, v):
        if v and not v.replace('-', '').replace('_', '').isalnum():
            raise ValueError(f"Invalid instance name: {v}")
        return v

    class Config:
        extra = "forbid"  # Reject unknown config keys
```

## Config File Format

Support both INI and TOML formats:

```ini
# ~/.config/remote.py/config.ini
[DEFAULT]
instance_name = my-dev-server
ssh_key_path = ~/.ssh/my-key.pem
ssh_user = ubuntu
```

```toml
# ~/.config/remote.py/config.toml
instance_name = "my-dev-server"
ssh_key_path = "~/.ssh/my-key.pem"
ssh_user = "ubuntu"
```

## Environment Variable Overrides

```python
class RemoteConfig(BaseModel):
    instance_name: str | None = Field(None, env="REMOTE_INSTANCE_NAME")
    ssh_key_path: Path | None = Field(None, env="REMOTE_SSH_KEY")
    aws_region: str | None = Field(None, env="AWS_DEFAULT_REGION")

    class Config:
        env_prefix = "REMOTE_"
```

## Acceptance Criteria

- [ ] Add pydantic dependency
- [ ] Create RemoteConfig model with validation
- [ ] Support environment variable overrides
- [ ] Provide clear error messages for invalid config
- [ ] Maintain backwards compatibility with existing config files
- [ ] Add config validation on startup
- [ ] Add `remote config validate` command
- [ ] Update tests for new config system
