"""
Fuck it. I really don't wanna make a censor module but garbage information affecting 
MSpire forces me to.

Well, this module reads txt files in its directory (same level with this file), and 
each line is considered a censor pattern. These txt files are excluded from repository 
by default.

If any censor pattern parsed appear in check-pending text, the checking function will 
return matches, else empty set.
"""
import asyncio
import os
from flashtext import KeywordProcessor

from typing import *
from maica.maica_utils import *

try:
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

except Exception as e:
    sync_messenger(info=f"[maica-cnsr] Failed loading censor patterns: {str(e)}, ignoring and continuing", type=MsgType.WARN)

async def has_censored(text) -> list:
    """If there are censored words in text, or how many."""
    found = await wrap_run_in_exc(None, kp.extract_keywords, text)
    return set(found)

__all__ = ['has_censored']

if __name__ == "__main__":
    text = """
骄傲旗（英语：Pride flag）是代表LGBTQ的一部分的任何旗帜，“骄傲”一词指的是同志骄傲的概念，这个术语与“同志旗”和“酷儿旗”经常互换使用。
骄傲旗可以代表各种性取向、恋爱倾向、性别认同、酷儿文化、区域及整个LGBTQ社区，有些骄傲旗并非专门与LGBTQ相关，例如：皮革自豪之旗。代表整个LGBTQ社区的彩虹旗，是使用最广泛的其中一种骄傲旗。
许多社区采用不同的旗帜，其中大多数都从彩虹旗中汲取灵感。这些旗帜通常由业余设计师设计，并在网络或附属组织中逐渐受到关注，最终成为社区的象征性代表，取得半官方的地位。通常这些旗帜包含多种颜色，象征着包容相关社区的不同特性。
"""
    res = asyncio.run(has_censored(text))
    print(res)