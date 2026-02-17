# Remote.py

[![Tests](https://github.com/ivyleavedtoadflax/remote.py/actions/workflows/test.yml/badge.svg)](https://github.com/ivyleavedtoadflax/remote.py/actions/workflows/test.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python CLI tool for managing AWS resources with a focus on EC2 instances. This is a Python port of the [remote](https://github.com/wellcometrust/remote) tool for controlling remote instances on AWS.

## Features

- **EC2 Instance Management**: Start, stop, connect, list, and terminate instances
- **Remote Execution**: Run commands on remote instances via SSH
- **File Transfer**: Copy and sync files to/from instances using rsync
- **Security Group Management**: Add/remove IP addresses from instance security groups
- **AMI Operations**: Create AMIs and launch instances from images
- **ECS Support**: Manage ECS clusters and services, including scaling operations
- **Volume & Snapshot Management**: List, resize, and manage EBS volumes and snapshots
- **Usage Tracking**: Track cumulative instance costs and runtime statistics
- **Smart Configuration**: Simple config file with sensible defaults
- **Comprehensive Error Handling**: User-friendly error messages for common AWS issues
- **Input Validation**: Safe handling of AWS resource IDs and user input
- **No AWS Credentials Required for Testing**: Comprehensive test suite with mocked AWS calls

## Migration from v0.x to v1.0.0

**Breaking Change**: v1.0.0 removes root-level instance commands. All instance commands now require the `instance` prefix:

| v0.x Command | v1.0.0 Command |
|--------------|----------------|
| `remote start` | `remote instance start` |
| `remote stop` | `remote instance stop` |
| `remote connect` | `remote instance connect` |
| `remote list` | `remote instance list` |
| `remote ls` | `remote instance ls` |
| `remote status` | `remote instance status` |
| `remote launch` | `remote instance launch` |
| `remote terminate` | `remote instance terminate` |

This change provides a cleaner CLI structure with service-specific subcommands.

## Getting Started

### Installation

The package can be installed directly from GitHub using uv (recommended):

```bash
uv tool install git+https://github.com/ivyleavedtoadflax/remote.py.git
```

Or with pipx:

```bash
pipx install git+https://github.com/ivyleavedtoadflax/remote.py.git
```

Or with pip:

```bash
pip install git+https://github.com/ivyleavedtoadflax/remote.py.git
```

## Usage

### Basic Setup

Add the name of your default instance to the config file:

```bash
remote config add
```

Verify your configuration:

```bash
remote config show
```

### Instance Management

Start an instance:

```bash
remote instance start
```

Connect to the instance with SSH:

```bash
remote instance connect
```

Connect with a specific SSH key:

```bash
remote instance connect --key ~/.ssh/my-key.pem
```

Connect with port forwarding and verbose output:

```bash
remote instance connect -p 1234:localhost:1234 -v
```

Stop the instance:

```bash
remote instance stop
```

Get instance status:

```bash
remote instance status
```

List all instances:

```bash
remote instance list
```

Terminate an instance (permanent):

```bash
remote instance terminate
```

### Remote Command Execution

Execute commands on a remote instance:

```bash
remote instance exec my-instance "ls -la"
remote instance exec my-instance "cat /etc/hostname"
```

If the instance is stopped, use `--start` to auto-start it:

```bash
remote instance exec --start my-instance "uptime"
```

### Port Forwarding

Forward a port from a remote instance to localhost (useful for viewing web servers):

```bash
# Forward remote port 8000 to localhost:8000 and open browser
remote instance forward 8000

# Forward remote port 3000 to local port 8000
remote instance forward 8000:3000

# Forward from a specific instance
remote instance forward 8000 my-instance

# Don't automatically open the browser
remote instance forward 8000 --no-browser
```

### File Transfer

Copy files to/from an instance using rsync:

```bash
# Upload a file
remote instance copy ./local-file.txt my-instance:/remote/path/

# Download a file
remote instance copy my-instance:/remote/file.txt ./local-path/

# Sync a directory
remote instance sync ./local-dir/ my-instance:/remote/dir/
```

### Security Group Management

Manage IP access to your instances:

```bash
# Show your current public IP
remote sg my-ip

# Add your IP to an instance's security group
remote sg add my-instance

# Add a specific IP/CIDR
remote sg add my-instance --ip 203.0.113.0/24

# List allowed IPs
remote sg list my-instance

# Remove an IP
remote sg remove my-instance --ip 203.0.113.50/32
```

### Auto-Shutdown

Automatically stop instances when they become idle (based on CPU utilization):

```bash
# Enable auto-shutdown (default: CPU < 5% for 30 min)
remote instance auto-shutdown enable

# Enable with custom thresholds
remote instance auto-shutdown enable my-server --threshold 10 --duration 60

# Check auto-shutdown status
remote instance auto-shutdown status

# Disable auto-shutdown
remote instance auto-shutdown disable

# Clean up orphaned alarm by instance ID (if instance was terminated elsewhere)
remote instance auto-shutdown disable --instance-id i-0123456789abcdef0
```

**Note**: Auto-shutdown uses AWS CloudWatch alarms to stop instances when CPU falls below the threshold for the specified duration. Stopped instances can be started again later. When you terminate an instance using `remote instance terminate`, the associated auto-shutdown alarm is automatically cleaned up.

### Usage Statistics

Track instance usage and costs:

```bash
# View cumulative stats for an instance
remote instance stats my-instance

# Reset tracking data
remote instance tracking-reset my-instance
```

### Working with Different Instances

To run commands on a different instance, pass the name as an argument:

```bash
remote instance status another_ec2_instance
remote instance start my-other-instance
```

### AMI Operations

Create an AMI from an instance:

```bash
remote ami create my-instance
```

Launch an instance from an AMI:

```bash
remote ami launch
```

### ECS Management

List ECS clusters:

```bash
remote ecs list-clusters
```

Scale ECS services:

```bash
remote ecs scale-service my-cluster my-service 3
```

### Volume and Snapshot Management

List EBS volumes:

```bash
remote volume list
```

Resize an EBS volume:

```bash
remote volume resize my-instance --size 100
```

Create a snapshot:

```bash
remote snapshot create vol-12345678
```

List snapshots:

```bash
remote snapshot list
```

## Configuration

RemotePy uses a simple configuration file to store your default instance and other settings.

### Config File Setup

The configuration is stored in `~/.config/remote.py/config.ini`

```bash
# Add default instance interactively
remote config add

# Show current configuration  
remote config show
```

The config file is stored at `~/.config/remote.py/config.ini` and serves as the single source of truth for your settings.

## IAM Permissions

RemotePy requires specific AWS IAM permissions to function. Below are the permissions needed for each feature.

### Complete IAM Policy

This policy includes all permissions needed for the full remote.py tool:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "EC2InstanceManagement",
            "Effect": "Allow",
            "Action": [
                "ec2:DescribeInstances",
                "ec2:DescribeInstanceStatus",
                "ec2:StartInstances",
                "ec2:StopInstances",
                "ec2:TerminateInstances",
                "ec2:ModifyInstanceAttribute",
                "ec2:RunInstances"
            ],
            "Resource": "*"
        },
        {
            "Sid": "EC2VolumeManagement",
            "Effect": "Allow",
            "Action": [
                "ec2:DescribeVolumes",
                "ec2:ModifyVolume",
                "ec2:CreateSnapshot",
                "ec2:DescribeSnapshots"
            ],
            "Resource": "*"
        },
        {
            "Sid": "EC2AMIManagement",
            "Effect": "Allow",
            "Action": [
                "ec2:CreateImage",
                "ec2:DescribeImages"
            ],
            "Resource": "*"
        },
        {
            "Sid": "EC2LaunchTemplates",
            "Effect": "Allow",
            "Action": [
                "ec2:CreateLaunchTemplate",
                "ec2:DescribeLaunchTemplates",
                "ec2:DescribeLaunchTemplateVersions"
            ],
            "Resource": "*"
        },
        {
            "Sid": "EC2SecurityGroups",
            "Effect": "Allow",
            "Action": [
                "ec2:DescribeSecurityGroups",
                "ec2:AuthorizeSecurityGroupIngress",
                "ec2:RevokeSecurityGroupIngress"
            ],
            "Resource": "*"
        },
        {
            "Sid": "ECSManagement",
            "Effect": "Allow",
            "Action": [
                "ecs:ListClusters",
                "ecs:ListServices",
                "ecs:UpdateService"
            ],
            "Resource": "*"
        },
        {
            "Sid": "CloudWatchAutoTerminate",
            "Effect": "Allow",
            "Action": [
                "cloudwatch:PutMetricAlarm",
                "cloudwatch:DeleteAlarms",
                "cloudwatch:DescribeAlarms"
            ],
            "Resource": "*"
        },
        {
            "Sid": "PricingLookup",
            "Effect": "Allow",
            "Action": [
                "pricing:GetProducts",
                "ssm:GetParameter"
            ],
            "Resource": "*"
        },
        {
            "Sid": "STSIdentity",
            "Effect": "Allow",
            "Action": [
                "sts:GetCallerIdentity"
            ],
            "Resource": "*"
        }
    ]
}
```

### Permissions by Feature

| Feature | Commands | Required Permissions |
|---------|----------|---------------------|
| **Instance Management** | `list`, `status`, `start`, `stop`, `terminate`, `type` | EC2: DescribeInstances, DescribeInstanceStatus, StartInstances, StopInstances, TerminateInstances, ModifyInstanceAttribute |
| **Instance Launch** | `launch` | EC2: RunInstances, DescribeLaunchTemplates, DescribeLaunchTemplateVersions |
| **SSH/Connect** | `connect`, `exec`, `copy`, `sync`, `forward` | EC2: DescribeInstances (to get IP) |
| **Volumes** | `volume list`, `volume resize` | EC2: DescribeVolumes, ModifyVolume |
| **Snapshots** | `snapshot create`, `snapshot list` | EC2: CreateSnapshot, DescribeSnapshots, DescribeVolumes |
| **AMIs** | `ami create`, `ami list` | EC2: CreateImage, DescribeImages |
| **Security Groups** | `sg show`, `sg allow`, `sg revoke` | EC2: DescribeSecurityGroups, AuthorizeSecurityGroupIngress, RevokeSecurityGroupIngress |
| **ECS** | `ecs list-services`, `ecs scale` | ECS: ListClusters, ListServices, UpdateService |
| **Auto-Shutdown** | `auto-shutdown enable/disable/status` | CloudWatch: PutMetricAlarm, DeleteAlarms, DescribeAlarms |
| **Cost Tracking** | `--cost` flag | Pricing: GetProducts, SSM: GetParameter |

### Minimal Policy (Instance Management Only)

For users who only need basic instance management:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ec2:DescribeInstances",
                "ec2:DescribeInstanceStatus",
                "ec2:StartInstances",
                "ec2:StopInstances"
            ],
            "Resource": "*"
        }
    ]
}
```

## Development

This project uses [uv](https://docs.astral.sh/uv/) for dependency management and requires Python 3.12+.

### Setup

```bash
# Clone the repository
git clone https://github.com/ivyleavedtoadflax/remote.py.git
cd remote.py

# Install dependencies
uv sync --dev

# Install pre-commit hooks (optional but recommended)
uv run pre-commit install
```

### Development Commands

```bash
# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov

# Code formatting and linting
uv run ruff format .      # Format code
uv run ruff check .       # Lint code
uv run ruff check . --fix # Fix linting issues

# Build package
uv build
```

### Testing

The project includes a comprehensive test suite with 780+ tests achieving high coverage:

#### Running Tests
```bash
# Run all tests
uv run pytest

# Run tests with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_config.py

# Run tests with coverage report
uv run pytest --cov --cov-report=html
```

#### Test Features
- **No AWS credentials required** - All AWS calls are mocked during testing
- **Test isolation** - Tests don't interfere with local configuration files
- **Comprehensive coverage** - 100% coverage target for core modules
- **Property-based testing** - Uses Hypothesis for edge case discovery
- **Factory pattern** - Reusable test data generation with immutable defaults
- **Defensive testing** - Validates error handling and edge cases

### Architecture

The codebase follows these principles:
- **Modular design** - Each AWS service has its own module
- **Custom exceptions** - Comprehensive error handling with user-friendly messages
- **Input validation** - Safe handling of AWS resource IDs and user input
- **Immutable patterns** - Defensive programming with bounds checking
- **Type safety** - Full type hints with mypy validation

### Contributing

Contributions are welcome! Please ensure:
1. All tests pass: `uv run pytest`
2. Code is formatted: `uv run ruff format .`
3. Linting passes: `uv run ruff check .`
4. Type checking passes: `uv run mypy .` (if mypy is installed)

### CI/CD

The project includes automated CI/CD:
- **Tests** run automatically on all pushes and pull requests
- **Code quality** checks (ruff linting/formatting)
- **Coverage reporting** with minimum thresholds
- **Manual publishing** workflow for PyPI releases

### Error Handling

The application provides user-friendly error messages for common AWS scenarios:
- Permission issues with helpful suggestions
- Invalid resource IDs with format examples
- Instance state conflicts with clear explanations
- Network and connectivity issues with troubleshooting tips
