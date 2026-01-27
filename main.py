"""
Strava ETL Pipeline - Main Entry Point

Orchestrates the complete extraction, transformation, and loading pipeline
for Strava cycling data to Tableau-optimized CSV.

Usage:
    python main.py                    # Run with cache (skip if <24h old)
    python main.py --force            # Force re-extraction (ignore cache)
    python main.py --months 6         # Extract last 6 months
    python main.py --force --months 3 # Force re-extract last 3 months
"""

import argparse
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple

from src.auth.strava_auth import StravaAuthenticator
from src.extraction.strava_extractor import StravaExtractor
from src.transformation.data_transformer import StravaTransformer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class StravaETLPipeline:
    """
    Orchestrates the complete Strava data pipeline.
    
    Manages:
    - Cache checking and expiration
    - Authentication
    - Data extraction
    - Transformation (when implemented)
    - Output to Tableau-optimized CSV
    """
    
    def __init__(self, output_dir: str = "data", cache_hours: int = 24):
        """
        Initialize the ETL pipeline.
        
        Args:
            output_dir: Directory for data files
            cache_hours: How many hours to consider cache as valid
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        self.raw_activities_file = self.output_dir / "raw_activities.json"
        self.cache_hours = cache_hours
        
        logger.info(f"StravaETLPipeline initialized (cache: {cache_hours}h)")
    
    def _is_cache_valid(self, force: bool = False) -> bool:
        """
        Check if cached raw activities file exists and is fresh.
        
        Args:
            force: If True, always return False (force re-extraction)
            
        Returns:
            True if cache is valid and should be used
        """
        if force:
            logger.info("--force flag detected, skipping cache check")
            return False
        
        if not self.raw_activities_file.exists():
            logger.info(f"Cache file not found: {self.raw_activities_file}")
            return False
        
        # Check file age
        file_mtime = datetime.fromtimestamp(self.raw_activities_file.stat().st_mtime)
        file_age = datetime.now() - file_mtime
        cache_threshold = timedelta(hours=self.cache_hours)
        
        if file_age < cache_threshold:
            hours_old = file_age.total_seconds() / 3600
            logger.info(
                f"Cache is valid (file is {hours_old:.1f} hours old, "
                f"threshold is {self.cache_hours}h). Skipping extraction."
            )
            return True
        else:
            hours_old = file_age.total_seconds() / 3600
            logger.info(
                f"Cache expired (file is {hours_old:.1f} hours old, "
                f"threshold is {self.cache_hours}h). Re-extracting data."
            )
            return False
    
    def _load_cached_activities(self) -> Optional[list]:
        """
        Load activities from cached JSON file.
        
        Returns:
            List of activities or None if load fails
        """
        try:
            with open(self.raw_activities_file, 'r') as f:
                activities = json.load(f)
            
            logger.info(f"Loaded {len(activities)} activities from cache")
            return activities
        
        except Exception as e:
            logger.error(f"Failed to load cached activities: {e}")
            return None
    
    def run(
        self,
        force: bool = False,
        months: int = 12,
        extract_only: bool = False,
        start_date: Optional[str] = None
    ) -> Tuple[Path, Optional[Path], Optional[Path]]:
        """
        Run the complete ETL pipeline.
        
        Args:
            force: Force re-extraction (ignore cache)
            months: Number of months to extract
            extract_only: Stop after extraction (don't transform)
            
        Returns:
            Tuple of (raw_file, summary_csv, paths_csv)
        """
        logger.info("="*80)
        logger.info("STRAVA ETL PIPELINE STARTED")
        logger.info("="*80)
        
        try:
            # Step 1: Check cache
            if self._is_cache_valid(force):
                activities = self._load_cached_activities()
                if activities:
                    logger.info("Using cached data for this run")
                else:
                    logger.warning("Cache loading failed, extracting from API")
                    activities = self._extract_activities(months, start_date=start_date)
            else:
                activities = self._extract_activities(months, start_date=start_date)
            
            if not activities:
                raise ValueError("No activities extracted. Pipeline cannot continue.")
            
            logger.info(f"Pipeline processed {len(activities)} activities")
            
            # Step 2: Transformation
            if not extract_only:
                logger.info("Starting transformation phase...")
                summary_path, paths_path = self._transform_data()
                logger.info(f"✓ Generated output files:")
                logger.info(f"    - Summary: {summary_path}")
                logger.info(f"    - Paths: {paths_path}")
            else:
                logger.info("Extract-only mode: skipping transformation")
                summary_path, paths_path = None, None
            
            logger.info("="*80)
            logger.info("STRAVA ETL PIPELINE COMPLETED SUCCESSFULLY")
            logger.info("="*80)
            
            return self.raw_activities_file, summary_path, paths_path
        
        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            raise
    
    def _extract_activities(self, months: int = 12, start_date: Optional[str] = None) -> Optional[list]:
        """
        Extract activities from Strava API.
        
        Args:
            months: Number of months to extract
            
        Returns:
            List of activities or None if extraction fails
        """
        try:
            logger.info("Starting data extraction from Strava API...")
            
            extractor = StravaExtractor(output_dir=str(self.output_dir))
            activities = extractor.fetch_activities(months_back=months, start_date=start_date)
            
            # Save raw activities
            extractor.save_activities(activities)
            
            return activities
        
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return None
    
    def _transform_data(self) -> Tuple[Path, Path]:
        """
        Transform extracted data into Tableau-optimized CSVs.
        
        Returns:
            Tuple of (summary_csv_path, paths_csv_path)
        """
        try:
            logger.info("Starting data transformation...")
            
            transformer = StravaTransformer(
                input_dir=str(self.output_dir),
                output_dir=str(self.output_dir)
            )
            
            summary_path, paths_path = transformer.transform_and_save()
            
            logger.info(f"Data transformation complete")
            
            return summary_path, paths_path
        
        except Exception as e:
            logger.error(f"Transformation failed: {e}")
            raise


def main():
    """
    Command-line entry point for the ETL pipeline.
    """
    parser = argparse.ArgumentParser(
        description='Strava ETL Pipeline - Extract cycling data for Tableau',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                    # Run with cache (skip if <24h old)
  python main.py --force            # Force re-extraction
  python main.py --months 6         # Extract last 6 months
  python main.py --force --months 3 # Force re-extract last 3 months
        """
    )
    
    parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='Force re-extraction (ignore cache)'
    )
    
    parser.add_argument(
        '--months', '-m',
        type=int,
        default=12,
        help='Number of months to extract (default: 12)'
    )
    
    parser.add_argument(
        '--extract-only', '-e',
        action='store_true',
        help='Stop after extraction, skip transformation'
    )
    
    parser.add_argument(
        '--cache-hours',
        type=int,
        default=24,
        help='Cache validity period in hours (default: 24)'
    )

    parser.add_argument(
        '--start-date',
        type=str,
        default=None,
        help="Absolute start date (YYYY-MM-DD) to fetch activities from. Overrides months back when provided."
    )
    
    args = parser.parse_args()
    
    # Run pipeline
    pipeline = StravaETLPipeline(cache_hours=args.cache_hours)
    
    try:
        raw_file, summary_csv, paths_csv = pipeline.run(
                force=args.force,
                months=args.months,
                extract_only=args.extract_only,
                start_date=args.start_date
            )
        
        print(f"\n✓ Pipeline completed successfully!")
        print(f"  Raw Data: {raw_file}")
        if summary_csv:
            print(f"  Summary CSV: {summary_csv}")
            print(f"  Paths CSV: {paths_csv}")
        
    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}")
        raise


if __name__ == "__main__":
    main()
