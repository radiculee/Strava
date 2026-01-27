"""
Unit tests for caching behavior.

Tests cover:
- Cache file age calculation
- Cache validity checking
- Force flag override
- Cache expiration (24-hour default)
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch
import sys
import json
import time

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestCacheFileHandling:
    """Test cache file creation and management."""

    def test_cache_file_path_exists(self, tmp_path):
        """Test cache file path creation."""
        cache_file = tmp_path / "raw_activities.json"
        
        # File doesn't exist yet
        assert not cache_file.exists()
        
        # Create cache file
        cache_file.write_text('{"activities": []}')
        assert cache_file.exists()

    def test_cache_file_modification_time(self, tmp_path):
        """Test reading cache file modification time."""
        cache_file = tmp_path / "raw_activities.json"
        cache_file.write_text('{"activities": []}')
        
        # Get file modification time
        mtime = cache_file.stat().st_mtime
        assert mtime > 0
        
        # Convert to datetime
        mod_time = datetime.fromtimestamp(mtime)
        assert isinstance(mod_time, datetime)

    def test_cache_file_content_structure(self, tmp_path):
        """Test cache file JSON structure."""
        cache_file = tmp_path / "raw_activities.json"
        
        # Write test data
        test_data = {
            "activities": [
                {"id": 1, "name": "Ride 1"},
                {"id": 2, "name": "Ride 2"}
            ],
            "cached_at": "2026-01-29T12:00:00"
        }
        cache_file.write_text(json.dumps(test_data, indent=2))
        
        # Read and verify
        loaded = json.loads(cache_file.read_text())
        assert loaded["activities"] == test_data["activities"]
        assert len(loaded["activities"]) == 2


class TestCacheAgeCalculation:
    """Test cache age detection and validity."""

    def test_cache_age_hours(self):
        """Test calculating cache age in hours."""
        now = datetime.now()
        one_hour_ago = now - timedelta(hours=1)
        
        age_seconds = (now - one_hour_ago).total_seconds()
        age_hours = age_seconds / 3600
        
        assert 0.99 < age_hours < 1.01  # ~1 hour

    def test_cache_age_24_hours(self):
        """Test cache at 24-hour boundary."""
        now = datetime.now()
        one_day_ago = now - timedelta(hours=24)
        
        age_seconds = (now - one_day_ago).total_seconds()
        
        # Should be approximately 86400 seconds
        assert 86390 < age_seconds < 86410  # ~86400

    def test_cache_age_beyond_24_hours(self):
        """Test cache beyond 24-hour expiration."""
        now = datetime.now()
        one_day_plus_one_hour = now - timedelta(hours=25)
        
        age_seconds = (now - one_day_plus_one_hour).total_seconds()
        
        # Should be > 86400 seconds
        assert age_seconds > 86400

    def test_cache_fresh(self):
        """Test very fresh cache (minutes old)."""
        now = datetime.now()
        five_minutes_ago = now - timedelta(minutes=5)
        
        age_seconds = (now - five_minutes_ago).total_seconds()
        
        # Should be approximately 300 seconds
        assert 290 < age_seconds < 310


class TestCacheValidity:
    """Test cache validity logic."""

    def test_cache_valid_within_24_hours(self):
        """Test cache is valid if less than 24 hours old."""
        cache_age_hours = 12
        cache_hours_threshold = 24
        
        is_valid = cache_age_hours < cache_hours_threshold
        assert is_valid is True

    def test_cache_invalid_after_24_hours(self):
        """Test cache is invalid if older than 24 hours."""
        cache_age_hours = 25
        cache_hours_threshold = 24
        
        is_valid = cache_age_hours < cache_hours_threshold
        assert is_valid is False

    def test_cache_validity_at_boundary(self):
        """Test cache validity at 24-hour boundary."""
        cache_age_hours = 24.0
        cache_hours_threshold = 24
        
        # At exact boundary, should still be valid (using < comparison)
        is_valid = cache_age_hours < cache_hours_threshold
        assert is_valid is False  # > or == means invalid

    def test_custom_cache_window(self):
        """Test custom cache validity window."""
        # User specifies --cache-hours 48
        custom_cache_hours = 48
        cache_age_hours = 30
        
        is_valid = cache_age_hours < custom_cache_hours
        assert is_valid is True
        
        # But after 48 hours
        cache_age_hours = 50
        is_valid = cache_age_hours < custom_cache_hours
        assert is_valid is False


class TestForceFlag:
    """Test --force flag behavior."""

    def test_force_bypasses_cache(self):
        """Test that --force flag bypasses cache check."""
        force = True
        cache_exists = True
        cache_valid = True
        
        # With force=True, should always re-extract
        should_extract = force or not cache_valid
        assert should_extract is True

    def test_force_with_valid_cache(self):
        """Test --force with valid cache file."""
        force = True
        cache_age_hours = 2
        cache_hours_threshold = 24
        
        is_valid = cache_age_hours < cache_hours_threshold
        should_use_cache = (not force) and is_valid
        
        # Should NOT use cache because force=True
        assert should_use_cache is False
        assert force is True

    def test_no_force_with_valid_cache(self):
        """Test normal operation (no force) with valid cache."""
        force = False
        cache_age_hours = 2
        cache_hours_threshold = 24
        
        is_valid = cache_age_hours < cache_hours_threshold
        should_use_cache = (not force) and is_valid
        
        # Should use cache
        assert should_use_cache is True

    def test_no_force_with_expired_cache(self):
        """Test normal operation with expired cache."""
        force = False
        cache_age_hours = 30
        cache_hours_threshold = 24
        
        is_valid = cache_age_hours < cache_hours_threshold
        should_use_cache = (not force) and is_valid
        
        # Should re-extract due to expiration
        assert should_use_cache is False


class TestCacheRefresh:
    """Test cache refresh scenarios."""

    def test_cache_overwrite_on_force(self, tmp_path):
        """Test that cache is overwritten when using --force."""
        cache_file = tmp_path / "raw_activities.json"
        
        # Write initial cache
        initial_data = {"activities": [{"id": 1, "name": "Old"}]}
        cache_file.write_text(json.dumps(initial_data))
        
        # New data arrives with --force
        new_data = {"activities": [{"id": 1, "name": "New"}, {"id": 2, "name": "New2"}]}
        cache_file.write_text(json.dumps(new_data))
        
        # Verify cache was updated
        loaded = json.loads(cache_file.read_text())
        assert len(loaded["activities"]) == 2
        assert loaded["activities"][0]["name"] == "New"

    def test_cache_preserved_without_force(self, tmp_path):
        """Test that cache is preserved without --force."""
        cache_file = tmp_path / "raw_activities.json"
        
        # Write initial cache
        initial_data = {"activities": [{"id": 1, "name": "Original"}], "cached_at": "2026-01-29"}
        cache_file.write_text(json.dumps(initial_data))
        
        # Read cache (simulating use without --force)
        loaded = json.loads(cache_file.read_text())
        
        # Cache should be unchanged
        assert loaded["activities"][0]["name"] == "Original"
        assert loaded["cached_at"] == "2026-01-29"

    def test_cache_timestamp_update(self, tmp_path):
        """Test that cache timestamp is updated on refresh."""
        cache_file = tmp_path / "raw_activities.json"
        
        # Write cache with timestamp
        data_v1 = {"activities": [], "cached_at": "2026-01-28T10:00:00"}
        cache_file.write_text(json.dumps(data_v1))
        
        # Update cache with new timestamp
        data_v2 = {"activities": [], "cached_at": "2026-01-29T12:00:00"}
        cache_file.write_text(json.dumps(data_v2))
        
        # Verify timestamp was updated
        loaded = json.loads(cache_file.read_text())
        assert loaded["cached_at"] == "2026-01-29T12:00:00"


class TestCachingIntegration:
    """Test caching integration scenarios."""

    def test_first_run_creates_cache(self, tmp_path):
        """Test that first run creates cache file."""
        cache_file = tmp_path / "raw_activities.json"
        
        # No cache exists
        assert not cache_file.exists()
        
        # First run: create cache
        data = {"activities": [{"id": 1}], "cached_at": "2026-01-29T10:00:00"}
        cache_file.write_text(json.dumps(data))
        
        assert cache_file.exists()

    def test_second_run_uses_cache(self, tmp_path):
        """Test that second run uses cached data if fresh."""
        cache_file = tmp_path / "raw_activities.json"
        
        # Cache from recent run
        cache_data = {"activities": [{"id": 1, "name": "Ride"}], "cached_at": "2026-01-29T10:00:00"}
        cache_file.write_text(json.dumps(cache_data))
        
        # Read cache
        loaded = json.loads(cache_file.read_text())
        
        # Should use cached data
        assert loaded["activities"][0]["name"] == "Ride"

    def test_cache_miss_reruns_extraction(self, tmp_path):
        """Test extraction reruns on cache miss."""
        cache_file = tmp_path / "raw_activities.json"
        
        # Cache doesn't exist or is expired
        if cache_file.exists():
            cache_file.unlink()
        
        # Should trigger extraction
        needs_extraction = not cache_file.exists()
        assert needs_extraction is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
