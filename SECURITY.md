# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it by emailing the maintainers directly. Do not create a public GitHub issue for security vulnerabilities.

Please include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We will respond within 48 hours and work with you to understand and address the issue.

## Security Measures

### Credential Handling

- AWS credentials are managed through boto3's standard credential chain
- No credentials are stored in config files or logged
- The config file only stores preferences (instance names, SSH user, etc.)
- Environment variables and AWS credential files are used per AWS best practices

### Input Validation

- All user input is validated before use
- Instance names and resource IDs are validated against AWS patterns
- Array indices are bounds-checked to prevent index errors
- File paths are validated before file operations

### SSH Security

- SSH commands are constructed as argument lists (no shell injection risk)
- `subprocess.run()` is used without `shell=True`
- Default SSH behavior uses `StrictHostKeyChecking=accept-new` (secure)
- The `--no-strict-host-key` flag is available but documented as less secure

### File System Security

- Config files are stored in `~/.config/remote.py/`
- File paths with spaces are properly quoted
- No arbitrary file operations from user input

### Subprocess Security

- Only SSH subprocess calls are made
- No shell command execution with user-controlled input
- Subprocess calls use list arguments, not string formatting

### Dependency Security

- Dependencies are regularly audited with `pip-audit`
- Static analysis is performed with `bandit`
- Pre-push hooks run security checks automatically

## Accepted Risks

### B311: Standard pseudo-random generators

The `random` module is used for generating instance name suggestions. This is not a security-sensitive operation as these are just display suggestions, not cryptographic keys.

### B404/B603: Subprocess usage

Subprocess is required for SSH connections. The implementation is secure:
- Uses list arguments (not shell strings)
- No `shell=True`
- User input is not directly interpolated into commands

## Security Tools

The following tools are integrated into the development workflow:

```bash
# Dependency vulnerability scanning
uv run pip-audit

# Static security analysis
uv run bandit -r remote/

# These run automatically on git push via pre-commit hooks
```
