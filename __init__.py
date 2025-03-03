"""
RSS Digest Tool - Generate summarized digests from RSS feeds using AI.
"""

# Version of the package
__version__ = '0.9.0'

# Export the main classes and functions
from .core import RSSDigestTool, SummaryCache, run_digest_tool

# Convenience exports for direct imports
__all__ = ['RSSDigestTool', 'SummaryCache', 'run_digest_tool']