"""Rate limiting for authentication and AI endpoints (NFR-4).

Keyed by client IP. In-memory storage is right for a single-process demo; a
real deployment would point `storage_uri` at Redis so limits hold across
workers.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=[])
