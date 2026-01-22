# Progress Log

## 2026-01-18: Fix inconsistent filtering in `get_instance_ids()`

**Files:** `remote/utils.py`, `remote/instance.py`, `remote/config.py`, `tests/test_utils.py`

**Issue:** The `get_instance_ids()` function had inconsistent filtering behavior compared to `get_instance_info()`:

1. `get_instance_info()` iterates through ALL instances in each reservation but filters out instances without a Name tag
2. `get_instance_ids()` only took the FIRST instance from each reservation and did NOT filter by Name tag

This inconsistency meant the arrays returned by these functions could have different lengths when used together. The code worked around this with `strict=False` in `zip()` calls, which silently truncated to the shortest array - masking potential data misalignment bugs.

**Changes:**
- Updated `get_instance_ids()` in `remote/utils.py` to:
  - Iterate through ALL instances in each reservation (not just the first)
  - Filter instances to only include those with a Name tag (matching `get_instance_info()`)
- Changed `strict=False` to `strict=True` in zip calls in:
  - `remote/instance.py:134` (list_instances command)
  - `remote/config.py:434` (add command)
- Added new test `test_get_instance_ids_filters_instances_without_name_tag()` to verify the filtering behavior

---

## 2026-01-18: Remove unused `validate_snapshot_id()` function

**Files:** `remote/validation.py`, `tests/test_validation.py`

**Issue:** The `validate_snapshot_id()` function was defined in `validation.py` but never used anywhere in the application. While it was tested in `test_validation.py`, the function itself had no callers in the actual codebase. This is dead code that should be removed to keep the codebase clean.

**Changes:**
- Removed the `validate_snapshot_id()` function from `remote/validation.py` (lines 104-129)
- Removed the `TestValidateSnapshotId` test class from `tests/test_validation.py` (lines 190-219)
- Removed the `validate_snapshot_id` import from `tests/test_validation.py`

---

## 2026-01-18: Standardize Typer parameter style in `status()` command

**File:** `remote/instance.py`

**Issue:** The `status()` command used the `Annotated[]` style for parameter type annotations while all other commands in the file (and throughout the codebase) used the simpler inline style:

- `status()` used:
  ```python
  instance_name: Annotated[str | None, typer.Argument(help="Instance name")] = None
  watch: Annotated[bool, typer.Option("--watch", "-w", help="...")] = False
  ```

- All other commands used:
  ```python
  instance_name: str | None = typer.Argument(None, help="Instance name")
  watch: bool = typer.Option(False, "--watch", "-w", help="...")
  ```

This inconsistency:
1. Made the codebase harder to read
2. Created confusion about which style to use for new commands
3. Required an unnecessary `Annotated` import in `instance.py`

**Changes:**
- Changed `status()` parameters from `Annotated[]` style to inline style:
  - `instance_name`: `Annotated[str | None, typer.Argument(help="Instance name")] = None` → `str | None = typer.Argument(None, help="Instance name")`
  - `watch`: `Annotated[bool, typer.Option("--watch", "-w", help="...")] = False` → `bool = typer.Option(False, "--watch", "-w", help="...")`
  - `interval`: `Annotated[int, typer.Option("--interval", "-i", help="...")] = 2` → `int = typer.Option(2, "--interval", "-i", help="...")`
- Removed the now-unused `Annotated` import from `typing`

---

## 2026-01-18: Fix inconsistent docstring formatting in `ecs.py`

**File:** `remote/ecs.py`

**Issue:** Multiple functions had inconsistent docstring formatting compared to the rest of the codebase:
1. Docstrings with opening `"""` on a separate line instead of inline with the description
2. Missing 4-space indentation in Args and Returns sections
3. Redundant type annotations in docstrings (types should be in function signatures only)

Affected functions:
- `get_all_clusters()` (lines 46-57)
- `get_all_services()` (lines 77-91)
- `scale_service()` (lines 111-122)
- `prompt_for_cluster_name()` (lines 137-143)
- `prompt_for_services_name()` (lines 180-189)
- `list_clusters()` (lines 249-254)
- `list_services()` (lines 273-279)
- `scale()` (lines 302-313)

**Changes:**
- Moved docstring descriptions to same line as opening `"""`
- Added proper 4-space indentation to Args and Returns sections
- Removed redundant type annotations (e.g., `cluster_name (str):` → `cluster_name:`)
- Removed redundant type prefixes in Returns (e.g., `list: A list of...` → `A list of...`)

This makes the docstrings consistent with the style used in `utils.py` and other modules.

---

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

---

## 2026-01-18: Remove unused `get_instance_pricing_info()` function

**File:** `remote/pricing.py`

**Issue:** The `get_instance_pricing_info()` function (lines 205-228) was never used in the application code:
1. Only `get_instance_price_with_fallback()` was imported and used by `remote/instance.py`
2. `get_instance_pricing_info()` was a higher-level wrapper that was only exercised by tests
3. The function provided formatted strings and a dictionary that duplicated what `format_price()` and `get_monthly_estimate()` already provided separately
4. According to `specs/issue-37-pricing-region-fallback.md`, the function was part of the original implementation plan but the actual implementation used the lower-level functions directly

**Changes:**
- Removed the `get_instance_pricing_info()` function from `remote/pricing.py`
- Removed the import of `get_instance_pricing_info` from `tests/test_pricing.py`
- Removed the `TestGetInstancePricingInfo` test class from `tests/test_pricing.py`
- Updated `specs/issue-37-pricing-region-fallback.md` to remove references to the unused function

**Impact:**
- ~24 lines of dead code removed
- ~60 lines of tests for dead code removed
- Cleaner module API surface

---

## 2026-01-18: Add explicit exit codes to `typer.Exit()` calls in `ecs.py`

**File:** `remote/ecs.py`

**Issue:** Two `typer.Exit()` calls lacked explicit exit codes:
1. Line 148 in `prompt_for_cluster_name()`: `raise typer.Exit()` when no clusters found
2. Line 194 in `prompt_for_services_name()`: `raise typer.Exit()` when no services found

While `typer.Exit()` defaults to exit code 0, this is implicit and inconsistent with other exit calls in the codebase that explicitly specify the exit code. Best practice is to be explicit about exit codes:
- Exit code 0: Success or informational (no error)
- Exit code 1: Error condition

Both of these cases are informational ("No clusters found", "No services found") rather than error conditions, so exit code 0 is correct but should be explicit.

**Changes:**
- Line 148: Changed `raise typer.Exit()` to `raise typer.Exit(0)`
- Line 194: Changed `raise typer.Exit()` to `raise typer.Exit(0)`

This makes the code consistent with other exit calls in the codebase and explicitly documents the intent that these are successful exits (no error), not implicit defaults.

---

## 2026-01-18: Standardize ConfigParser variable naming in `config.py`

**File:** `remote/config.py`

**Issue:** Inconsistent variable naming for `configparser.ConfigParser` objects throughout the file:
- Some functions used `cfg`: `read_config()`, `write_config()`, `show()`, `get_value()`, `unset_value()`
- Other functions used `config`: `ConfigManager.set_value()`, `ConfigManager.get_value()`, `init()`

This inconsistency made the code harder to follow and violated the principle of uniform naming conventions.

**Changes:**
- Renamed `cfg` to `config` in `read_config()` function (lines 346-349)
- Changed `write_config()` parameter from `cfg` to `config` (line 360)
- Renamed `cfg` to `config` in `show()` command (line 378)
- Renamed `cfg` to `config` in `get_value()` command (line 493)
- Renamed `cfg` to `config` in `unset_value()` command (lines 513, 515, 519, 520)

This standardizes on `config` as the variable name throughout the file, which is more descriptive and consistent with the ConfigManager class methods.

---

## 2026-01-18: Remove unused `if __name__ == "__main__"` blocks

**Files:** `remote/ami.py`, `remote/config.py`, `remote/instance.py`, `remote/snapshot.py`, `remote/volume.py`

**Issue:** Five modules contained dead code in the form of unused `if __name__ == "__main__"` blocks:
- `remote/ami.py` (line 296)
- `remote/config.py` (line 621)
- `remote/instance.py` (line 1036)
- `remote/snapshot.py` (line 88)
- `remote/volume.py` (line 61)

These modules are library code imported into `__main__.py`, not executed directly. The `if __name__ == "__main__"` blocks were never executed because:
1. The package entry point is `remote/__main__.py` which imports and composes the sub-applications
2. Users run `remote <command>` not `python -m remote.instance` etc.
3. These blocks added no value and cluttered the code

**Changes:**
- Removed `if __name__ == "__main__": app()` block from all five modules

---

## 2026-01-18: Remove unused return value from `write_config()` function

**File:** `remote/config.py`

**Issue:** The `write_config()` function returned a `configparser.ConfigParser` object, but this return value was never used by any caller:
- Line 313: `write_config(config, config_path)` - return value ignored
- Line 331: `write_config(config, config_path)` - return value ignored
- Line 520: `write_config(config, config_path)` - return value ignored
- Line 557: `write_config(config, config_path)` - return value ignored

This created a misleading function signature - if a function's return value is never used, it shouldn't return anything. The returned value was the same `config` object that was passed in as a parameter, providing no additional information to callers.

**Changes:**
- Changed return type annotation from `-> configparser.ConfigParser` to `-> None`
- Removed the `return config` statement from the function body

---

## 2026-01-18: Remove unused `get_snapshot_status()` function

**File:** `remote/utils.py`

**Issue:** The `get_snapshot_status()` function (lines 549-581) was defined but never called anywhere in the production codebase:
1. The function returned the status of an EBS snapshot by calling AWS `describe_snapshots` API
2. It was only referenced in test files (`tests/test_utils.py`)
3. No production code in the `remote/` directory ever called this function
4. While `snapshot.py` has commands for creating and listing snapshots, none of them used this status-checking function

**Changes:**
- Removed the `get_snapshot_status()` function from `remote/utils.py`
- Removed the import of `get_snapshot_status` from `tests/test_utils.py`
- Removed the three associated test functions from `tests/test_utils.py`:
  - `test_get_snapshot_status()` - happy path test
  - `test_get_snapshot_status_snapshot_not_found_error()` - error handling test
  - `test_get_snapshot_status_other_client_error()` - error handling test

---

## 2026-01-18: Move misplaced Terraform comment in `terminate()` function

**File:** `remote/instance.py`

**Issue:** The comment "# If the instance is managed by Terraform, warn user" on line 963 was separated from the code it described by 20 lines. The actual Terraform check (`terraform_managed = any(...)`) was on line 983, with the confirmation prompts and user input validation in between.

This is a code smell because:
1. Orphaned comments reduce readability
2. The comment implied the next line would be the Terraform check, but it wasn't
3. Readers had to mentally reconnect the comment to its relevant code

**Changes:**
- Removed the comment from line 963 (after the tag fetching try-except block)
- Added the comment directly above line 981 where `terraform_managed` is assigned

This places the comment immediately before the code it documents, following the principle that comments should be adjacent to the code they describe.

---

## 2026-01-18: Simplify config path assignment using ternary operator

**File:** `remote/config.py`

**Issue:** Two methods in `config.py` used verbose if-else blocks for config path assignment that could be simplified using ternary operators (SIM108 code smell):

```python
# Before (4 lines):
if config_path is None:
    config_path = Settings.get_config_path()
else:
    config_path = Path(config_path)
```

This pattern appeared in:
- `RemoteConfig.from_ini_file()` (lines 137-140)
- `ConfigValidationResult.validate_config()` (lines 179-182)

The ruff linter flagged these as SIM108 violations, recommending ternary operator syntax for simpler code.

**Changes:**
- Replaced both if-else blocks with ternary operators:
  ```python
  config_path = Settings.get_config_path() if config_path is None else Path(config_path)
  ```
- This reduces each 4-line block to a single line while maintaining the same behavior
- The change is purely stylistic with no functional impact

---

## 2026-01-18: Use `config_manager.remove_value()` in `unset_value()` CLI command

**File:** `remote/config.py`

**Issue:** The `unset_value()` CLI command (lines 500-519) bypassed the `ConfigManager.remove_value()` method and directly manipulated the config file, while other similar CLI commands properly used the ConfigManager abstraction:

- `set_value()` correctly used `config_manager.set_value(key, value, config_path)` (line 472)
- `add()` correctly used `config_manager.set_instance_name(instance_name, config_path)` (line 449)
- `unset_value()` incorrectly bypassed the manager:
  ```python
  config = read_config(config_path)
  config.remove_option("DEFAULT", key)
  write_config(config, config_path)
  ```

This was problematic because:
1. **Violated encapsulation**: The proper `ConfigManager.remove_value()` method exists but wasn't used
2. **Broke consistency**: Other similar operations use the manager abstraction
3. **Missing state management**: `ConfigManager.remove_value()` properly resets the cached pydantic config with `self._pydantic_config = None`, but the direct approach didn't, which could lead to stale cached configuration data

**Changes:**
- Replaced direct config file manipulation with `config_manager.remove_value(key, config_path)`
- Simplified the logic using the boolean return value to check if the key existed
- Reduced code duplication by using the existing abstraction

---

## 2026-01-18: Remove unused `get_monthly_estimate()` function and `HOURS_PER_MONTH` constant

**Files:** `remote/pricing.py`, `tests/test_pricing.py`

**Issue:** The `get_monthly_estimate()` function (lines 174-185) and `HOURS_PER_MONTH` constant (line 48) were defined but never used anywhere in the application code:
1. No code in the `remote/` directory called `get_monthly_estimate()`
2. `HOURS_PER_MONTH` was only used by `get_monthly_estimate()`
3. The function was only exercised by tests
4. This is similar to `get_instance_pricing_info()` which was removed in a previous refactor

The function calculated monthly cost estimates from hourly prices, but the actual application displays hourly prices directly without converting to monthly estimates.

**Changes:**
- Removed the `HOURS_PER_MONTH = 730` constant from `remote/pricing.py`
- Removed the `get_monthly_estimate()` function from `remote/pricing.py`
- Removed the `HOURS_PER_MONTH` and `get_monthly_estimate` imports from `tests/test_pricing.py`
- Removed the `TestGetMonthlyEstimate` test class from `tests/test_pricing.py`

**Impact:**
- ~15 lines of dead code removed from production code
- ~24 lines of tests for dead code removed
- Cleaner module API surface

---

## 2026-01-18: Extract duplicate exception handling in `ConfigManager` to helper method

**File:** `remote/config.py`

**Issue:** The `ConfigManager` class had duplicate exception handling blocks in two methods:
- `get_instance_name()` (lines 255-264)
- `get_value()` (lines 285-290)

Both methods contained identical exception handling code:
```python
except (configparser.Error, OSError, PermissionError) as e:
    typer.secho(f"Warning: Could not read config file: {e}", fg=typer.colors.YELLOW)
except (KeyError, TypeError, AttributeError):
    typer.secho("Warning: Config file structure is invalid", fg=typer.colors.YELLOW)
except ValueError as e:
    typer.secho(f"Warning: Config validation error: {e}", fg=typer.colors.YELLOW)
```

This duplication meant any changes to error handling would need to be made in multiple places.

**Changes:**
- Added new helper method `_handle_config_error(self, error: Exception)` that centralizes the error handling logic
- Updated `get_instance_name()` to catch all config-related exceptions in a single except clause and delegate to the helper
- Updated `get_value()` to use the same pattern
- Reduced code duplication by ~12 lines

---

## 2026-01-18: Fix `get_value` CLI command to use `ConfigManager` consistently

**File:** `remote/config.py`

**Issue:** The `get_value()` CLI command (lines 482-503) bypassed the `ConfigManager.get_value()` method and directly read from the config file:

```python
# Before - bypassed ConfigManager
config = read_config(config_path)
value = config.get("DEFAULT", key, fallback=None)
```

This was inconsistent with other CLI commands:
- `set_value()` correctly used `config_manager.set_value(key, value, config_path)` (line 478)
- `add()` correctly used `config_manager.set_instance_name(instance_name, config_path)` (line 455)
- `unset_value()` correctly used `config_manager.remove_value(key, config_path)`

This inconsistency meant:
1. **Missing validation**: `ConfigManager.get_value()` uses Pydantic validation for config values
2. **Missing env var overrides**: `ConfigManager.get_value()` supports `REMOTE_*` environment variable overrides
3. **Missing key validation**: The CLI command didn't validate that `key` was a known config key
4. **Violated encapsulation**: The proper `ConfigManager.get_value()` method exists but wasn't used

**Changes:**
- Renamed function from `get_value` to `get_value_cmd` to avoid name collision with the CLI command decorator
- Added key validation against `VALID_KEYS` (consistent with `set_value` command)
- For default config path: delegate to `config_manager.get_value(key)` for full Pydantic validation and env var override support
- For custom config paths: continue reading directly from file (as ConfigManager is bound to default path)
- Updated docstring to document environment variable override support

---

## 2026-01-18: Extract hardcoded time constants in `instance.py`

**File:** `remote/instance.py`

**Issue:** Multiple hardcoded magic numbers for time-related values were scattered throughout the file, making the code harder to understand and maintain:

| Line | Magic Number | Purpose |
|------|--------------|---------|
| 165 | `3600` | Seconds per hour for uptime calculation |
| 411 | `60` | Max wait time for instance startup |
| 412 | `5` | Poll interval during startup wait |
| 710 | `20` | Sleep duration between connection retries |
| 709 | `5` | Max connection attempts |
| 1018-1022 | `60`, `24 * 60` | Seconds/minutes conversion for uptime formatting |

These magic numbers:
1. Made the code harder to read without context
2. Required hunting through the codebase to understand what values were being used
3. Risked inconsistency if similar values were used elsewhere

**Changes:**
- Added module-level constants at the top of the file:
  - `SECONDS_PER_MINUTE = 60`
  - `SECONDS_PER_HOUR = 3600`
  - `MINUTES_PER_DAY = 24 * 60`
  - `MAX_STARTUP_WAIT_SECONDS = 60`
  - `STARTUP_POLL_INTERVAL_SECONDS = 5`
  - `CONNECTION_RETRY_SLEEP_SECONDS = 20`
  - `MAX_CONNECTION_ATTEMPTS = 5`
- Updated all usages to reference the named constants instead of magic numbers

**Impact:**
- Improved code readability and self-documentation
- Centralized configuration of timing-related behavior
- Made it easier to adjust values if needed in the future

---

## 2026-01-18: Extract hardcoded SSH readiness sleep to constant

**File:** `remote/instance.py`

**Issue:** The hardcoded value `10` was used for SSH readiness wait times in two locations:
- Line 444: `time.sleep(10)` - waiting for SSH to be ready after instance startup
- Line 755: `time.sleep(10)` - sleep between connection retry attempts

These magic numbers:
1. Made the code harder to understand without context
2. Required searching the codebase to find all related wait times
3. Made it difficult to adjust the SSH wait time consistently

**Changes:**
- Added `SSH_READINESS_WAIT_SECONDS = 10` constant to the "Instance startup/connection constants" section
- Updated both `time.sleep(10)` calls to use `time.sleep(SSH_READINESS_WAIT_SECONDS)`

This follows the established pattern of extracting time-related constants, as done in previous refactors for `STARTUP_POLL_INTERVAL_SECONDS`, `CONNECTION_RETRY_SLEEP_SECONDS`, etc.

---

## 2026-01-18: Add `MINUTES_PER_HOUR` constant for semantic correctness in `_format_uptime()`

**File:** `remote/instance.py`

**Issue:** The `_format_uptime()` function used `SECONDS_PER_MINUTE` (value: 60) to perform arithmetic on variables measured in minutes, not seconds:

```python
# Before - semantically incorrect
hours = remaining // SECONDS_PER_MINUTE  # remaining is in minutes!
minutes = remaining % SECONDS_PER_MINUTE  # remaining is in minutes!
```

While mathematically correct (60 seconds per minute = 60 minutes per hour), this was semantically misleading because:
1. `remaining` is measured in minutes (from `total_minutes % MINUTES_PER_DAY`)
2. Using `SECONDS_PER_MINUTE` to divide minutes violates the principle of using appropriately-named constants
3. A `MINUTES_PER_HOUR` constant was missing from the time-related constants

**Changes:**
- Added `MINUTES_PER_HOUR = 60` constant alongside existing time constants
- Updated `MINUTES_PER_DAY` to use `24 * MINUTES_PER_HOUR` for consistency
- Changed `_format_uptime()` to use `MINUTES_PER_HOUR` for the hours/minutes calculation

```python
# After - semantically correct
hours = remaining // MINUTES_PER_HOUR  # remaining is in minutes ✓
minutes = remaining % MINUTES_PER_HOUR  # remaining is in minutes ✓
```

---

## 2026-01-19: Fix test argument order for exec command --key option

**File:** `tests/test_instance.py`

**Issue:** The `test_exec_uses_ssh_key_from_option` test was incorrectly placing the `--key` option after the instance name positional argument:
```python
result = runner.invoke(app, ["exec", "test-instance", "--key", "/path/to/key.pem", "ls"])
```

The exec command uses `allow_interspersed_args=False` in its context settings, which means all options must come before positional arguments. This setting is necessary to capture arbitrary commands (like `ls -la | grep foo`) as extra arguments without them being parsed as options.

**Changes:**
- Moved `--key` option before the instance name to fix the test:
```python
result = runner.invoke(app, ["exec", "--key", "/path/to/key.pem", "test-instance", "ls"])
```

---

## 2026-01-19: Fix inconsistent color string literals in `typer.secho()` calls

**File:** `remote/instance.py`

**Issue:** Two `typer.secho()` calls in the `connect()` function used string literals `fg="yellow"` instead of the `typer.colors.YELLOW` constant used throughout the rest of the codebase:

- Line 821: `fg="yellow"` (in "Waiting X seconds to allow instance to initialize" message)
- Line 830: `fg="yellow"` (in "Connecting to instance" message)

All other `typer.secho()` calls in `instance.py` (and the rest of the codebase) consistently use `fg=typer.colors.YELLOW`, `fg=typer.colors.RED`, `fg=typer.colors.GREEN`, etc.

This inconsistency:
1. Made the code style inconsistent
2. Could cause issues if Typer's string-based color support ever changed
3. Reduced code readability by mixing two different patterns

**Changes:**
- Changed line 821 from `fg="yellow"` to `fg=typer.colors.YELLOW`
- Changed line 830 from `fg="yellow"` to `fg=typer.colors.YELLOW`

---

## 2026-01-18: Extract type change polling magic numbers to constants

**File:** `remote/instance.py`

**Issue:** The `instance_type()` function used hardcoded magic numbers for type change polling:
- Line 883: `wait = 5` - maximum polling attempts
- Line 887: `time.sleep(5)` - sleep duration between polls

These magic numbers made the code harder to understand and maintain, and were inconsistent with the established pattern of using named constants for time-related values (e.g., `MAX_STARTUP_WAIT_SECONDS`, `STARTUP_POLL_INTERVAL_SECONDS`).

**Changes:**
- Added two new constants to the "Instance type change polling constants" section:
  - `TYPE_CHANGE_MAX_POLL_ATTEMPTS = 5` - maximum number of polling attempts
  - `TYPE_CHANGE_POLL_INTERVAL_SECONDS = 5` - sleep duration between polls in seconds
- Updated the `instance_type()` function to use these constants instead of hardcoded values

**Impact:**
- Improved code readability and self-documentation
- Consistent with existing patterns for time-related constants
- Easier to adjust polling behavior if needed in the future

---

