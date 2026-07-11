"""
Rate limiting configuration using SlowAPI.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Global limiter instance configured with client IP as the rate-limit key
limiter = Limiter(key_func=get_remote_address)
