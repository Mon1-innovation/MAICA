"""
SERP is really complex if you don't use google's super expensive api, so I made this.

This searches submodules in its folder at a priority sequence from 0 to 99, and adopts 
the first module that implements a valid 'asearch' function with optional 'requires'.

'asearch' must accept (query, target_lang), and returns a list[dict[#type, #content]]. This 
implementation will only take effect if all items in 'requires' exist in TpAPIKeys.

The local solution is not stable and efficient enough, so I might be using some third-
party apis. They're not ads.

You can always implement your own SERP function by adding a submodule with higher priority 
(smaller number).
"""
import importlib
import random
from typing import *
from collections.abc import Callable
from maica.maica_utils import *
from maica.mtools.api_keys import TpAPIKeys

@overload
async def asearch(query: str, target_lang: Literal['zh', 'en']) -> list[dict[Literal['title', 'text'], Annotated[str, Desc('Content')]]]:...

available_list: list[tuple[int, Callable]]
last_used = -1

def pkg_init_serp_provider():
    global available_list
    serp_provider = None; asearch = None; requires = None
    available_list = []

    if G.A.NO_SERP != '1':
        for prio in range(0, 100):
            modname = f".serp_provider_{prio}"
            try:
                serp_provider = importlib.import_module(modname, "maica.mtools.providers")
                asearch = serp_provider.asearch; requires = serp_provider.requires
                for r in requires:
                    assert getattr(TpAPIKeys, r)
                available_list.append((prio, asearch))
            except Exception:...
    sync_messenger(info=f"[maica-serp] Available SERP providers: {', '.join([str(i[0]) for i in available_list]) or None}", type=MsgType.DEBUG)

def get_asearch(avoid: Union[Literal['last'], int]=None, rand: bool=False) -> Callable:
    global last_used

    if avoid == 'last':
        avoid = last_used

    avail_temp = [e for e in available_list if e[0] != avoid]
    if not avail_temp:
        avail_temp = available_list
    if rand:
        selected = random.choice(avail_temp) if avail_temp else (-1, None)
    else:
        selected = avail_temp[0] if avail_temp else (-1, None)

    last_used = selected[0]; asearch = selected[1]

    return asearch

# Normally you should not do 'from provider import ...' to keep it dynamic
__all__ = ['get_asearch']