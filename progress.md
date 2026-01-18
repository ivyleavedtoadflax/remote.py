# Progress Log

## 2026-01-18: Replace silent exception handler in `list_launch_templates()`

**File:** `remote/ami.py`

**Issue:** The `list_launch_templates()` function silently swallowed exceptions with a bare `pass`:
```python
except (ResourceNotFoundError, AWSServiceError):
    pass
```

This is problematic because:
1. Silently ignoring errors hides potential problems from users
2. Users have no indication when version details fail to load
3. Debugging becomes difficult when errors are silently discarded

**Changes:**
- Replaced silent `pass` with a warning message: `"Warning: Could not fetch version details"`
- The warning uses the same `[yellow]` styling pattern used elsewhere in the codebase (e.g., `utils.py:354`, `config.py:264`)

This maintains the non-fatal behavior (template listing continues) while informing users that some details couldn't be retrieved.

---

## 2026-01-18: Replace overly broad exception handling in `list_launch_templates()`

**File:** `remote/ami.py`

**Issue:** The `list_launch_templates()` function had overly broad exception handling at line 141:
```python
except (ResourceNotFoundError, Exception):
    pass
```

This is problematic because:
1. `Exception` is too broad and catches all exceptions, hiding unexpected errors
2. `ResourceNotFoundError` is a subclass of `Exception`, making it redundant in the tuple
3. Silently passing on all exceptions can mask bugs

The function `get_launch_template_versions()` (called within the try block) documents that it raises only:
- `ResourceNotFoundError`: If template not found
- `AWSServiceError`: If AWS API call fails

**Changes:**
- Added `AWSServiceError` to imports from `remote.exceptions`
- Changed exception handling from `(ResourceNotFoundError, Exception)` to `(ResourceNotFoundError, AWSServiceError)`

This makes the error handling explicit and specific to the documented exceptions.

---

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

---

## 2026-01-18: Remove unnecessary `builtins` import from `instance.py`

**File:** `remote/instance.py`

**Issue:** The file imported `builtins` and used `builtins.list[dict[str, str]]` for a type annotation on line 742. This is unnecessary because:
1. In Python 3.9+, `list` can be used directly in type annotations without importing from `builtins`
2. The `builtins` module was only used for this single type annotation
3. Using `list` directly is more idiomatic and readable

**Changes:**
- Removed the `import builtins` statement from line 1
- Changed `builtins.list[dict[str, str]]` to `list[dict[str, str]]` in the `tags` variable annotation

---

## 2026-01-18: Remove unused Typer app instance from `utils.py`

**File:** `remote/utils.py`

**Issue:** Line 33 defined `app = typer.Typer()` but this app instance was never used anywhere in the codebase:
1. No commands were registered to this app
2. No other modules imported this app
3. The `utils.py` module is a utility module, not a CLI entrypoint

The `typer` import itself is still needed for other uses in the file (typer.Exit, typer.secho, typer.colors).

**Changes:**
- Removed the unused `app = typer.Typer()` line

---

## 2026-01-18: Use cached STS client in `get_account_id()`

**File:** `remote/utils.py`

**Issue:** The `get_sts_client()` function (lines 46-55) was defined as a cached client factory but was never used. The `get_account_id()` function at line 86 created a new STS client directly with `boto3.client("sts")` instead of using the cached `get_sts_client()` function.

This was inconsistent with the pattern used for EC2 clients, where `get_ec2_client()` is consistently used throughout the codebase.

**Changes:**
- Changed line 86 from `boto3.client("sts").get_caller_identity()` to `get_sts_client().get_caller_identity()`
- This makes the code consistent with the EC2 client pattern and utilizes the caching provided by `@lru_cache`

---

## 2026-01-18: Remove unnecessary `enumerate()` in `get_instance_ids()`

**File:** `remote/utils.py`

**Issue:** The `get_instance_ids()` function at line 390 used `enumerate()` to iterate over instances:
```python
for _i, reservation in enumerate(instances):
```

The loop index `_i` was never used in the function body. The underscore prefix conventionally indicates an unused variable, but in this case the `enumerate()` call itself was unnecessary.

**Changes:**
- Changed from `for _i, reservation in enumerate(instances):` to `for reservation in instances:`
- Removes dead code and improves clarity by eliminating unused variable

---

## 2026-01-18: Remove unused `drop_nameless` parameter from `get_instance_info()`

**File:** `remote/utils.py`

**Issue:** The `get_instance_info()` function had an unused parameter `drop_nameless: bool = False`:
1. The parameter was defined in the function signature and documented in the docstring
2. However, the function body always skips instances without a Name tag (lines 336-338), regardless of the parameter value
3. No callers in the codebase ever passed this parameter

The parameter was misleading because:
- Default value `False` implied nameless instances would be included by default
- But the actual behavior always excluded them (as if `drop_nameless=True`)

**Changes:**
- Removed the `drop_nameless` parameter from the function signature
- Removed the parameter documentation from the docstring
- Added a "Note" section to the docstring clarifying that instances without a Name tag are automatically excluded

---

## 2026-01-18: Remove deprecated `ec2_client` backwards compatibility shim

**File:** `remote/utils.py`

**Issue:** The module contained deprecated backwards compatibility code for accessing `ec2_client` as a module-level attribute:
1. Lines 59-62 had a comment indicating the deprecated attribute "will be removed in v0.5.0"
2. Lines 65-74 defined a `__getattr__` function providing lazy access to `ec2_client` for backwards compatibility
3. The `Any` type was imported solely for this `__getattr__` function's return type

After scanning the entire codebase, no code was found using the deprecated `ec2_client` attribute:
- All modules use `get_ec2_client()` function directly
- All test files use local mock variables named `mock_ec2_client`, not the deprecated module attribute

**Changes:**
- Removed the deprecation comment block (lines 59-62)
- Removed the `__getattr__` function (lines 65-74)

---

## 2026-01-18: Remove deprecated `ecs_client` backwards compatibility shim

**File:** `remote/ecs.py`

**Issue:** The module contained dead code for backwards compatibility access to `ecs_client` as a module-level attribute:
1. Lines 29-30 had a comment about backwards compatibility
2. Lines 33-37 defined a `__getattr__` function providing lazy access to `ecs_client`
3. The `Any` type was imported solely for this `__getattr__` function's return type

After scanning the entire codebase, no code was found using the deprecated `ecs_client` attribute:
- All ECS functions use `get_ecs_client()` function directly (lines 72, 106, 136)
- All test files mock `get_ecs_client`, not the deprecated module attribute
- No imports of `ecs_client` exist anywhere in the codebase

This is similar to the `ec2_client` shim that was removed from `utils.py` in a previous refactor.

**Changes:**
- Removed the `Any` type from imports (no longer needed)
- Removed the backwards compatibility comment (lines 29-30)
- Removed the `__getattr__` function (lines 33-37)

---

## 2026-01-18: Remove unused `ENV_PREFIX` constant from `config.py`

**File:** `remote/config.py`

**Issue:** Line 30 defined `ENV_PREFIX = "REMOTE_"` but this constant was never used anywhere in the codebase:
1. The actual environment prefix is hardcoded in `RemoteConfig.model_config` as `env_prefix="REMOTE_"` (line 52)
2. No other code references `ENV_PREFIX`
3. The constant was misleading since it appeared to be the source of truth but wasn't actually used

**Changes:**
- Removed the unused `ENV_PREFIX = "REMOTE_"` constant
- Removed the associated comment "Environment variable mapping for config values"

---

## 2026-01-18: Rename `in_duration` parameter to `stop_in` for consistency

**File:** `remote/instance.py`

**Issue:** The `stop()` function used parameter name `in_duration` while the `start()` function used `stop_in` for the same purpose (scheduling automatic shutdown). This inconsistency created cognitive overhead when working with both functions:
- `start()` (line 375): parameter `stop_in` with CLI flag `--stop-in`
- `stop()` (line 601): parameter `in_duration` with CLI flag `--in`

Both parameters serve the same purpose: specifying a duration after which the instance should be stopped.

**Changes:**
- Renamed `in_duration` to `stop_in` in the `stop()` function signature (line 601)
- Updated all references to `in_duration` within the function body (lines 641, 649)
- The CLI flag `--in` remains unchanged for backwards compatibility

---

## 2026-01-18: Rename `type` function and parameter to avoid shadowing Python built-in

**File:** `remote/instance.py`

**Issue:** The `type()` command function and its `type` parameter shadowed the Python built-in `type`. This is problematic because:
1. The function name `type` shadows the built-in `type()` function at module scope
2. The parameter `type` shadows the built-in within the function body
3. This prevents using the built-in `type()` for any introspection within this function
4. It's a code smell that can cause subtle bugs and confuses static analysis tools

**Changes:**
- Renamed function from `type` to `instance_type` with `@app.command("type")` decorator to preserve CLI command name
- Renamed parameter from `type` to `new_type` to avoid shadowing the built-in
- Updated all references within the function body to use `new_type`
- Changed the else branch's reassignment from `type = get_instance_type(...)` to `current_instance_type = get_instance_type(...)` to avoid confusion

---

## 2026-01-18: Add missing `width=200` to Console initialization in `config.py`

**File:** `remote/config.py`

**Issue:** The module-level `console` initialization on line 18 was inconsistent with all other modules:
- `config.py` used: `Console(force_terminal=True)` (missing width)
- All other modules used: `Console(force_terminal=True, width=200)`

Affected modules with consistent pattern:
- `utils.py:32`: `Console(force_terminal=True, width=200)`
- `snapshot.py:13`: `Console(force_terminal=True, width=200)`
- `ecs.py:30`: `Console(force_terminal=True, width=200)`
- `volume.py:13`: `Console(force_terminal=True, width=200)`
- `instance.py:44`: `Console(force_terminal=True, width=200)`
- `ami.py:24`: `Console(force_terminal=True, width=200)`

This inconsistency could cause different output formatting in `config.py` commands compared to other modules.

**Changes:**
- Changed line 18 from `Console(force_terminal=True)` to `Console(force_terminal=True, width=200)`

---

## 2026-01-18: Remove unused `is_instance_stopped()` function

**File:** `remote/utils.py`

**Issue:** The `is_instance_stopped()` function (lines 424-460) was defined but never called anywhere in the production codebase:
1. The function checked if an EC2 instance was in "stopped" state
2. It was only referenced in test files (`tests/test_utils.py`)
3. No production code in the `remote/` directory ever called this function
4. The similar function `is_instance_running()` is actively used, but `is_instance_stopped()` was dead code

**Changes:**
- Removed the `is_instance_stopped()` function from `remote/utils.py`
- Removed the import of `is_instance_stopped` from `tests/test_utils.py`
- Removed the two associated test functions `test_is_instance_stopped_true()` and `test_is_instance_stopped_false()` from `tests/test_utils.py`

---

## 2026-01-18: Remove duplicate `list_launch_templates()` function from `instance.py`

**File:** `remote/instance.py`

**Issue:** The `list_launch_templates()` function (lines 922-952) was duplicated in both `instance.py` and `ami.py`:
1. `instance.py` version: Simple implementation with basic table display
2. `ami.py` version: Feature-rich implementation with `--filter` and `--details` options

The duplicate in `instance.py` was:
- A subset of the `ami.py` functionality
- Inconsistent with DRY (Don't Repeat Yourself) principle
- Creating maintenance burden for similar functionality in two places

Users can use `remote ami list-templates` which provides the same functionality plus additional features like filtering and detailed output.

**Changes:**
- Removed the `list_launch_templates()` function from `remote/instance.py`
- Removed the corresponding test `test_list_launch_templates_command()` from `tests/test_instance.py`

---

## 2026-01-18: Remove unused `ConfigurationError` exception class

**File:** `remote/exceptions.py`

**Issue:** The `ConfigurationError` exception class (lines 132-142) was defined but never used anywhere in the codebase:
1. No code raised this exception
2. No code caught this exception
3. No tests referenced this exception class
4. The class was complete dead code adding unnecessary lines to the module

The exception was designed for configuration-related errors but was never integrated into the config handling code.

**Changes:**
- Removed the `ConfigurationError` class definition from `remote/exceptions.py`

---

## 2026-01-18: Remove unused `InvalidInstanceStateError` exception class

**File:** `remote/exceptions.py`

**Issue:** The `InvalidInstanceStateError` exception class (lines 51-65) was defined but never raised anywhere in the codebase:
1. No code raised this exception - grep search for `InvalidInstanceStateError` in the `remote/` directory only found the class definition itself
2. The exception was designed for instance state validation errors but was never integrated
3. Tests existed for the class (`tests/test_exceptions.py` lines 90-118) but only tested that the class worked correctly, not that it was actually used
4. Similar to `ConfigurationError` which was removed in commit 50886f1

**Changes:**
- Removed the `InvalidInstanceStateError` class definition from `remote/exceptions.py`
- Removed the import and test class `TestInvalidInstanceStateError` from `tests/test_exceptions.py`

---

## 2026-01-18: Extract `_build_ssh_command()` helper to reduce SSH argument duplication

**File:** `remote/instance.py`

**Issue:** The SSH argument building code was duplicated in two functions:
1. `_schedule_shutdown()` (lines 486-494) - built SSH args for scheduling shutdown
2. `_cancel_scheduled_shutdown()` (lines 552-560) - built identical SSH args for cancelling shutdown

Both functions contained the exact same SSH argument list:
```python
ssh_args = [
    "ssh",
    "-o",
    "StrictHostKeyChecking=accept-new",
    "-o",
    "BatchMode=yes",
    "-o",
    "ConnectTimeout=10",
]
if key:
    ssh_args.extend(["-i", key])
ssh_args.append(f"{user}@{dns}")
```

This duplication meant any changes to SSH options (e.g., adding new options, changing timeout) would need to be made in multiple places.

**Changes:**
- Added new helper function `_build_ssh_command(dns, key, user)` that returns the base SSH command arguments
- Updated `_schedule_shutdown()` to use the new helper
- Updated `_cancel_scheduled_shutdown()` to use the new helper
- Reduced code duplication by ~14 lines

---

## 2026-01-18: Consolidate datetime imports to module level in `instance.py`

**File:** `remote/instance.py`

**Issue:** The `datetime` module was imported inconsistently in three different locations inside functions rather than at the module level:
- Line 68: `from datetime import timezone` (inside `_get_raw_launch_times`)
- Line 159: `from datetime import datetime, timezone` (inside `list_instances`)
- Line 498: `from datetime import datetime, timedelta, timezone` (inside `_schedule_shutdown`)

This pattern is inconsistent with other modules like `utils.py` which imports datetime at the module level (line 2). Inline imports inside functions:
1. Reduce code readability
2. Make it harder to see all module dependencies at a glance
3. Create slight performance overhead from repeated imports (though Python caches them)

**Changes:**
- Added `from datetime import datetime, timedelta, timezone` at the module level (after line 4)
- Removed the three inline imports from `_get_raw_launch_times`, `list_instances`, and `_schedule_shutdown` functions

---

## 2026-01-18: Centralize console initialization in `utils.py`

**Issue:** Duplicated `console = Console(force_terminal=True, width=200)` initialization across 7 modules:
- `remote/utils.py:32`
- `remote/ami.py:24`
- `remote/config.py:18`
- `remote/ecs.py:30`
- `remote/instance.py:45`
- `remote/snapshot.py:13`
- `remote/volume.py:13`

This duplication meant any changes to console configuration would need to be made in 7 places. It also increased the risk of inconsistency (as seen in the previous `config.py` fix where `width=200` was missing).

**Changes:**
- Kept the single console instance in `remote/utils.py`
- Updated all other modules to import `console` from `remote.utils` instead of creating their own instances
- Removed redundant `from rich.console import Console` imports where Console was only used for the module-level instance

**Files Modified:**
- `remote/ami.py` - Import console from utils, remove Console import
- `remote/config.py` - Import console from utils, remove Console import
- `remote/ecs.py` - Import console from utils, remove Console import
- `remote/instance.py` - Import console from utils (kept Console import for local use in `_watch_status`)
- `remote/snapshot.py` - Import console from utils, remove Console import
- `remote/volume.py` - Import console from utils, remove Console import

**Note:** `remote/instance.py` still imports `Console` from `rich.console` because the `_watch_status` function creates a separate Console instance for its Live display functionality.

---

## 2026-01-18: Remove redundant Console creation in `_watch_status()`

**File:** `remote/instance.py`

**Issue:** The `_watch_status()` function created a new `Console()` instance on line 305:
```python
watch_console = Console()
```

This was redundant because:
1. The module already imports `console` from `remote.utils` (centralized console instance)
2. The local `watch_console` duplicated functionality already available
3. This was noted as an exception in the previous refactor, but there's no reason not to reuse the shared console

**Changes:**
- Removed the `watch_console = Console()` line from `_watch_status()`
- Changed `Live(console=watch_console, ...)` to `Live(console=console, ...)`
- Changed `watch_console.print(...)` to `console.print(...)`
- Removed the now-unused `from rich.console import Console` import

This completes the console centralization refactor - all modules now use the shared `console` instance from `remote/utils.py`.

---

## 2026-01-18: Remove redundant `get_instance_type()` call in `instance_type()` function

**File:** `remote/instance.py`

**Issue:** The `instance_type()` function called `get_instance_type()` twice to retrieve the same value:
1. Line 833: `current_type = get_instance_type(instance_id)` - first call at function start
2. Line 909: `current_instance_type = get_instance_type(instance_id)` - redundant second call in the else branch

Both calls retrieved the same value for the same `instance_id`. The second call was unnecessary because:
- `current_type` was already available and unchanged
- This was making a redundant AWS API call
- The variable naming inconsistency (`current_type` vs `current_instance_type`) obscured the duplication

**Changes:**
- Removed the redundant `get_instance_type()` call in the else branch
- Reused the existing `current_type` variable instead of creating `current_instance_type`
- This eliminates one AWS API call when displaying current instance type

---

## 2026-01-18: Remove misleading return type from `list_launch_templates()` Typer command

**File:** `remote/ami.py`

**Issue:** The `list_launch_templates()` function had a misleading API contract:
1. Return type annotation was `-> list[dict[str, Any]]`
2. Line 117 returned an empty list `[]`
3. Line 161 returned `templates` list
4. However, as a Typer CLI command (decorated with `@app.command("list-templates")`), the return value is never consumed by callers

This is problematic because:
- Typer command functions should return `None` or have no return type annotation
- The returned value was never used by the CLI framework
- The return type annotation created a misleading API contract implying the value could be used programmatically
- The `Any` type import was only needed for this return type

**Changes:**
- Changed return type from `-> list[dict[str, Any]]` to `-> None`
- Changed `return []` on line 117 to `return` (early exit with no value)
- Removed `return templates` statement on line 161 (implicit None return)
- Removed the now-unused `from typing import Any` import

---

## 2026-01-18: Replace overly broad exception handling in `config.py`

**File:** `remote/config.py`

**Issue:** Three locations used overly broad `except Exception` clauses:
1. Line 195: `except Exception as e:` in `ConfigValidationResult.validate_config()`
2. Lines 268-270: `except Exception as e:` in `ConfigManager.get_instance_name()`
3. Lines 295-296: `except Exception as e:` in `ConfigManager.get_value()`

This is problematic because:
- `except Exception` catches too many exception types including ones that shouldn't be silently handled
- It can mask unexpected errors and make debugging harder
- The prior except blocks already handled specific cases (`configparser.Error`, `OSError`, `PermissionError`, `KeyError`, `TypeError`, `AttributeError`)
- The only remaining realistic exception type is `ValueError` from Pydantic validation

**Changes:**
- Line 195: Changed `except Exception as e:` to `except ValueError as e:` (Pydantic's `ValidationError` inherits from `ValueError`)
- Lines 268-270: Changed `except Exception as e:` to `except ValueError as e:` with updated error message "Config validation error"
- Lines 295-296: Changed `except Exception as e:` to `except ValueError as e:` with updated error message "Config validation error"

This makes the error handling explicit and specific to the documented exceptions, consistent with the refactor in PR #48 which addressed similar issues in `ami.py`.

---

## 2026-01-18: Extract duplicated `launch()` logic into shared utility function

**Files:** `remote/utils.py`, `remote/ami.py`, `remote/instance.py`, `tests/test_ami.py`

**Issue:** The `launch()` function was duplicated nearly identically (~130 lines) in both `remote/ami.py` (lines 162-296) and `remote/instance.py` (lines 916-1050). This was identified as the highest priority code smell during codebase analysis.

Both modules had identical logic for:
1. Checking default template from config
2. Interactive template selection with table display
3. User input validation for template number
4. Name suggestion with random string generation
5. Instance launch via `run_instances()` API
6. Result display with Rich panel

The only differences were:
- Docstring examples (different command names)
- Minor whitespace/comment differences

This duplication violated DRY (Don't Repeat Yourself) and meant any bug fix or feature change needed to be made in two places.

**Changes:**
- Added new shared function `launch_instance_from_template()` in `remote/utils.py` containing all the common launch logic
- Added necessary imports to `remote/utils.py`: `random`, `string`, `Panel`, `Table`, `validate_array_index`
- Simplified `launch()` in `remote/ami.py` to a thin wrapper (from ~135 lines to ~15 lines) calling the shared function
- Simplified `launch()` in `remote/instance.py` to a thin wrapper (from ~135 lines to ~15 lines) calling the shared function
- Removed unused imports from `ami.py`: `random`, `string`, `Panel`, `config_manager`, `get_launch_template_id`, `ValidationError`, `safe_get_array_item`, `validate_array_index`
- Removed unused imports from `instance.py`: `random`, `string`, `get_launch_template_id`, `get_launch_templates`, `validate_array_index`
- Updated test mocks in `tests/test_ami.py` to patch `remote.utils` and `remote.config` instead of `remote.ami`

**Impact:**
- ~130 lines of duplicated code removed
- Single source of truth for launch logic
- Easier maintenance - changes only needed in one place
- All 405 tests pass

