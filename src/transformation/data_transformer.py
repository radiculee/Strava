"""
Strava Data Transformation Module

Transforms raw JSON activity data into Tableau-optimized CSV formats.
Includes unit conversions, date parsing, geospatial polyline decoding,
and metric calculations.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

import pandas as pd
import polyline
from dateutil.parser import isoparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class StravaTransformer:
    """
    Transforms raw Strava activity data into Tableau-optimized formats.
    
    Handles:
    - Unit conversions (meters→km, seconds→minutes)
    - Date/time parsing and decomposition
    - Metric calculations (speed, pace)
    - GPS polyline decoding for mapping
    - CSV export in two formats: summary and paths
    """
    
    # Conversion constants
    METERS_TO_KM = 0.001
    SECONDS_TO_MINUTES = 1 / 60
    
    # Days of week mapping
    DAYS_OF_WEEK = [
        'Monday', 'Tuesday', 'Wednesday', 'Thursday', 
        'Friday', 'Saturday', 'Sunday'
    ]
    
    # Activity type mapping for better readability
    ACTIVITY_TYPE_MAP = {
        'Ride': 'Road Bike',
        'VirtualRide': 'Virtual Ride',
        'EBikeRide': 'E-Bike',
        'MountainBikeRide': 'Mountain Bike',
        'GravelRide': 'Gravel Bike'
    }
    
    def __init__(self, input_dir: str = "data", output_dir: str = "data"):
        """
        Initialize StravaTransformer.
        
        Args:
            input_dir: Directory containing raw_activities.json
            output_dir: Directory to save transformed CSV files
        """
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        self.raw_file = self.input_dir / "raw_activities.json"
        self.summary_file = self.output_dir / "cycling_summary.csv"
        self.paths_file = self.output_dir / "cycling_paths.csv"
        
        logger.info(f"StravaTransformer initialized")
        logger.info(f"  Input: {self.raw_file}")
        logger.info(f"  Output Summary: {self.summary_file}")
        logger.info(f"  Output Paths: {self.paths_file}")
    
    def _load_raw_activities(self) -> List[Dict[str, Any]]:
        """
        Load raw activities from JSON file.
        
        Returns:
            List of activity dictionaries
            
        Raises:
            FileNotFoundError: If raw_activities.json doesn't exist
        """
        if not self.raw_file.exists():
            raise FileNotFoundError(
                f"Raw activities file not found: {self.raw_file}\n"
                "Please run extraction first with: python main.py"
            )
        
        try:
            with open(self.raw_file, 'r') as f:
                activities = json.load(f)
            
            logger.info(f"Loaded {len(activities)} raw activities from {self.raw_file}")
            return activities
        
        except Exception as e:
            logger.error(f"Failed to load raw activities: {e}")
            raise
    
    def _parse_datetime(self, datetime_str: str) -> datetime:
        """
        Parse ISO-8601 datetime string.
        
        Args:
            datetime_str: ISO format datetime string
            
        Returns:
            datetime object
        """
        return isoparse(datetime_str) if datetime_str else None
    
    def _calculate_metrics(
        self,
        distance_m: float,
        moving_time_s: float
    ) -> Tuple[float, Optional[float]]:
        """
        Calculate Average Speed (km/h) and Pace (min/km).
        
        Args:
            distance_m: Distance in meters
            moving_time_s: Moving time in seconds
            
        Returns:
            Tuple of (average_speed_kmh, pace_min_km)
        """
        distance_km = distance_m * self.METERS_TO_KM
        moving_time_h = moving_time_s / 3600  # Convert seconds to hours
        
        # Avoid division by zero
        if moving_time_s == 0 or distance_m == 0:
            return 0.0, None
        
        average_speed_kmh = distance_km / moving_time_h if moving_time_h > 0 else 0.0
        pace_min_km = (moving_time_s / 60) / distance_km if distance_km > 0 else None
        
        return round(average_speed_kmh, 2), round(pace_min_km, 2) if pace_min_km else None
    
    def _transform_activity(self, activity: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform a single activity with all conversions and calculations.
        
        Args:
            activity: Raw activity dictionary from JSON
            
        Returns:
            Transformed activity dictionary with Tableau-ready fields
        """
        # Parse date
        start_date_local = self._parse_datetime(activity.get('start_date_local'))
        
        # Unit conversions
        distance_km = activity.get('distance', 0) * self.METERS_TO_KM
        moving_time_min = activity.get('moving_time', 0) * self.SECONDS_TO_MINUTES
        elevation_m = activity.get('total_elevation_gain', 0)
        
        # Calculate metrics
        avg_speed_kmh, pace_min_km = self._calculate_metrics(
            activity.get('distance', 0),
            activity.get('moving_time', 0)
        )
        
        # Extract date components for Tableau time series
        date_parts = {}
        if start_date_local:
            date_parts = {
                'Year': start_date_local.year,
                'Month': start_date_local.month,
                'Day': start_date_local.day,
                'Day_of_Week': self.DAYS_OF_WEEK[start_date_local.weekday()],
                'Date': start_date_local.strftime('%Y-%m-%d'),
            }
        
        # Activity type mapping
        activity_type = str(activity.get('type', 'Unknown')).strip()
        # Handle RelaxedActivityType string representations
        if "'" in activity_type:
            activity_type = activity_type.split("'")[1]
        activity_type_label = self.ACTIVITY_TYPE_MAP.get(activity_type, activity_type)
        
        # Activity classification
        activity_class = 'Commute' if activity.get('commute', False) else 'Leisure'
        
        # Has GPS data check
        has_gps = activity.get('summary_polyline') is not None
        
        # Build transformed activity
        transformed = {
            'Activity_ID': activity.get('id'),
            'Activity_Name': activity.get('name', ''),
            'Activity_Type': activity_type_label,
            'Activity_Class': activity_class,
            'Start_Date_Local': activity.get('start_date_local', ''),
            'Distance_KM': round(distance_km, 2),
            'Elevation_M': round(elevation_m, 1) if elevation_m else 0,
            'Moving_Time_Minutes': round(moving_time_min, 1),
            'Average_Speed_KMH': avg_speed_kmh,
            'Pace_Min_Per_KM': pace_min_km,
            'Has_GPS_Data': has_gps,
            'Summary_Polyline': activity.get('summary_polyline'),
            **date_parts
        }
        
        return transformed
    
    def _decode_polyline(self, polyline_str: str) -> List[Tuple[float, float]]:
        """
        Decode polyline string into list of (lat, lon) tuples.
        
        Args:
            polyline_str: Encoded polyline string from Strava
            
        Returns:
            List of (latitude, longitude) tuples
        """
        if not polyline_str:
            return []
        
        try:
            # polyline.decode() returns list of (lat, lon) tuples
            coordinates = polyline.decode(polyline_str)
            return coordinates
        except Exception as e:
            logger.warning(f"Failed to decode polyline: {e}")
            return []
    
    def _create_paths_data(self, activities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Create path-format data from activities (one row per GPS point).
        
        Args:
            activities: List of transformed activity dictionaries
            
        Returns:
            List of path point dictionaries for Tableau
        """
        paths_data = []
        
        for activity in activities:
            activity_id = activity.get('Activity_ID')
            polyline_str = activity.get('Summary_Polyline')
            
            # Skip if no polyline data
            if not polyline_str:
                logger.debug(f"Activity {activity_id} has no GPS data, skipping")
                continue
            
            # Decode polyline
            coordinates = self._decode_polyline(polyline_str)
            
            if not coordinates:
                logger.debug(f"Activity {activity_id} polyline decode failed")
                continue
            
            # Create one row per coordinate point
            for point_index, (latitude, longitude) in enumerate(coordinates):
                path_point = {
                    'Activity_ID': activity_id,
                    'Activity_Name': activity.get('Activity_Name'),
                    'Activity_Type': activity.get('Activity_Type'),
                    'Point_Index': point_index,
                    'Latitude': round(latitude, 6),
                    'Longitude': round(longitude, 6),
                    'Start_Date': activity.get('Date', ''),  # For context
                }
                paths_data.append(path_point)
        
        logger.info(f"Created {len(paths_data)} GPS points from {len(activities)} activities")
        
        return paths_data
    
    def transform(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Execute complete transformation pipeline.
        
        Returns:
            Tuple of (summary_df, paths_df) DataFrames
        """
        logger.info("Starting transformation pipeline...")
        
        try:
            # Load raw data
            raw_activities = self._load_raw_activities()
            
            # Transform each activity
            logger.info("Transforming activities...")
            transformed_activities = [
                self._transform_activity(activity)
                for activity in raw_activities
            ]
            
            logger.info(f"✓ Transformed {len(transformed_activities)} activities")
            
            # Create DataFrames
            summary_df = pd.DataFrame(transformed_activities)
            
            # Remove polyline from summary (it's large and not needed here)
            if 'Summary_Polyline' in summary_df.columns:
                summary_df = summary_df.drop(columns=['Summary_Polyline'])
            
            # Create paths data
            paths_data = self._create_paths_data(transformed_activities)
            paths_df = pd.DataFrame(paths_data) if paths_data else pd.DataFrame()
            
            logger.info("✓ Transformation complete")
            
            return summary_df, paths_df
        
        except Exception as e:
            logger.error(f"Transformation failed: {e}")
            raise
    
    def save_summary(self, summary_df: pd.DataFrame) -> Path:
        """
        Save summary data to CSV.
        
        Args:
            summary_df: Summary DataFrame
            
        Returns:
            Path to saved file
        """
        try:
            # Ensure proper date format (ISO-8601)
            if 'Start_Date_Local' in summary_df.columns:
                summary_df['Start_Date_Local'] = pd.to_datetime(
                    summary_df['Start_Date_Local']
                ).dt.strftime('%Y-%m-%d %H:%M:%S')
            
            summary_df.to_csv(self.summary_file, index=False)
            
            file_size_kb = self.summary_file.stat().st_size / 1024
            logger.info(
                f"✓ Summary CSV saved to {self.summary_file} "
                f"({len(summary_df)} rows, {file_size_kb:.2f} KB)"
            )
            
            return self.summary_file
        
        except Exception as e:
            logger.error(f"Failed to save summary CSV: {e}")
            raise
    
    def save_paths(self, paths_df: pd.DataFrame) -> Path:
        """
        Save paths data to CSV.
        
        Args:
            paths_df: Paths DataFrame
            
        Returns:
            Path to saved file
        """
        if paths_df.empty:
            logger.warning("No paths data to save")
            return self.paths_file
        
        try:
            paths_df.to_csv(self.paths_file, index=False)
            
            file_size_kb = self.paths_file.stat().st_size / 1024
            logger.info(
                f"✓ Paths CSV saved to {self.paths_file} "
                f"({len(paths_df)} rows, {file_size_kb:.2f} KB)"
            )
            
            return self.paths_file
        
        except Exception as e:
            logger.error(f"Failed to save paths CSV: {e}")
            raise
    
    def transform_and_save(self) -> Tuple[Path, Path]:
        """
        Complete transformation and save pipeline.
        
        Returns:
            Tuple of (summary_path, paths_path)
        """
        summary_df, paths_df = self.transform()
        
        summary_path = self.save_summary(summary_df)
        paths_path = self.save_paths(paths_df)
        
        return summary_path, paths_path


def test_transformation():
    """
    Test the transformation module.
    
    Useful for debugging transformation issues.
    """
    try:
        transformer = StravaTransformer()
        
        summary_path, paths_path = transformer.transform_and_save()
        
        print(f"\n✓ Transformation successful!")
        print(f"  Summary CSV: {summary_path}")
        print(f"  Paths CSV: {paths_path}")
        
        # Load and display sample
        summary_df = pd.read_csv(summary_path)
        print(f"\nSummary CSV Preview ({len(summary_df)} activities):")
        print(summary_df.head(3).to_string())
        
        if Path(paths_path).exists() and Path(paths_path).stat().st_size > 0:
            paths_df = pd.read_csv(paths_path)
            print(f"\nPaths CSV Preview ({len(paths_df)} points):")
            print(paths_df.head(3).to_string())
        
    except Exception as e:
        logger.error(f"Transformation test failed: {e}")
        raise


if __name__ == "__main__":
    test_transformation()
