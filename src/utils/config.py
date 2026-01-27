"""
Configuration and Environment Management

Handles configuration loading and validation for the ETL pipeline.
"""

import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class Config:
    """Application configuration management."""
    
    def __init__(self, env_file: str = ".env"):
        """Load and validate configuration."""
        load_dotenv(env_file)
        
        # Strava API Credentials
        self.STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
        self.STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
        self.STRAVA_REFRESH_TOKEN = os.getenv("STRAVA_REFRESH_TOKEN")
        
        # Output Configuration
        self.OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./data")
        self.OUTPUT_FILENAME = os.getenv("OUTPUT_FILENAME", "cycling_activities_2025.csv")
        
        # API Configuration
        self.STRAVA_API_BASE_URL = os.getenv("STRAVA_API_BASE_URL", "https://www.strava.com/api/v3")
        self.ACTIVITIES_PER_PAGE = int(os.getenv("ACTIVITIES_PER_PAGE", 200))
        self.MONTHS_BACK = int(os.getenv("MONTHS_BACK", 12))
        
        # Create output directory
        Path(self.OUTPUT_DIR).mkdir(exist_ok=True)
        
        logger.info("Configuration loaded successfully")
    
    def validate(self) -> bool:
        """
        Validate required configuration is present.
        
        Returns:
            True if all required config is valid
        """
        if not self.STRAVA_CLIENT_ID or not self.STRAVA_CLIENT_SECRET:
            logger.error("Missing Strava credentials in configuration")
            return False
        
        if self.ACTIVITIES_PER_PAGE < 1 or self.ACTIVITIES_PER_PAGE > 200:
            logger.warning(f"Invalid ACTIVITIES_PER_PAGE: {self.ACTIVITIES_PER_PAGE}, using 200")
            self.ACTIVITIES_PER_PAGE = 200
        
        if self.MONTHS_BACK < 1:
            logger.warning(f"Invalid MONTHS_BACK: {self.MONTHS_BACK}, using 12")
            self.MONTHS_BACK = 12
        
        logger.info("Configuration validation passed")
        return True


def get_config(env_file: str = ".env") -> Config:
    """Get application configuration instance."""
    return Config(env_file)
