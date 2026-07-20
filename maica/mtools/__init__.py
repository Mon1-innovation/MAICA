
from maica.maica_utils import G

from .api_keys import TpAPIKeys
from .mpostal import make_postmail
from .mspire import make_inspire, ms_from_cache, ms_to_cache
from .weather_get import name_to_loc, weather_api_get
from .serp_get import internet_search
from .date_event_get import RegEvent, EventsCollection
from .post_proc import emo_proc, emo_proc_llm, emo_proc_auto, post_proc, zlist, elist
from .post_proc_rt import PPRTProcessor
from .nv_watcher import NvWatcher
from .mvista import ImgByUuid, query_vlm
from .quality_chk import quality_chk
from .censor import has_censored
from .memory_concl import memory_concl

__all__ = [
    'TpAPIKeys',
    'make_postmail',
    'make_inspire',
    'ms_from_cache',
    'ms_to_cache',
    'name_to_loc',
    'weather_api_get',
    'internet_search',
    'RegEvent',
    'EventsCollection',
    'emo_proc',
    'emo_proc_llm',
    'emo_proc_auto',
    'post_proc',
    'zlist',
    'elist',
    'PPRTProcessor',
    'NvWatcher',
    'ImgByUuid',
    'query_vlm',
    'quality_chk',
    'has_censored',
    'memory_concl',
    ]

from .mcp import pkg_init_mcp
from .api_keys import pkg_init_api_keys
from .providers import pkg_init_serp_provider
from .censor import pkg_init_censor
def pkg_init_mtools():
    pkg_init_api_keys()
    if not int(G.A.NO_SERP):
        pkg_init_mcp()
    pkg_init_serp_provider()
    pkg_init_censor()
