"""
Strava OAuth2 Authentication Module

Handles OAuth2 authentication flow, token management, and refresh logic for Strava API.
Uses stravalib.Client for API interactions and manages tokens persistently.
"""

import json
import os
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any

import requests
from dotenv import load_dotenv
from stravalib.client import Client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class StravaAuthenticator:
    """
    Manages Strava OAuth2 authentication and token lifecycle.
    
    Handles:
    - Initial authorization handshake
    - Token storage and retrieval
    - Automatic token refresh on expiration
    - Error handling for auth failures
    """
    
    # Strava API endpoints
    STRAVA_API_BASE = "https://www.strava.com/api/v3"
    STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
    STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
    
    # OAuth scopes required for full access
    SCOPES = ["read_all", "activity:read_all", "profile:read_all"]
    
    def __init__(self, env_file: str = ".env"):
        """
        Initialize StravaAuthenticator.
        
        Args:
            env_file: Path to .env file containing Strava credentials
        """
        # Load environment variables
        load_dotenv(env_file)
        
        self.client_id = os.getenv("STRAVA_CLIENT_ID")
        self.client_secret = os.getenv("STRAVA_CLIENT_SECRET")
        self.refresh_token = os.getenv("STRAVA_REFRESH_TOKEN")
        
        # Token storage path
        self.config_dir = Path("config")
        self.token_file = self.config_dir / "strava_tokens.json"
        
        # Ensure config directory exists
        self.config_dir.mkdir(exist_ok=True)
        
        # Validate credentials are loaded
        if not self.client_id or not self.client_secret:
            logger.error("Missing STRAVA_CLIENT_ID or STRAVA_CLIENT_SECRET in .env file")
            raise ValueError(
                "Strava credentials not found. Please ensure .env file contains "
                "STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET"
            )
        
        logger.info("StravaAuthenticator initialized successfully")
    
    def _save_token(self, token_data: Dict[str, Any]) -> None:
        """
        Save token data to config/strava_tokens.json.
        
        Args:
            token_data: Dictionary containing access_token, refresh_token, expires_at
        """
        try:
            with open(self.token_file, 'w') as f:
                json.dump(token_data, f, indent=2)
            logger.info(f"Token saved to {self.token_file}")
        except Exception as e:
            logger.error(f"Failed to save token: {e}")
            raise
    
    def _load_token(self) -> Optional[Dict[str, Any]]:
        """
        Load saved token data from config/strava_tokens.json.
        
        Returns:
            Token dictionary or None if file doesn't exist
        """
        if not self.token_file.exists():
            logger.warning(f"Token file not found: {self.token_file}")
            return None
        
        try:
            with open(self.token_file, 'r') as f:
                token_data = json.load(f)
            logger.info("Token loaded successfully")
            return token_data
        except Exception as e:
            logger.error(f"Failed to load token: {e}")
            return None
    
    def _is_token_expired(self, expires_at: float) -> bool:
        """
        Check if token is expired with a 5-minute buffer.
        
        Args:
            expires_at: Unix timestamp when token expires
            
        Returns:
            True if token is expired or will expire within 5 minutes
        """
        # Add 5-minute buffer for safety
        buffer_seconds = 300
        expiration_with_buffer = expires_at - buffer_seconds
        current_time = datetime.now().timestamp()
        
        is_expired = current_time >= expiration_with_buffer
        
        if is_expired:
            logger.warning("Token is expired or expiring soon")
        
        return is_expired
    
    def _refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Use refresh token to obtain a new access token from Strava API.
        
        Args:
            refresh_token: The refresh token from previous authentication
            
        Returns:
            Dictionary with new token data (access_token, refresh_token, expires_at)
            
        Raises:
            requests.RequestException: If API call fails
        """
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        }
        
        try:
            logger.info("Attempting to refresh access token...")
            response = requests.post(self.STRAVA_TOKEN_URL, data=payload)
            response.raise_for_status()
            
            token_response = response.json()
            
            # Extract relevant fields
            token_data = {
                "access_token": token_response.get("access_token"),
                "refresh_token": token_response.get("refresh_token"),
                "expires_at": token_response.get("expires_at")
            }
            
            logger.info("Access token refreshed successfully")
            self._save_token(token_data)
            
            return token_data
            
        except requests.RequestException as e:
            logger.error(f"Failed to refresh access token: {e}")
            raise
    
    def get_valid_token(self) -> str:
        """
        Get a valid (non-expired) access token.
        
        Checks saved token file:
        - If exists and valid: returns stored access_token
        - If expired: refreshes using refresh_token and returns new access_token
        - If missing: prompts user to authorize and obtain initial token
        
        Returns:
            Valid access token string
            
        Raises:
            ValueError: If unable to obtain valid token
        """
        # Try to load saved token
        saved_token = self._load_token()
        
        if saved_token:
            expires_at = saved_token.get("expires_at")
            
            # Check if token is still valid
            if not self._is_token_expired(expires_at):
                logger.info("Using saved access token")
                return saved_token["access_token"]
            
            # Token expired, attempt refresh
            refresh_token = saved_token.get("refresh_token")
            if refresh_token:
                try:
                    refreshed_token = self._refresh_access_token(refresh_token)
                    return refreshed_token["access_token"]
                except requests.RequestException:
                    logger.warning("Token refresh failed, prompting for new authorization")
        
        # No saved token or refresh failed - need initial authorization
        logger.info("No valid token found. Initiating authorization flow...")
        token_data = self.authorize()
        return token_data["access_token"]
    
    def get_authorization_url(self, redirect_uri: str = "http://localhost") -> str:
        """
        Generate Strava OAuth authorization URL.
        
        Args:
            redirect_uri: Where user will be redirected with authorization code
            
        Returns:
            Complete authorization URL
        """
        scope = ",".join(self.SCOPES)
        
        auth_url = (
            f"{self.STRAVA_AUTH_URL}?"
            f"client_id={self.client_id}&"
            f"redirect_uri={redirect_uri}&"
            f"response_type=code&"
            f"scope={scope}&"
            f"approval_prompt=force"
        )
        
        return auth_url
    
    def authorize(self) -> Dict[str, Any]:
        """
        Initial OAuth2 authorization handshake.
        
        Prompts user to:
        1. Visit authorization URL
        2. Authorize the application
        3. Paste the authorization code back
        
        Returns:
            Dictionary with access_token, refresh_token, expires_at
            
        Raises:
            ValueError: If authorization fails
        """
        try:
            redirect_uri = "http://localhost"
            auth_url = self.get_authorization_url(redirect_uri)
            
            print("\n" + "="*80)
            print("STRAVA AUTHORIZATION REQUIRED")
            print("="*80)
            print("\n1. Open this URL in your browser:")
            print(f"   {auth_url}")
            print("\n2. Authorize the application")
            print("3. You'll be redirected to a URL like: http://localhost?code=YOUR_CODE&scope=...")
            print("\nPaste the authorization CODE (not the full URL):\n")
            
            auth_code = input("Authorization Code: ").strip()
            
            if not auth_code:
                raise ValueError("Authorization code cannot be empty")
            
            # Exchange code for token
            payload = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": auth_code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri
            }
            
            logger.info("Exchanging authorization code for access token...")
            response = requests.post(self.STRAVA_TOKEN_URL, data=payload)
            response.raise_for_status()
            
            token_response = response.json()
            
            # Extract and save token data
            token_data = {
                "access_token": token_response.get("access_token"),
                "refresh_token": token_response.get("refresh_token"),
                "expires_at": token_response.get("expires_at")
            }
            
            self._save_token(token_data)
            
            print("\n✓ Authorization successful! Token saved to config/strava_tokens.json")
            logger.info("Authorization successful")
            
            return token_data
            
        except requests.RequestException as e:
            logger.error(f"Authorization failed: {e}")
            raise ValueError(f"Authorization failed: {e}")
        except ValueError as e:
            logger.error(f"Authorization error: {e}")
            raise
    
    def get_authenticated_client(self) -> Client:
        """
        Get an authenticated Strava API client.
        
        Returns:
            Authenticated stravalib.Client instance ready for API calls
            
        Raises:
            ValueError: If unable to obtain valid token
        """
        try:
            access_token = self.get_valid_token()
            client = Client(access_token=access_token)
            logger.info("Authenticated Strava client created successfully")
            return client
        except Exception as e:
            logger.error(f"Failed to create authenticated client: {e}")
            raise


def test_authentication():
    """
    Test the authentication flow.
    
    Useful for debugging authorization issues.
    """
    try:
        auth = StravaAuthenticator()
        
        # Test getting valid token
        token = auth.get_valid_token()
        print(f"\n✓ Valid token obtained (length: {len(token)} chars)")
        
        # Test creating authenticated client
        client = auth.get_authenticated_client()
        athlete = client.get_athlete()
        
        print(f"✓ Authenticated as: {athlete.firstname} {athlete.lastname}")
        print(f"✓ Location: {athlete.city}, {athlete.state}, {athlete.country}")
        
    except Exception as e:
        logger.error(f"Authentication test failed: {e}")
        raise


if __name__ == "__main__":
    # Quick test of authentication
    test_authentication()
