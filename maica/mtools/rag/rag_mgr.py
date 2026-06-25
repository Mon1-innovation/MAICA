"""
Okay, calm down Edge, take a breath.

We want RAG to handle long-term memory (MFocus-sfe), which optionally replaces the former LLM implementation.
We shouldn't rebuild the vector storage on every connection init, so we have to keep it in fs_storage.

Things we need:
- Information MFocus uses changes frequently. We want an index (id, text, hash?) to be able to remove determined items.
    - For temp items, maybe we also need a unique key for convenient purging.
- To know which we should remove or add, we want a simple function to diff a raw-text collection with vector db.
- A async lock to ensure mutation finished before searching.
"""
import asyncio
import json
from typing import *
from maica.maica_utils import *

class RagPersistentManager():
    """We try to write in SfPersistentManager style if possible."""

    session_id: Optional[int] = None

    def __init__(self, fsc: FullSocketsContainer, session_num: int=0):
        self.fsc = fsc

        self.user_id = fsc.maica_settings.verification.user_id
        self.session_num = session_num

    def _init_db(self):
        base_path = get_inner_path('fs_storage/rag')