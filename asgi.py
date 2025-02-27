"""
ASGI config for Scraping-backend project.
"""

import os
import sys

# מוסיף את הספריה הנוכחית לנתיב החיפוש של Python
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

application = get_asgi_application()