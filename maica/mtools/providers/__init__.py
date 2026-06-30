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
from maica.maica_utils import *
from .base import SerpResults, get_providers, get_asearch, available_list
from . import _activator

def pkg_init_serp_provider():
    global available_list
    if G.A.NO_SERP != '1':
        available_list = get_providers()
    sync_messenger(info=f"[maica-serp] Available SERP providers: {', '.join([str(i[0]) for i in available_list]) or None}", type=MsgType.DEBUG)

__all__ = [
    'SerpResults',
    'get_asearch',
]