"""
Celery configuration for the Scraping-backend project.
"""

import os
from celery import Celery
from django.conf import settings

# Set the default Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fintech_project.settings")

# Create the Celery app
app = Celery("fintech_project")

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
