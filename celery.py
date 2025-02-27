"""
Celery configuration for the Scraping-backend project.
"""

import os
import sys

# מוסיף את הספריה הנוכחית לנתיב החיפוש של Python
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from celery import Celery
from django.conf import settings

# Set the default Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

# Create the Celery app
app = Celery("Scraping_backend")

# Use a string here to avoid pickle issues
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load tasks from all registered Django apps
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)


@app.task(bind=True)
def debug_task(self):
    """
    Debug task to verify Celery is working.
    """
    print(f"Request: {self.request!r}")