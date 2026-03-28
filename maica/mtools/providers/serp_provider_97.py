"""
This is the local MCP tool implementation.
Works well for minor deployment, but relatively slow & some performance consume & might hit captchas.
"""

from .base import register_provider

prio = 97
requires = []

from maica.mtools.mcp import asearch

register_provider(prio, requires, asearch)