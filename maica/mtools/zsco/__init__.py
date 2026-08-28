"""
We write this module to enhance generic model's performance as core model through RAG and specific instructions.
"""

from .rag import GenericModelHelper

from typing import *
generic_helper: Optional[GenericModelHelper] = None

__all__ = [
    'GenericModelHelper',
    'generic_helper',
]