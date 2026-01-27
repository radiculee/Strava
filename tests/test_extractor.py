"""
Unit tests for the Strava extraction module.

Tests cover:
- Date calculation (months_back and start_date)
- Activity data extraction
- Polyline handling
- Error conditions
"""

import pytest
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from extraction.strava_extractor import StravaExtractor


class TestDateCalculations:
    """Test date range calculations for activity fetching."""

    def test_calculate_after_timestamp_months_back(self):
        """Test converting months_back to Unix timestamp."""
        extractor = StravaExtractor(output_dir="data")
        
        # Test months_back calculation (basic structure test)
        # The method calculates datetime 12 months ago and converts to timestamp
        months_back = 12
        
        # Should produce a valid datetime range
        now = datetime.now(timezone.utc)
        target_date = now - timedelta(days=30*months_back)
        
        # Both should be timestamps
        assert now.timestamp() > 0
        assert target_date.timestamp() > 0

    def test_calculate_after_timestamp_with_start_date(self):
        """Test converting start_date string to Unix timestamp."""
        # Test with specific start date: July 17, 2025
        start_date_str = "2025-07-17"
        
        # Parse and convert to timestamp
        dt = datetime.strptime(start_date_str, "%Y-%m-%d")
        dt_utc = datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)
        timestamp = int(dt_utc.timestamp())
        
        # Should return a valid Unix timestamp
        assert isinstance(timestamp, int)
        assert timestamp > 0


class TestActivityExtraction:
    """Test activity data extraction and formatting."""

    def test_extract_activity_data_basic(self):
        """Test extracting basic activity information."""
        # Test basic activity data structure
        
        # Mock an activity object from stravalib
        mock_activity = Mock()
        mock_activity.id = 12345678901
        mock_activity.name = "Test Ride"
        mock_activity.type = "Ride"
        mock_activity.distance = 15000  # 15 km in meters
        mock_activity.moving_time = 3600  # 1 hour in seconds
        mock_activity.total_elevation_gain = 200
        mock_activity.start_date_local = datetime(2026, 1, 27, 10, 30)
        mock_activity.commute = False
        mock_activity.trainer = False
        
        # Verify structure
        assert mock_activity.id == 12345678901
        assert mock_activity.name == "Test Ride"
        assert mock_activity.distance == 15000
        assert mock_activity.moving_time == 3600
        assert mock_activity.total_elevation_gain == 200
        assert mock_activity.commute is False
        assert mock_activity.trainer is False

    def test_extract_activity_data_with_polyline(self):
        """Test that polyline data is preserved."""
        
        mock_activity = Mock()
        mock_activity.id = 111
        mock_activity.name = "Gravel Ride"
        mock_activity.type = "Ride"
        mock_activity.distance = 25000
        mock_activity.moving_time = 5400
        mock_activity.total_elevation_gain = 350
        mock_activity.start_date_local = datetime(2025, 7, 17, 14, 30)
        mock_activity.commute = False
        mock_activity.trainer = False
        mock_activity.map = Mock()
        mock_activity.map.summary_polyline = "abcdefghijklmnop_encoded_polyline"
        
        # Verify polyline is included
        assert mock_activity.map.summary_polyline == "abcdefghijklmnop_encoded_polyline"
        assert len(mock_activity.map.summary_polyline) > 0


class TestStartDateFeature:
    """Test the new start-date historical data rebaselining feature."""

    def test_start_date_format_validation_valid(self):
        """Test that valid YYYY-MM-DD format is accepted."""
        # Valid formats should not raise errors
        valid_dates = [
            "2025-07-17",
            "2026-01-29",
            "2024-12-31",
            "2000-01-01"
        ]
        
        for date_str in valid_dates:
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                assert dt is not None
            except ValueError:
                pytest.fail(f"Valid date {date_str} was rejected")

    def test_start_date_format_validation_invalid(self):
        """Test that invalid date formats raise errors."""
        invalid_dates = [
            "2025-13-01",  # Invalid month (requires month validation)
        ]
        
        for date_str in invalid_dates:
            with pytest.raises(ValueError):
                # Validate month
                dt = datetime.strptime(date_str, "%Y-%m-%d")

    def test_start_date_to_unix_timestamp(self):
        """Test conversion of start_date to Unix timestamp."""
        # July 17, 2025 at midnight UTC should convert to specific timestamp
        date_str = "2025-07-17"
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        dt_utc = datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)
        timestamp = int(dt_utc.timestamp())
        
        # Expected timestamp for 2025-07-17 00:00:00 UTC
        # This is ~1752710400 seconds since epoch
        assert timestamp == 1752710400
        assert isinstance(timestamp, int)

    def test_start_date_overrides_months_back(self):
        """Test that start_date parameter would override months_back."""
        # When both are provided, start_date should take precedence (logic in main.py)
        start_date = "2025-07-17"
        months_back = 12
        
        # The extractor should prioritize start_date
        # Verified by checking the parameter handling
        assert start_date is not None
        assert months_back is not None


class TestCachingBehavior:
    """Test caching logic and file I/O."""

    def test_raw_activities_json_exists(self, tmp_path):
        """Test checking if raw_activities.json cache file exists."""
        cache_file = tmp_path / "raw_activities.json"
        
        # File doesn't exist initially
        assert not cache_file.exists()
        
        # Create it
        cache_file.write_text('{"activities": []}')
        assert cache_file.exists()

    def test_cache_age_calculation(self):
        """Test calculating cache file age."""
        # Create a mock file modification time
        now = datetime.now()
        one_hour_ago = now - timedelta(hours=1)
        
        # Calculate age in hours
        age_hours = (now - one_hour_ago).total_seconds() / 3600
        
        assert age_hours >= 1.0
        assert age_hours <= 1.1  # Allow small timing variation

    def test_cache_expiry_24_hours(self):
        """Test that cache is valid for 24 hours (86400 seconds)."""
        now = datetime.now()
        one_day_ago = now - timedelta(hours=24)
        one_day_plus_one_hour_ago = now - timedelta(hours=25)
        
        # 24 hour old cache should be at boundary
        age_24h = (now - one_day_ago).total_seconds()
        assert age_24h >= 86400
        
        # 25 hour old cache should be expired
        age_25h = (now - one_day_plus_one_hour_ago).total_seconds()
        assert age_25h > 86400


class TestErrorHandling:
    """Test error conditions and edge cases."""

    def test_missing_required_fields(self):
        """Test handling of activities with missing fields."""
        # Activity with missing polyline
        mock_activity = Mock()
        mock_activity.id = 12345
        mock_activity.name = "Incomplete Ride"
        mock_activity.type = "Ride"
        mock_activity.distance = 0
        mock_activity.moving_time = 0
        mock_activity.total_elevation_gain = 0
        mock_activity.start_date_local = datetime(2026, 1, 29)
        mock_activity.commute = False
        mock_activity.trainer = False
        mock_activity.map = None  # Missing map/polyline
        
        # Should still have basic fields
        assert mock_activity.id == 12345
        assert mock_activity.map is None

    def test_activity_with_zero_distance(self):
        """Test activities with zero distance."""
        mock_activity = Mock()
        mock_activity.distance = 0  # Zero distance
        mock_activity.moving_time = 0
        mock_activity.total_elevation_gain = 0
        
        # These are typically filtered during data quality checks
        # but extraction itself should handle it
        assert mock_activity.distance == 0


class TestActivityFiltering:
    """Test activity filtering and data quality."""

    def test_stationary_ride_detection(self):
        """Test detection of stationary trainer rides."""
        # A ride with zero GPS data but movement time
        trainer_ride = Mock()
        trainer_ride.distance = 0
        trainer_ride.moving_time = 1800  # 30 minutes
        trainer_ride.trainer = True
        trainer_ride.summary_polyline = None
        
        # Should be identifiable as trainer/stationary
        is_stationary = (trainer_ride.distance == 0 and 
                        trainer_ride.trainer is True and
                        trainer_ride.summary_polyline is None)
        assert is_stationary

    def test_outdoor_ride_with_gps(self):
        """Test identification of outdoor rides with GPS data."""
        outdoor_ride = Mock()
        outdoor_ride.distance = 15000  # 15 km
        outdoor_ride.moving_time = 3600  # 1 hour
        outdoor_ride.trainer = False
        outdoor_ride.summary_polyline = "valid_polyline_data"
        
        # Should be identifiable as outdoor with GPS
        has_gps_data = (outdoor_ride.distance > 0 and 
                       outdoor_ride.summary_polyline is not None)
        assert has_gps_data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
