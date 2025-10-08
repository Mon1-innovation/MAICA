
from .mpostal import make_postmail
from .mspire import make_inspire
from .wiki_scraping import get_page
from .weather_scraping import weather_api_get
from .enet_scraping import internet_search
from .ev_scraping import RegEvent, EventsCollection
from .post_proc import emo_proc, post_proc, zlist, elist
from .nv_watcher import NvWatcher

__all__ = [
    'make_postmail',
    'make_inspire',
    'weather_api_get',
    'internet_search',
    'RegEvent',
    'EventsCollection',
    'emo_proc',
    'post_proc',
    'zlist',
    'elist',
    'NvWatcher',
    ]

from .mcp import pkg_init_mcp
def pkg_init_mtools():
    pkg_init_mcp()