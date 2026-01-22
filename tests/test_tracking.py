"""Tests for the tracking module."""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from remote.tracking import (
    InstanceTracking,
    TrackingManager,
    UsageSession,
    get_tracking_file_path,
)


class TestUsageSession:
    """Tests for UsageSession dataclass."""

    def test_to_dict(self):
        """Test converting session to dictionary."""
        session = UsageSession(
            start="2026-01-20T10:00:00+00:00",
            stop="2026-01-20T18:00:00+00:00",
            hours=8.0,
            cost=0.80,
        )
        result = session.to_dict()

        assert result["start"] == "2026-01-20T10:00:00+00:00"
        assert result["stop"] == "2026-01-20T18:00:00+00:00"
        assert result["hours"] == 8.0
        assert result["cost"] == 0.80

    def test_from_dict(self):
        """Test creating session from dictionary."""
        data = {
            "start": "2026-01-20T10:00:00+00:00",
            "stop": "2026-01-20T18:00:00+00:00",
            "hours": 8.0,
            "cost": 0.80,
        }
        session = UsageSession.from_dict(data)

        assert session.start == "2026-01-20T10:00:00+00:00"
        assert session.stop == "2026-01-20T18:00:00+00:00"
        assert session.hours == 8.0
        assert session.cost == 0.80

    def test_from_dict_missing_fields(self):
        """Test creating session from dictionary with missing fields."""
        data = {"start": "2026-01-20T10:00:00+00:00"}
        session = UsageSession.from_dict(data)

        assert session.start == "2026-01-20T10:00:00+00:00"
        assert session.stop is None
        assert session.hours == 0.0
        assert session.cost == 0.0

    def test_active_session_no_stop(self):
        """Test that session without stop is considered active."""
        session = UsageSession(start="2026-01-20T10:00:00+00:00")
        assert session.stop is None


class TestInstanceTracking:
    """Tests for InstanceTracking dataclass."""

    def test_to_dict(self):
        """Test converting instance tracking to dictionary."""
        session = UsageSession(
            start="2026-01-20T10:00:00+00:00",
            stop="2026-01-20T18:00:00+00:00",
            hours=8.0,
            cost=0.80,
        )
        tracking = InstanceTracking(
            instance_id="i-abc123",
            name="my-server",
            sessions=[session],
            total_hours=8.0,
            total_cost=0.80,
            last_updated="2026-01-20T18:00:00+00:00",
        )
        result = tracking.to_dict()

        assert result["name"] == "my-server"
        assert len(result["sessions"]) == 1
        assert result["total_hours"] == 8.0
        assert result["total_cost"] == 0.80
        assert result["last_updated"] == "2026-01-20T18:00:00+00:00"

    def test_from_dict(self):
        """Test creating instance tracking from dictionary."""
        data = {
            "name": "my-server",
            "sessions": [
                {
                    "start": "2026-01-20T10:00:00+00:00",
                    "stop": "2026-01-20T18:00:00+00:00",
                    "hours": 8.0,
                    "cost": 0.80,
                }
            ],
            "total_hours": 8.0,
            "total_cost": 0.80,
            "last_updated": "2026-01-20T18:00:00+00:00",
        }
        tracking = InstanceTracking.from_dict("i-abc123", data)

        assert tracking.instance_id == "i-abc123"
        assert tracking.name == "my-server"
        assert len(tracking.sessions) == 1
        assert tracking.total_hours == 8.0
        assert tracking.total_cost == 0.80

    def test_recalculate_totals(self):
        """Test recalculating totals from sessions."""
        sessions = [
            UsageSession(start="", stop="", hours=4.0, cost=0.40),
            UsageSession(start="", stop="", hours=6.0, cost=0.60),
        ]
        tracking = InstanceTracking(
            instance_id="i-abc123",
            sessions=sessions,
            total_hours=0.0,
            total_cost=0.0,
        )
        tracking.recalculate_totals()

        assert tracking.total_hours == 10.0
        assert tracking.total_cost == 1.00

    def test_get_active_session(self):
        """Test finding an active session."""
        sessions = [
            UsageSession(start="", stop="2026-01-20T18:00:00+00:00", hours=8.0, cost=0.80),
            UsageSession(start="2026-01-20T19:00:00+00:00", stop=None),
        ]
        tracking = InstanceTracking(instance_id="i-abc123", sessions=sessions)

        active = tracking.get_active_session()
        assert active is not None
        assert active.start == "2026-01-20T19:00:00+00:00"

    def test_get_active_session_none(self):
        """Test when no active session exists."""
        sessions = [
            UsageSession(start="", stop="2026-01-20T18:00:00+00:00", hours=8.0, cost=0.80),
        ]
        tracking = InstanceTracking(instance_id="i-abc123", sessions=sessions)

        active = tracking.get_active_session()
        assert active is None


class TestTrackingManager:
    """Tests for TrackingManager class."""

    @pytest.fixture
    def tracking_file(self, tmp_path):
        """Create a temporary tracking file path."""
        return tmp_path / "tracking.json"

    @pytest.fixture
    def manager(self, tracking_file):
        """Create a TrackingManager with a temporary file."""
        return TrackingManager(tracking_file)

    def test_init_default_path(self):
        """Test that default path is set correctly."""
        manager = TrackingManager()
        assert manager.tracking_file == get_tracking_file_path()

    def test_init_custom_path(self, tracking_file):
        """Test that custom path is used."""
        manager = TrackingManager(tracking_file)
        assert manager.tracking_file == tracking_file

    def test_load_empty_file(self, manager):
        """Test loading when file doesn't exist."""
        result = manager.get_all_tracking()
        assert result == {}

    def test_load_existing_file(self, tracking_file):
        """Test loading from existing file."""
        data = {
            "instances": {
                "i-abc123": {
                    "name": "my-server",
                    "sessions": [],
                    "total_hours": 10.0,
                    "total_cost": 1.00,
                    "last_updated": None,
                }
            }
        }
        with open(tracking_file, "w") as f:
            json.dump(data, f)

        manager = TrackingManager(tracking_file)
        result = manager.get_all_tracking()

        assert "i-abc123" in result
        assert result["i-abc123"].name == "my-server"
        assert result["i-abc123"].total_hours == 10.0

    def test_record_start_new_instance(self, manager):
        """Test recording start for a new instance."""
        session = manager.record_start("i-abc123", "my-server")

        assert session is not None
        assert session.stop is None

        tracking = manager.get_instance_tracking("i-abc123")
        assert tracking is not None
        assert tracking.name == "my-server"
        assert len(tracking.sessions) == 1

    def test_record_start_existing_instance(self, manager):
        """Test recording start for existing instance creates new session."""
        manager.record_start("i-abc123", "my-server")
        # Complete the first session
        manager.record_stop("i-abc123", hourly_price=0.10)
        # Start new session
        manager.record_start("i-abc123")

        tracking = manager.get_instance_tracking("i-abc123")
        assert len(tracking.sessions) == 2

    def test_record_start_closes_orphan_session(self, manager):
        """Test that starting closes any orphaned active session."""
        # Start first session but don't stop
        manager.record_start("i-abc123", "my-server")

        # Start again - should close the orphan
        manager.record_start("i-abc123")

        tracking = manager.get_instance_tracking("i-abc123")
        # Should have 2 sessions - first one closed, second one active
        assert len(tracking.sessions) == 2
        assert tracking.sessions[0].stop is not None
        assert tracking.sessions[1].stop is None

    def test_record_stop(self, manager):
        """Test recording stop for an active session."""
        manager.record_start("i-abc123", "my-server")
        session = manager.record_stop("i-abc123", hourly_price=0.10)

        assert session is not None
        assert session.stop is not None
        assert session.hours > 0

        tracking = manager.get_instance_tracking("i-abc123")
        assert tracking.total_hours > 0

    def test_record_stop_with_cost(self, manager):
        """Test that stop calculates cost based on hourly price."""
        # We need to mock time to get predictable cost
        start_time = datetime.now(timezone.utc)
        stop_time = start_time + timedelta(hours=2)

        with patch("remote.tracking.datetime") as mock_datetime:
            mock_datetime.now.return_value = start_time
            mock_datetime.fromisoformat = datetime.fromisoformat
            manager.record_start("i-abc123")

            mock_datetime.now.return_value = stop_time
            session = manager.record_stop("i-abc123", hourly_price=0.10)

        # 2 hours at $0.10/hr = $0.20
        assert session is not None
        assert session.hours == pytest.approx(2.0, rel=0.01)
        assert session.cost == pytest.approx(0.20, rel=0.01)

    def test_record_stop_no_active_session(self, manager):
        """Test that stop returns None when no active session."""
        result = manager.record_stop("i-abc123")
        assert result is None

    def test_record_stop_unknown_instance(self, manager):
        """Test that stop returns None for unknown instance."""
        result = manager.record_stop("i-unknown")
        assert result is None

    def test_get_lifetime_stats(self, manager):
        """Test getting lifetime statistics."""
        # Create two completed sessions
        manager.record_start("i-abc123", "my-server")
        manager.record_stop("i-abc123", hourly_price=0.10)
        manager.record_start("i-abc123")
        manager.record_stop("i-abc123", hourly_price=0.10)

        stats = manager.get_lifetime_stats("i-abc123")
        assert stats is not None
        total_hours, total_cost, session_count = stats
        assert session_count == 2
        assert total_hours > 0
        assert total_cost > 0

    def test_get_lifetime_stats_unknown(self, manager):
        """Test getting stats for unknown instance."""
        result = manager.get_lifetime_stats("i-unknown")
        assert result is None

    def test_clear_instance_tracking(self, manager):
        """Test clearing tracking for specific instance."""
        manager.record_start("i-abc123", "my-server")
        manager.record_start("i-def456", "other-server")

        result = manager.clear_instance_tracking("i-abc123")
        assert result is True

        assert manager.get_instance_tracking("i-abc123") is None
        assert manager.get_instance_tracking("i-def456") is not None

    def test_clear_instance_tracking_unknown(self, manager):
        """Test clearing unknown instance returns False."""
        result = manager.clear_instance_tracking("i-unknown")
        assert result is False

    def test_clear_all_tracking(self, manager):
        """Test clearing all tracking data."""
        manager.record_start("i-abc123", "my-server")
        manager.record_start("i-def456", "other-server")

        count = manager.clear_all_tracking()
        assert count == 2

        assert manager.get_all_tracking() == {}

    def test_reload(self, tracking_file, manager):
        """Test reloading data from file."""
        manager.record_start("i-abc123")

        # Modify file externally
        data = {
            "instances": {
                "i-new123": {
                    "name": "new-server",
                    "sessions": [],
                    "total_hours": 5.0,
                    "total_cost": 0.50,
                    "last_updated": None,
                }
            }
        }
        with open(tracking_file, "w") as f:
            json.dump(data, f)

        manager.reload()
        result = manager.get_all_tracking()

        assert "i-new123" in result
        assert "i-abc123" not in result

    def test_save_creates_directory(self, tmp_path):
        """Test that save creates config directory if needed."""
        nested_path = tmp_path / "subdir" / "tracking.json"
        manager = TrackingManager(nested_path)

        manager.record_start("i-abc123")

        assert nested_path.exists()

    def test_corrupted_file_handled(self, tracking_file):
        """Test that corrupted JSON file is handled gracefully."""
        with open(tracking_file, "w") as f:
            f.write("not valid json {{{")

        manager = TrackingManager(tracking_file)
        result = manager.get_all_tracking()

        # Should return empty dict instead of crashing
        assert result == {}


class TestGetTrackingFilePath:
    """Tests for get_tracking_file_path function."""

    def test_returns_path_in_config_dir(self):
        """Test that tracking file is in the config directory."""
        path = get_tracking_file_path()
        assert path.name == "tracking.json"
        assert "remote.py" in str(path.parent)
