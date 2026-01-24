"""Tracking module for cumulative instance usage and costs.

This module provides persistence for instance usage tracking, including:
- Start/stop session recording
- Cumulative uptime and cost calculation
- Historical session data
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from remote.settings import SECONDS_PER_HOUR, Settings

logger = logging.getLogger(__name__)

# Default tracking file path
TRACKING_FILE_NAME = "tracking.json"


def get_tracking_file_path() -> Path:
    """Get the path to the tracking JSON file.

    Returns:
        Path to ~/.config/remote.py/tracking.json
    """
    config_dir = Settings.get_config_path().parent
    return config_dir / TRACKING_FILE_NAME


@dataclass
class UsageSession:
    """Represents a single usage session for an instance.

    A session tracks the time period when an instance was running,
    from start to stop.
    """

    start: str  # ISO format timestamp
    stop: str | None = None  # ISO format timestamp, None if still running
    hours: float = 0.0
    cost: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert session to dictionary for JSON serialization."""
        return {
            "start": self.start,
            "stop": self.stop,
            "hours": self.hours,
            "cost": self.cost,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UsageSession":
        """Create a UsageSession from a dictionary."""
        return cls(
            start=data.get("start", ""),
            stop=data.get("stop"),
            hours=data.get("hours", 0.0),
            cost=data.get("cost", 0.0),
        )


@dataclass
class InstanceTracking:
    """Tracking data for a single EC2 instance."""

    instance_id: str
    name: str | None = None
    sessions: list[UsageSession] = field(default_factory=list)
    total_hours: float = 0.0
    total_cost: float = 0.0
    last_updated: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert instance tracking to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "sessions": [s.to_dict() for s in self.sessions],
            "total_hours": self.total_hours,
            "total_cost": self.total_cost,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, instance_id: str, data: dict[str, Any]) -> "InstanceTracking":
        """Create an InstanceTracking from a dictionary."""
        sessions = [UsageSession.from_dict(s) for s in data.get("sessions", [])]
        return cls(
            instance_id=instance_id,
            name=data.get("name"),
            sessions=sessions,
            total_hours=data.get("total_hours", 0.0),
            total_cost=data.get("total_cost", 0.0),
            last_updated=data.get("last_updated"),
        )

    def recalculate_totals(self) -> None:
        """Recalculate total hours and cost from all sessions."""
        self.total_hours = sum(s.hours for s in self.sessions)
        self.total_cost = sum(s.cost for s in self.sessions)

    def get_active_session(self) -> UsageSession | None:
        """Get the currently active (not stopped) session, if any."""
        for session in self.sessions:
            if session.stop is None:
                return session
        return None


class TrackingManager:
    """Manager for instance usage tracking persistence.

    This class handles reading and writing the tracking.json file,
    which stores cumulative usage data for EC2 instances.
    """

    def __init__(self, tracking_file: Path | None = None) -> None:
        """Initialize the tracking manager.

        Args:
            tracking_file: Path to the tracking file. Defaults to
                ~/.config/remote.py/tracking.json
        """
        self._tracking_file = tracking_file or get_tracking_file_path()
        self._data: dict[str, InstanceTracking] = {}
        self._loaded = False

    @property
    def tracking_file(self) -> Path:
        """Get the tracking file path."""
        return self._tracking_file

    def _ensure_config_dir(self) -> None:
        """Ensure the config directory exists."""
        config_dir = self._tracking_file.parent
        if not config_dir.exists():
            config_dir.mkdir(parents=True)
            logger.debug(f"Created config directory: {config_dir}")

    def _load(self) -> None:
        """Load tracking data from file."""
        if self._loaded:
            return

        self._data = {}
        if self._tracking_file.exists():
            try:
                with open(self._tracking_file) as f:
                    raw_data = json.load(f)

                instances_data = raw_data.get("instances", {})
                for instance_id, instance_data in instances_data.items():
                    self._data[instance_id] = InstanceTracking.from_dict(instance_id, instance_data)
                logger.debug(f"Loaded tracking data for {len(self._data)} instances")
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Could not load tracking data: {e}")
                self._data = {}

        self._loaded = True

    def _save(self) -> None:
        """Save tracking data to file."""
        self._ensure_config_dir()

        data = {
            "instances": {
                instance_id: tracking.to_dict() for instance_id, tracking in self._data.items()
            }
        }

        try:
            with open(self._tracking_file, "w") as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved tracking data for {len(self._data)} instances")
        except OSError as e:
            logger.warning(f"Could not save tracking data: {e}")

    def reload(self) -> None:
        """Force reload tracking data from file."""
        self._loaded = False
        self._load()

    def get_instance_tracking(self, instance_id: str) -> InstanceTracking | None:
        """Get tracking data for a specific instance.

        Args:
            instance_id: The EC2 instance ID

        Returns:
            InstanceTracking data, or None if not tracked
        """
        self._load()
        return self._data.get(instance_id)

    def get_all_tracking(self) -> dict[str, InstanceTracking]:
        """Get tracking data for all instances.

        Returns:
            Dictionary mapping instance IDs to their tracking data
        """
        self._load()
        return self._data.copy()

    def record_start(self, instance_id: str, instance_name: str | None = None) -> UsageSession:
        """Record an instance start event.

        If there's already an active session (no stop time), this will
        complete that session first before starting a new one.

        Args:
            instance_id: The EC2 instance ID
            instance_name: Optional instance name

        Returns:
            The newly created UsageSession
        """
        self._load()

        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        # Get or create instance tracking
        if instance_id not in self._data:
            self._data[instance_id] = InstanceTracking(
                instance_id=instance_id,
                name=instance_name,
            )

        tracking = self._data[instance_id]

        # Update name if provided
        if instance_name:
            tracking.name = instance_name

        # Check for existing active session and close it
        active_session = tracking.get_active_session()
        if active_session:
            logger.debug(
                f"Closing orphaned active session for {instance_id} started at {active_session.start}"
            )
            # Close the orphaned session with current time
            active_session.stop = now_iso
            start_dt = datetime.fromisoformat(active_session.start)
            duration_seconds = (now - start_dt).total_seconds()
            active_session.hours = duration_seconds / SECONDS_PER_HOUR

        # Create new session
        new_session = UsageSession(start=now_iso)
        tracking.sessions.append(new_session)
        tracking.last_updated = now_iso
        tracking.recalculate_totals()

        self._save()
        logger.debug(f"Recorded start for instance {instance_id}")

        return new_session

    def record_stop(
        self,
        instance_id: str,
        hourly_price: float | None = None,
        instance_name: str | None = None,
    ) -> UsageSession | None:
        """Record an instance stop event.

        Completes the active session with stop time and calculates
        duration and cost.

        Args:
            instance_id: The EC2 instance ID
            hourly_price: Optional hourly price for cost calculation
            instance_name: Optional instance name to update

        Returns:
            The completed UsageSession, or None if no active session
        """
        self._load()

        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        tracking = self._data.get(instance_id)
        if not tracking:
            logger.debug(f"No tracking data for instance {instance_id}")
            return None

        # Update name if provided
        if instance_name:
            tracking.name = instance_name

        # Find active session
        active_session = tracking.get_active_session()
        if not active_session:
            logger.debug(f"No active session for instance {instance_id}")
            return None

        # Complete the session
        active_session.stop = now_iso
        start_dt = datetime.fromisoformat(active_session.start)
        duration_seconds = (now - start_dt).total_seconds()
        active_session.hours = duration_seconds / SECONDS_PER_HOUR

        # Calculate cost if price provided
        if hourly_price is not None and hourly_price > 0:
            active_session.cost = active_session.hours * hourly_price

        # Update tracking totals
        tracking.last_updated = now_iso
        tracking.recalculate_totals()

        self._save()
        logger.debug(f"Recorded stop for instance {instance_id}: {active_session.hours:.2f} hours")

        return active_session

    def get_lifetime_stats(self, instance_id: str) -> tuple[float, float, int] | None:
        """Get lifetime statistics for an instance.

        Args:
            instance_id: The EC2 instance ID

        Returns:
            Tuple of (total_hours, total_cost, session_count) or None if not tracked
        """
        self._load()

        tracking = self._data.get(instance_id)
        if not tracking:
            return None

        return (tracking.total_hours, tracking.total_cost, len(tracking.sessions))

    def clear_instance_tracking(self, instance_id: str) -> bool:
        """Clear all tracking data for an instance.

        Args:
            instance_id: The EC2 instance ID

        Returns:
            True if tracking was cleared, False if instance was not tracked
        """
        self._load()

        if instance_id not in self._data:
            return False

        del self._data[instance_id]
        self._save()
        logger.debug(f"Cleared tracking data for instance {instance_id}")
        return True

    def clear_all_tracking(self) -> int:
        """Clear all tracking data.

        Returns:
            Number of instances cleared
        """
        self._load()
        count = len(self._data)
        self._data = {}
        self._save()
        logger.debug(f"Cleared tracking data for {count} instances")
        return count


# Global tracking manager instance
tracking_manager = TrackingManager()
