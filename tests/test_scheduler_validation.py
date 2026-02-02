"""Tests for scheduler time/day validation functions.

These tests cover:
- Time parsing (e.g., "09:00", "9:00")
- Day parsing (e.g., "mon-fri", "mon,wed,fri")
- Cron expression building for EventBridge Scheduler
"""

import pytest

from remote.exceptions import ValidationError


class TestParseScheduleTime:
    """Tests for parse_schedule_time function."""

    def test_should_parse_time_with_leading_zero(self):
        """Should parse time like '09:00'."""
        from remote.validation import parse_schedule_time

        hour, minute = parse_schedule_time("09:00")
        assert hour == 9
        assert minute == 0

    def test_should_parse_time_without_leading_zero(self):
        """Should parse time like '9:00'."""
        from remote.validation import parse_schedule_time

        hour, minute = parse_schedule_time("9:00")
        assert hour == 9
        assert minute == 0

    def test_should_parse_midnight(self):
        """Should parse midnight as '00:00' or '0:00'."""
        from remote.validation import parse_schedule_time

        hour, minute = parse_schedule_time("00:00")
        assert hour == 0
        assert minute == 0

        hour, minute = parse_schedule_time("0:00")
        assert hour == 0
        assert minute == 0

    def test_should_parse_end_of_day(self):
        """Should parse '23:59'."""
        from remote.validation import parse_schedule_time

        hour, minute = parse_schedule_time("23:59")
        assert hour == 23
        assert minute == 59

    def test_should_parse_noon(self):
        """Should parse '12:00'."""
        from remote.validation import parse_schedule_time

        hour, minute = parse_schedule_time("12:00")
        assert hour == 12
        assert minute == 0

    def test_should_parse_with_non_zero_minutes(self):
        """Should parse times with non-zero minutes."""
        from remote.validation import parse_schedule_time

        hour, minute = parse_schedule_time("14:30")
        assert hour == 14
        assert minute == 30

        hour, minute = parse_schedule_time("8:45")
        assert hour == 8
        assert minute == 45

    def test_should_strip_whitespace(self):
        """Should handle leading/trailing whitespace."""
        from remote.validation import parse_schedule_time

        hour, minute = parse_schedule_time("  09:00  ")
        assert hour == 9
        assert minute == 0

    def test_should_reject_invalid_hour(self):
        """Should reject hours outside 0-23 range."""
        from remote.validation import parse_schedule_time

        with pytest.raises(ValidationError) as exc_info:
            parse_schedule_time("24:00")
        assert "hour" in str(exc_info.value).lower() or "time" in str(exc_info.value).lower()

        with pytest.raises(ValidationError) as exc_info:
            parse_schedule_time("25:00")
        assert "hour" in str(exc_info.value).lower() or "time" in str(exc_info.value).lower()

    def test_should_reject_invalid_minute(self):
        """Should reject minutes outside 0-59 range."""
        from remote.validation import parse_schedule_time

        with pytest.raises(ValidationError) as exc_info:
            parse_schedule_time("09:60")
        assert "minute" in str(exc_info.value).lower() or "time" in str(exc_info.value).lower()

        with pytest.raises(ValidationError) as exc_info:
            parse_schedule_time("09:99")
        assert "minute" in str(exc_info.value).lower() or "time" in str(exc_info.value).lower()

    def test_should_reject_invalid_format(self):
        """Should reject invalid time formats."""
        from remote.validation import parse_schedule_time

        invalid_times = [
            "9",  # Missing colon and minutes
            "9:0",  # Single digit minute (should this be valid?)
            "09-00",  # Wrong separator
            "09:00:00",  # Seconds not supported
            "abc",  # Not a time
            "",  # Empty string
            "   ",  # Whitespace only
            "9:0a",  # Non-numeric
        ]

        for invalid_time in invalid_times:
            with pytest.raises(ValidationError):
                parse_schedule_time(invalid_time)

    def test_should_reject_negative_values(self):
        """Should reject negative hour/minute values."""
        from remote.validation import parse_schedule_time

        with pytest.raises(ValidationError):
            parse_schedule_time("-1:00")

        with pytest.raises(ValidationError):
            parse_schedule_time("09:-30")


class TestParseScheduleDays:
    """Tests for parse_schedule_days function."""

    def test_should_parse_weekday_range(self):
        """Should parse 'mon-fri' to weekday list."""
        from remote.validation import parse_schedule_days

        days = parse_schedule_days("mon-fri")
        assert days == ["MON", "TUE", "WED", "THU", "FRI"]

    def test_should_parse_full_week(self):
        """Should parse 'sun-sat' or 'mon-sun' to all days."""
        from remote.validation import parse_schedule_days

        # Monday to Sunday
        days = parse_schedule_days("mon-sun")
        assert set(days) == {"MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"}

    def test_should_parse_comma_separated_days(self):
        """Should parse 'mon,wed,fri' to specific days."""
        from remote.validation import parse_schedule_days

        days = parse_schedule_days("mon,wed,fri")
        assert days == ["MON", "WED", "FRI"]

    def test_should_parse_single_day(self):
        """Should parse a single day."""
        from remote.validation import parse_schedule_days

        assert parse_schedule_days("mon") == ["MON"]
        assert parse_schedule_days("tue") == ["TUE"]
        assert parse_schedule_days("wed") == ["WED"]
        assert parse_schedule_days("thu") == ["THU"]
        assert parse_schedule_days("fri") == ["FRI"]
        assert parse_schedule_days("sat") == ["SAT"]
        assert parse_schedule_days("sun") == ["SUN"]

    def test_should_be_case_insensitive(self):
        """Should accept uppercase, lowercase, and mixed case."""
        from remote.validation import parse_schedule_days

        assert parse_schedule_days("MON") == ["MON"]
        assert parse_schedule_days("Mon") == ["MON"]
        assert parse_schedule_days("mon") == ["MON"]
        assert parse_schedule_days("MON-FRI") == ["MON", "TUE", "WED", "THU", "FRI"]

    def test_should_strip_whitespace(self):
        """Should handle whitespace."""
        from remote.validation import parse_schedule_days

        assert parse_schedule_days("  mon  ") == ["MON"]
        assert parse_schedule_days("mon, wed, fri") == ["MON", "WED", "FRI"]
        assert parse_schedule_days("  mon-fri  ") == ["MON", "TUE", "WED", "THU", "FRI"]

    def test_should_handle_weekend(self):
        """Should parse weekend days correctly."""
        from remote.validation import parse_schedule_days

        days = parse_schedule_days("sat,sun")
        assert days == ["SAT", "SUN"]

        days = parse_schedule_days("sat-sun")
        assert days == ["SAT", "SUN"]

    def test_should_handle_wrap_around_range(self):
        """Should handle ranges that wrap around the week (fri-mon)."""
        from remote.validation import parse_schedule_days

        days = parse_schedule_days("fri-mon")
        assert set(days) == {"FRI", "SAT", "SUN", "MON"}

    def test_should_reject_invalid_day_names(self):
        """Should reject invalid day names."""
        from remote.validation import parse_schedule_days

        invalid_days = [
            "monday",  # Full name not supported
            "m",  # Too short
            "xyz",  # Not a day
            "",  # Empty
            "   ",  # Whitespace only
        ]

        for invalid_day in invalid_days:
            with pytest.raises(ValidationError):
                parse_schedule_days(invalid_day)

    def test_should_reject_invalid_range_format(self):
        """Should reject malformed ranges."""
        from remote.validation import parse_schedule_days

        with pytest.raises(ValidationError):
            parse_schedule_days("mon-")  # Missing end

        with pytest.raises(ValidationError):
            parse_schedule_days("-fri")  # Missing start

        with pytest.raises(ValidationError):
            parse_schedule_days("mon--fri")  # Double dash

    def test_should_deduplicate_days(self):
        """Should remove duplicate days."""
        from remote.validation import parse_schedule_days

        days = parse_schedule_days("mon,mon,tue")
        assert days == ["MON", "TUE"]


class TestBuildScheduleCronExpression:
    """Tests for build_schedule_cron_expression function."""

    def test_should_build_cron_for_weekdays_morning(self):
        """Should build cron for weekday mornings."""
        from remote.validation import build_schedule_cron_expression

        # Wake at 9:00 AM on weekdays
        cron = build_schedule_cron_expression(9, 0, ["MON", "TUE", "WED", "THU", "FRI"])

        # EventBridge cron format: cron(minutes hours day-of-month month day-of-week year)
        assert cron == "cron(0 9 ? * MON,TUE,WED,THU,FRI *)"

    def test_should_build_cron_for_specific_days(self):
        """Should build cron for specific days."""
        from remote.validation import build_schedule_cron_expression

        cron = build_schedule_cron_expression(18, 30, ["MON", "WED", "FRI"])
        assert cron == "cron(30 18 ? * MON,WED,FRI *)"

    def test_should_build_cron_for_single_day(self):
        """Should build cron for a single day."""
        from remote.validation import build_schedule_cron_expression

        cron = build_schedule_cron_expression(8, 0, ["MON"])
        assert cron == "cron(0 8 ? * MON *)"

    def test_should_build_cron_for_all_days(self):
        """Should build cron for all days of the week."""
        from remote.validation import build_schedule_cron_expression

        cron = build_schedule_cron_expression(
            12, 0, ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
        )
        # Days should be sorted or in consistent order
        assert "cron(" in cron
        assert "12 0" in cron or "0 12" in cron  # minutes hours

    def test_should_handle_midnight(self):
        """Should handle midnight correctly."""
        from remote.validation import build_schedule_cron_expression

        cron = build_schedule_cron_expression(0, 0, ["MON"])
        assert cron == "cron(0 0 ? * MON *)"

    def test_should_handle_end_of_day(self):
        """Should handle 23:59."""
        from remote.validation import build_schedule_cron_expression

        cron = build_schedule_cron_expression(23, 59, ["FRI"])
        assert cron == "cron(59 23 ? * FRI *)"


class TestValidateScheduleTimeString:
    """Tests for validate_schedule_time_string function (CLI validation)."""

    def test_should_accept_valid_time_strings(self):
        """Should accept valid time strings."""
        from remote.validation import validate_schedule_time_string

        assert validate_schedule_time_string("09:00") == "09:00"
        assert validate_schedule_time_string("9:00") == "9:00"
        assert validate_schedule_time_string("14:30") == "14:30"

    def test_should_reject_invalid_time_strings(self):
        """Should raise ValidationError for invalid time strings."""
        from remote.validation import validate_schedule_time_string

        with pytest.raises(ValidationError):
            validate_schedule_time_string("25:00")

        with pytest.raises(ValidationError):
            validate_schedule_time_string("invalid")


class TestValidateScheduleDaysString:
    """Tests for validate_schedule_days_string function (CLI validation)."""

    def test_should_accept_valid_days_strings(self):
        """Should accept valid days strings."""
        from remote.validation import validate_schedule_days_string

        assert validate_schedule_days_string("mon-fri") == "mon-fri"
        assert validate_schedule_days_string("mon,wed,fri") == "mon,wed,fri"
        assert validate_schedule_days_string("sat") == "sat"

    def test_should_reject_invalid_days_strings(self):
        """Should raise ValidationError for invalid days strings."""
        from remote.validation import validate_schedule_days_string

        with pytest.raises(ValidationError):
            validate_schedule_days_string("monday")

        with pytest.raises(ValidationError):
            validate_schedule_days_string("invalid")


class TestParseScheduleDate:
    """Tests for parse_schedule_date function (one-time schedules)."""

    def test_should_parse_today(self, mocker):
        """Should parse 'today' as today's date."""
        from datetime import date

        from remote.validation import parse_schedule_date

        mock_date = mocker.patch("remote.validation.date")
        mock_date.today.return_value = date(2026, 2, 2)
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)

        result = parse_schedule_date("today")
        assert result == date(2026, 2, 2)

    def test_should_parse_tomorrow(self, mocker):
        """Should parse 'tomorrow' as the next day."""
        from datetime import date

        from remote.validation import parse_schedule_date

        # Mock today as 2026-02-02
        mock_date = mocker.patch("remote.validation.date")
        mock_date.today.return_value = date(2026, 2, 2)
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)

        result = parse_schedule_date("tomorrow")
        assert result == date(2026, 2, 3)

    def test_should_parse_day_name_for_future_day(self, mocker):
        """Should parse day name as next occurrence."""
        from datetime import date

        from remote.validation import parse_schedule_date

        # Mock today as Monday 2026-02-02
        mock_date = mocker.patch("remote.validation.date")
        mock_date.today.return_value = date(2026, 2, 2)  # Monday
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)

        # Tuesday should be tomorrow (Feb 3)
        result = parse_schedule_date("tuesday")
        assert result == date(2026, 2, 3)

        # Wednesday should be Feb 4
        result = parse_schedule_date("wednesday")
        assert result == date(2026, 2, 4)

    def test_should_parse_day_name_for_same_day_as_next_week(self, mocker):
        """Should parse same day name as next week."""
        from datetime import date

        from remote.validation import parse_schedule_date

        # Mock today as Monday 2026-02-02
        mock_date = mocker.patch("remote.validation.date")
        mock_date.today.return_value = date(2026, 2, 2)  # Monday
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)

        # Monday should be next Monday (Feb 9)
        result = parse_schedule_date("monday")
        assert result == date(2026, 2, 9)

    def test_should_parse_iso_date_format(self):
        """Should parse ISO date format YYYY-MM-DD."""
        from datetime import date

        from remote.validation import parse_schedule_date

        result = parse_schedule_date("2026-02-15")
        assert result == date(2026, 2, 15)

    def test_should_parse_short_day_names(self, mocker):
        """Should parse short day names like 'tue'."""
        from datetime import date

        from remote.validation import parse_schedule_date

        mock_date = mocker.patch("remote.validation.date")
        mock_date.today.return_value = date(2026, 2, 2)  # Monday
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)

        result = parse_schedule_date("tue")
        assert result == date(2026, 2, 3)

    def test_should_reject_past_dates(self, mocker):
        """Should reject dates in the past."""
        from datetime import date

        from remote.validation import parse_schedule_date

        mock_date = mocker.patch("remote.validation.date")
        mock_date.today.return_value = date(2026, 2, 2)
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)

        with pytest.raises(ValidationError):
            parse_schedule_date("2026-02-01")  # Yesterday

    def test_should_reject_invalid_date_strings(self):
        """Should reject invalid date strings."""
        from remote.validation import parse_schedule_date

        invalid_dates = ["invalid", "2026-13-01", "not-a-date", ""]

        for invalid_date in invalid_dates:
            with pytest.raises(ValidationError):
                parse_schedule_date(invalid_date)


class TestBuildScheduleAtExpression:
    """Tests for build_schedule_at_expression function (one-time schedules)."""

    def test_should_build_at_expression(self):
        """Should build at() expression for one-time schedule."""
        from datetime import date

        from remote.validation import build_schedule_at_expression

        result = build_schedule_at_expression(date(2026, 2, 15), 9, 30)
        assert result == "at(2026-02-15T09:30:00)"

    def test_should_handle_midnight(self):
        """Should handle midnight correctly."""
        from datetime import date

        from remote.validation import build_schedule_at_expression

        result = build_schedule_at_expression(date(2026, 2, 15), 0, 0)
        assert result == "at(2026-02-15T00:00:00)"

    def test_should_handle_end_of_day(self):
        """Should handle 23:59."""
        from datetime import date

        from remote.validation import build_schedule_at_expression

        result = build_schedule_at_expression(date(2026, 2, 15), 23, 59)
        assert result == "at(2026-02-15T23:59:00)"
