"""
Helper functions for the Scraping-backend project.
"""

import uuid
import random
import string
import hashlib
import logging
from datetime import datetime, timedelta

from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


def generate_unique_id():
    """
    Generate a unique ID.

    Returns:
        str: Unique ID
    """
    return str(uuid.uuid4())


def generate_random_string(length=10):
    """
    Generate a random string of the specified length.

    Args:
        length (int): Length of the string

    Returns:
        str: Random string
    """
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for _ in range(length))


def hash_string(text, salt=None):
    """
    Hash a string with SHA-256.

    Args:
        text (str): Text to hash
        salt (str, optional): Salt to use

    Returns:
        str: Hashed string
    """
    if salt is None:
        salt = settings.SECRET_KEY

    text_with_salt = f"{text}{salt}"
    return hashlib.sha256(text_with_salt.encode()).hexdigest()


def get_future_date(days=0, hours=0, minutes=0, seconds=0):
    """
    Get a future date from now.

    Args:
        days (int): Days to add
        hours (int): Hours to add
        minutes (int): Minutes to add
        seconds (int): Seconds to add

    Returns:
        datetime: Future date
    """
    return timezone.now() + timedelta(
        days=days, hours=hours, minutes=minutes, seconds=seconds
    )


def parse_date_string(date_string, format_str="%Y-%m-%d"):
    """
    Parse a date string into a datetime object.

    Args:
        date_string (str): Date string
        format_str (str): Format string

    Returns:
        datetime: Parsed date
    """
    try:
        return datetime.strptime(date_string, format_str)
    except (ValueError, TypeError):
        return None


def format_currency(amount, currency="USD"):
    """
    Format a currency amount.

    Args:
        amount (float): Amount
        currency (str): Currency code

    Returns:
        str: Formatted currency
    """
    if currency == "USD":
        return f"${amount:.2f}"
    elif currency == "EUR":
        return f"€{amount:.2f}"
    elif currency == "ILS":
        return f"₪{amount:.2f}"
    else:
        return f"{amount:.2f} {currency}"


def limit_text(text, max_length=100, suffix="..."):
    """
    Limit text to a maximum length.

    Args:
        text (str): Text to limit
        max_length (int): Maximum length
        suffix (str): Suffix to append if shortened

    Returns:
        str: Limited text
    """
    if text is None:
        return ""

    if len(text) <= max_length:
        return text

    return text[: max_length - len(suffix)] + suffix


def is_valid_email(email):
    """
    Check if an email is valid.

    Args:
        email (str): Email to check

    Returns:
        bool: True if valid, False otherwise
    """
    # This is a simple check, for production use a more robust validation
    return "@" in email and "." in email.split("@")[1]


def safe_json_loads(json_string, default=None):
    """
    Safely load JSON string.

    Args:
        json_string (str): JSON string to load
        default: Default value to return on error

    Returns:
        dict: Parsed JSON or default value
    """
    import json

    if not json_string:
        return default if default is not None else {}

    try:
        return json.loads(json_string)
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON: {str(e)}")
        return default if default is not None else {}
