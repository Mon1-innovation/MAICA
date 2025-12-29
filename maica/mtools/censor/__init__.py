"""
Fuck it. I really don't wanna make a censor module but garbage information affecting 
MSpire forces me to.

Well, this module reads txt files in its directory (same level with this file), and 
each line is considered a censor pattern. These txt files are excluded from repository 
by default.

If any censor pattern parsed appear in check-pending text, the checking function will 
return matches.
"""
import asyncio
import os
from flashtext import KeywordProcessor

from typing import *
from maica.maica_utils import *

base_path = get_inner_path('mtools/censor')
censor_file_entries = os.scandir(base_path)
censor_set = set()
for entry in censor_file_entries:
    if entry.is_file() and entry.name.endswith('.txt'):
        with open(entry.path, 'r') as file:
            censor_set.update(file.read().splitlines())

kp = KeywordProcessor()
for kw in censor_set:
    kp.add_keyword(kw)

sync_messenger(info=f"[maica-cnsr] Loaded censor patterns: {len(censor_set)}", type=MsgType.DEBUG)

async def has_censored(text) -> list:
    """If there are censored words in text, or how many."""
    found = await wrap_run_in_exc(None, kp.extract_keywords, text)
    return set(found)

__all__ = ['has_censored']