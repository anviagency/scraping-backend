"""
Initialize the Scraping-backend project.
"""

# Import Celery
from .celery import app as celery_app

# Export the Celery app
__all__ = ("celery_app",)
