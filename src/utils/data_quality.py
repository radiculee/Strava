"""
Data Quality and Validation Utilities

Handles data cleaning, validation, and quality checks for cycling activities.
"""

import logging
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)


class DataQualityChecker:
    """
    Validates and cleans activity data for consistency and completeness.
    """
    
    @staticmethod
    def is_valid_activity(activity: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Check if an activity is valid and usable.
        
        Args:
            activity: Activity dictionary
            
        Returns:
            Tuple of (is_valid, reason)
        """
        # Check required fields
        required_fields = ['id', 'name', 'type', 'start_date_local', 'distance', 'moving_time']
        
        for field in required_fields:
            if field not in activity or activity[field] is None:
                return False, f"Missing required field: {field}"
        
        # Check for stationary trainer rides with zero GPS
        if activity.get('trainer', False) and not activity.get('summary_polyline'):
            return False, "Stationary trainer ride without GPS data"
        
        # Check for zero distance or duration
        if activity.get('distance', 0) == 0:
            return False, "Zero distance activity"
        
        if activity.get('moving_time', 0) == 0:
            return False, "Zero moving time activity"
        
        return True, "Valid"
    
    @staticmethod
    def remove_duplicates(activities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate activities by ID.
        
        Args:
            activities: List of activities
            
        Returns:
            Deduplicated list of activities
        """
        seen_ids = set()
        unique_activities = []
        duplicates_found = 0
        
        for activity in activities:
            activity_id = activity.get('id')
            if activity_id not in seen_ids:
                seen_ids.add(activity_id)
                unique_activities.append(activity)
            else:
                duplicates_found += 1
        
        if duplicates_found > 0:
            logger.info(f"Removed {duplicates_found} duplicate activities")
        
        return unique_activities
    
    @staticmethod
    def filter_quality_activities(activities: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
        """
        Filter out low-quality activities.
        
        Args:
            activities: List of activities
            
        Returns:
            Tuple of (quality_activities, removed_count)
        """
        quality_activities = []
        removed_count = 0
        
        for activity in activities:
            is_valid, reason = DataQualityChecker.is_valid_activity(activity)
            if is_valid:
                quality_activities.append(activity)
            else:
                removed_count += 1
                logger.debug(f"Filtered activity {activity.get('id')}: {reason}")
        
        if removed_count > 0:
            logger.info(f"Filtered out {removed_count} low-quality activities")
        
        return quality_activities, removed_count


def validate_csv_output(df_rows: int, expected_min: int = 10) -> bool:
    """
    Validate CSV output has reasonable data.
    
    Args:
        df_rows: Number of rows in output
        expected_min: Minimum expected rows
        
    Returns:
        True if output is valid
    """
    if df_rows < expected_min:
        logger.warning(f"Output has only {df_rows} rows (expected at least {expected_min})")
        return False
    
    logger.info(f"CSV output validation passed: {df_rows} rows")
    return True
