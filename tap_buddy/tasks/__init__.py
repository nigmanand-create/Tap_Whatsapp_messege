"""Task entrypoints for TAP Buddy background jobs."""

from .scheduler import dispatch_campaign

__all__ = ["dispatch_campaign"]
