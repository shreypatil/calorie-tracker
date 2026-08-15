"""AI providers.

The model describes document layout; our own code reads the values. See
`provider.py` for the contract and the reasoning behind it.
"""

from app.ai.factory import build_provider, get_provider
from app.ai.provider import AIProvider
from app.ai.stub import StubProvider

__all__ = ["AIProvider", "StubProvider", "build_provider", "get_provider"]
