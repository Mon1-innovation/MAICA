import random

from typing import *
from pydantic import BaseModel, Field, model_validator
from maica.maica_utils import *
from maica.mtools.api_keys import TpAPIKeys

_providers_raw: List[Tuple[int, List[str], Awaitable]] = []
_providers_initialized = False
_providers = []

class SerpResults(BaseModel):

    class SerpItem(BaseModel):
        title: str
        description: str
        rank: Optional[int] = None
        link: Optional[str] = None
        source: Optional[str] = None

    results: RobustList[SerpItem]

def register_provider(prio: int, requires: List[str], asearch):
    _providers_raw.append((prio, requires, asearch))

def get_providers():
    global _providers_initialized
    if not _providers_initialized:
        for p in _providers_raw:
            prio, requires, asearch = p
            try:
                for r in requires:
                    if not getattr(TpAPIKeys, r):
                        raise ValueError(f"{r} not configured")
                _providers.append((prio, asearch))
            except (ValueError, AttributeError) as e:
                sync_messenger(info=f"[maica-serp] Provider {prio} not available: {e}", type=MsgType.DEBUG)
        _providers_initialized = True
    return sorted(_providers, key=lambda x: x[0])

@overload
async def asearch(query: str, target_lang: Literal['zh', 'en', 'auto']) -> SerpResults:...

available_list: list[tuple[int, asearch]] = []
last_used = -1

def get_asearch(avoid: Union[Literal['last'], int]=None, rand: bool=False) -> Callable[[str, str], Coroutine[Any, Any, SerpResults]]:
    global available_list, last_used

    if avoid == 'last':
        avoid = last_used

    avail_temp = [e for e in available_list if e[0] != avoid]
    if not avail_temp:
        avail_temp = available_list
    if rand:
        selected = random.choice(avail_temp) if avail_temp else (-1, None)
    else:
        selected = avail_temp[0] if avail_temp else (-1, None)

    last_used = selected[0]
    asearch = selected[1]

    return asearch
