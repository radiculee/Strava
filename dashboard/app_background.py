"""
Photo-overlay variant of the Strava dashboard.

Run with:
    streamlit run dashboard/app_background.py
"""

from app import main


if __name__ == "__main__":
    main(photo_layout="overlay")
