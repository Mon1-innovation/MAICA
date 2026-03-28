from typing import *
from maica.maica_utils import *
from maica.mtools.api_keys import TpAPIKeys

_providers_raw: List[Tuple[int, List[str], Awaitable]] = []
_providers_initialized = False
_providers = []

def register_provider(prio: int, requires: List[str], asearch):
    _providers_raw.append((prio, requires, asearch))

def get_providers():
    global _providers_initialized
    if not _providers_initialized:
        for p in _providers_raw:
            prio, requires, asearch = p
            try:
                for r in requires:
                    assert getattr(TpAPIKeys, r), f"{r} not exist"
                _providers.append((prio, asearch))
            except (AssertionError, AttributeError) as e:
                sync_messenger(info=f"[maica-serp] Provider {prio} not available: {e}", type=MsgType.DEBUG)
        _providers_initialized = True
    return sorted(_providers, key=lambda x: x[0])