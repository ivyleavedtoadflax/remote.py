# Progress Log

## 2026-01-18: Remove unused `cfg` parameter from `get_instance_name()`

**File:** `remote/utils.py`

**Issue:** The `get_instance_name()` function had an unused parameter `cfg: ConfigParser | None = None`. The docstring mentioned it was for "backward compatibility" but:
1. The parameter was never used inside the function
2. All callers (8 call sites across instance.py, ami.py, snapshot.py, volume.py) called the function without arguments

**Changes:**
- Removed the unused `cfg` parameter from the function signature
- Removed the corresponding parameter documentation from the docstring
- Removed the now-unused `from configparser import ConfigParser` import
