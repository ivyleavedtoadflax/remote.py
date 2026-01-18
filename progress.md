# Progress Log

## 2026-01-18: Fix incorrect config key `ssh_key` → `ssh_key_path`

**File:** `remote/instance.py`

**Issue:** The `connect()` function was using the wrong config key name when retrieving the SSH key path from configuration:
- Line 415 used `config_manager.get_value("ssh_key")` (incorrect)
- The valid config key defined in `remote/config.py` is `"ssh_key_path"`

This caused the SSH key configuration to fail silently - users who set `ssh_key_path` in their config would not have the key applied when connecting via SSH.

**Changes:**
- Fixed line 415: Changed `"ssh_key"` to `"ssh_key_path"` in `get_value()` call
- Fixed line 329: Updated help text to reference `ssh_key_path` instead of `ssh_key`

---

## 2026-01-18: Remove unused `cfg` parameter from `get_instance_name()`

**File:** `remote/utils.py`

**Issue:** The `get_instance_name()` function had an unused parameter `cfg: ConfigParser | None = None`. The docstring mentioned it was for "backward compatibility" but:
1. The parameter was never used inside the function
2. All callers (8 call sites across instance.py, ami.py, snapshot.py, volume.py) called the function without arguments

**Changes:**
- Removed the unused `cfg` parameter from the function signature
- Removed the corresponding parameter documentation from the docstring
- Removed the now-unused `from configparser import ConfigParser` import
