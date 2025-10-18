"""Import layer 4"""
from typing import *
from dataclasses import dataclass
from websockets import ServerConnection
from Crypto.Random import random as crandom
from maica.maica_utils import *
from .setting_utils import *
from .container_early import *
from .connection_utils import *

def create_slink(name: str, inner: str):
    """Just like a symlink."""
    def getter(self):
        return getattr(getattr(self, inner), name)
    def setter(self, v: any):
        setattr(getattr(self, inner), name, v)
    return property(getter, setter)

@dataclass
class ConnSocketsContainer():
    """Why so many connections!!!"""
    auth_pool: Optional[DbPoolCoroutine]=None
    maica_pool: Optional[DbPoolCoroutine]=None
    mcore_conn: Optional[AiConnCoroutine]=None
    mfocus_conn: Optional[AiConnCoroutine]=None
    mvista_conn: Optional[AiConnCoroutine]=None
    mnerve_conn: Optional[AiConnCoroutine]=None

    def spawn_sub(self, rsc=None):
        """Spawns a per-user sub instance."""
        sub_kwargs = {k: getattr(self, k).summon_sub(rsc) if getattr(self, k) else None for k in ['auth_pool', 'maica_pool', 'mcore_conn', 'mfocus_conn', 'mvista_conn', 'mnerve_conn']}
        return ConnSocketsContainer(**sub_kwargs)

@dataclass
class FullSocketsContainer():
    """For all convenience consideration."""
    rsc: Optional[RealtimeSocketsContainer]=None
    csc: Optional[ConnSocketsContainer]=None

    rsc_proxied = ['websocket', 'traceray_id', 'maica_settings']
    csc_proxied = ['auth_pool', 'maica_pool', 'mcore_conn', 'mfocus_conn', 'mvista_conn', 'mnerve_conn']

    # websocket: ClassVar[Optional[ServerConnection]] = None
    # traceray_id: ClassVar[TracerayId] = None
    # maica_settings: ClassVar[MaicaSettings] = None
    # auth_pool: ClassVar[Optional[AiConnCoroutine]] = None
    # maica_pool: ClassVar[Optional[AiConnCoroutine]] = None
    # mcore_conn: ClassVar[Optional[AiConnCoroutine]] = None
    # mfocus_conn: ClassVar[Optional[AiConnCoroutine]] = None
    # mvista_conn: ClassVar[Optional[AiConnCoroutine]] = None
    # mnerve_conn: ClassVar[Optional[AiConnCoroutine]] = None

    def __getattr__(self, k):
        if k in self.rsc_proxied:
            return getattr(self.rsc, k)
        elif k in self.csc_proxied:
            return getattr(self.csc, k)
        else:
            return super().__getattr__(k)

    def __setattr__(self, k, v):
        if k in self.rsc_proxied:
            setattr(self.rsc, k, v)
        elif k in self.csc_proxied:
            setattr(self.csc, k, v)
        else:
            super().__setattr__(k, v)
