"""
Strava Data Extraction Module

Extracts cycling activities from the Strava API with pagination support.
Fetches detailed activity data including GPS coordinates (polyline) and metrics.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

from stravalib.client import Client

from src.auth.strava_auth import StravaAuthenticator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class StravaExtractor:
    """
    Extracts cycling activity data from Strava API.
    
    Handles:
    - Authentication via StravaAuthenticator
    - Activity fetching with pagination
    - Detailed activity data capture including GPS polylines
    - JSON persistence for downstream processing
    """
    
    # Activity fields to capture from Strava API
    REQUIRED_FIELDS = [
        'id', 'name', 'type', 'start_date_local', 'distance', 
        'moving_time', 'total_elevation_gain', 'commute', 'trainer'
    ]
    
    # Map field is critical for geospatial analysis
    MAP_FIELD = 'map'
    
    def __init__(self, output_dir: str = "data"):
        """
        Initialize StravaExtractor.
        
        Args:
            output_dir: Directory to save extracted data (default: "data")
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.raw_output_file = self.output_dir / "raw_activities.json"
        
        # Initialize authenticator and client
        self.auth = StravaAuthenticator()
        self.client: Optional[Client] = None
        
        logger.info(f"StravaExtractor initialized with output directory: {output_dir}")
    
    def _get_client(self) -> Client:
        """
        Get authenticated Strava client (lazy initialization).
        
        Returns:
            Authenticated stravalib.Client instance
        """
        if self.client is None:
            self.client = self.auth.get_authenticated_client()
            logger.info("Authenticated client created")
        
        return self.client
    
    def _calculate_after_timestamp(self, months_back: int = 12) -> datetime:
        """
        Calculate datetime for 'months_back' months ago.
        
        Args:
            months_back: Number of months to go back (default: 12)
            
        Returns:
            datetime object for the target date
        """
        # Calculate date from months ago
        # Using 30 days per month for simplicity
        days_back = months_back * 30
        target_date = datetime.now() - timedelta(days=days_back)
        
        logger.info(
            f"Calculated 'after' date: {target_date.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        return target_date
    
    def _extract_activity_data(self, activity: Any) -> Dict[str, Any]:
        """
        Extract relevant fields from a Strava activity object.
        
        Args:
            activity: stravalib Activity object
            
        Returns:
            Dictionary with extracted activity data
        """
        activity_dict = {
            'id': activity.id,
            'name': activity.name,
            'type': str(activity.type),  # Convert RelaxedActivityType to string
            'start_date_local': activity.start_date_local.isoformat() if activity.start_date_local else None,
            'distance': activity.distance.num if hasattr(activity.distance, 'num') else float(activity.distance),
            'moving_time': activity.moving_time.total_seconds() if hasattr(activity.moving_time, 'total_seconds') else int(activity.moving_time),
            'total_elevation_gain': activity.total_elevation_gain.num if hasattr(activity.total_elevation_gain, 'num') else float(activity.total_elevation_gain),
            'commute': activity.commute,
            'trainer': activity.trainer,
        }
        
        # Add GPS polyline if available
        if hasattr(activity, 'map') and activity.map and hasattr(activity.map, 'summary_polyline'):
            activity_dict['summary_polyline'] = activity.map.summary_polyline
        else:
            activity_dict['summary_polyline'] = None
        
        return activity_dict
    
    def fetch_activities(self, months_back: int = 12, start_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch all cycling activities from the last N months.
        
        Handles pagination automatically using stravalib's built-in pagination.
        Filters out non-cycling activities.
        
        Args:
            months_back: Number of months to fetch data for (default: 12)
            
        Returns:
            List of activity dictionaries with detailed data
        """
        logger.info(f"Starting activity extraction for the last {months_back} months...")
        
        try:
            client = self._get_client()

            # Determine the 'after' parameter: either absolute start_date or months_back
            after_date = None
            after_timestamp = None
            if start_date:
                # Parse start_date string 'YYYY-MM-DD' into datetime and unix timestamp
                try:
                    dt = datetime.strptime(start_date, "%Y-%m-%d")
                    # Treat provided date as start of that day in UTC
                    from datetime import timezone
                    dt_utc = datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)
                    after_timestamp = int(dt_utc.timestamp())
                    # Log confirmation message required by user
                    logger.info(f"Fetching activities from absolute start date: {start_date}")
                except Exception as e:
                    logger.error(f"Invalid start_date format '{start_date}': {e}")
                    raise
            else:
                after_date = self._calculate_after_timestamp(months_back)
            
            activities = []
            activity_count = 0
            cycling_count = 0
            
            # Fetch all activities after the date
            # stravalib handles pagination automatically via generator
            if after_timestamp is not None:
                # Attempt to pass unix timestamp directly; fall back to datetime if needed
                logger.info(f"Fetching activities after timestamp {after_timestamp} (derived from {start_date})...")
                try:
                    iterator = client.get_activities(after=after_timestamp, limit=None)
                except AssertionError:
                    # stravalib may require a datetime object; convert and retry
                    logger.info("stravalib requires datetime; converting timestamp to datetime and retrying")
                    from datetime import timezone
                    iterator = client.get_activities(after=datetime.fromtimestamp(after_timestamp, tz=timezone.utc), limit=None)
            else:
                logger.info(f"Fetching activities after {after_date.strftime('%Y-%m-%d')}...")
                iterator = client.get_activities(after=after_date, limit=None)

            for activity in iterator:
                activity_count += 1
                
                # Filter for cycling activities only
                if activity.type not in ['Ride', 'VirtualRide', 'EBikeRide']:
                    continue
                
                cycling_count += 1
                
                # Extract and store activity data
                activity_data = self._extract_activity_data(activity)
                activities.append(activity_data)
                
                # Log progress every 50 activities
                if cycling_count % 50 == 0:
                    logger.info(f"Processed {cycling_count} cycling activities...")
            
            logger.info(
                f"✓ Extraction complete: {cycling_count} cycling activities "
                f"found (from {activity_count} total activities)"
            )
            
            return activities
        
        except Exception as e:
            logger.error(f"Failed to fetch activities: {str(e)}", exc_info=True)
            raise
    
    def save_activities(self, activities: List[Dict[str, Any]]) -> Path:
        """
        Save activities to JSON file.
        
        Args:
            activities: List of activity dictionaries
            
        Returns:
            Path to saved file
        """
        try:
            with open(self.raw_output_file, 'w') as f:
                json.dump(activities, f, indent=2)
            
            file_size_kb = self.raw_output_file.stat().st_size / 1024
            
            logger.info(
                f"✓ Activities saved to {self.raw_output_file} "
                f"({len(activities)} activities, {file_size_kb:.2f} KB)"
            )
            
            return self.raw_output_file
        
        except Exception as e:
            logger.error(f"Failed to save activities: {e}")
            raise
    
    def extract_and_save(self, months_back: int = 12) -> Path:
        """
        Complete extraction and save pipeline.
        
        Args:
            months_back: Number of months to fetch
            
        Returns:
            Path to saved activities file
        """
        activities = self.fetch_activities(months_back=months_back)
        return self.save_activities(activities)


def test_extraction():
    """
    Test the extraction module.
    
    Useful for debugging extraction issues.
    """
    try:
        extractor = StravaExtractor()
        
        # Fetch last 3 months for quick testing
        print("\nFetching activities...")
        activities = extractor.fetch_activities(months_back=3)
        
        print(f"\n✓ Found {len(activities)} cycling activities")
        
        if activities:
            sample_activity = activities[0]
            print(f"\nSample activity:")
            print(f"  ID: {sample_activity.get('id')}")
            print(f"  Name: {sample_activity.get('name')}")
            print(f"  Type: {sample_activity.get('type')}")
            print(f"  Distance: {sample_activity.get('distance')} meters")
            print(f"  Has polyline: {'summary_polyline' in sample_activity and sample_activity['summary_polyline'] is not None}")
        
        # Save for real
        extractor.save_activities(activities)
        
    except Exception as e:
        logger.error(f"Extraction test failed: {e}")
        raise


if __name__ == "__main__":
    test_extraction()
