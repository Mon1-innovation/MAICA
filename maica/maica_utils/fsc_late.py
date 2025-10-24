"""Import layer 4"""
from typing import *
from dataclasses import dataclass
from websockets import ServerConnection
from Crypto.Random import random as crandom
from maica.maica_utils import *
from .setting_utils import MaicaSettings
from .fsc_early import RealtimeSocketsContainer, TracerayId
from .connection_utils import DbPoolManager, AiConnectionManager

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
    auth_pool: Optional[DbPoolManager]=None
    maica_pool: Optional[DbPoolManager]=None
    mcore_conn: Optional[AiConnectionManager]=None
    mfocus_conn: Optional[AiConnectionManager]=None
    mvista_conn: Optional[AiConnectionManager]=None
    mnerve_conn: Optional[AiConnectionManager]=None

    def spawn_sub(self, rsc=None):
        """Spawns a per-user sub instance."""
        sub_kwargs = {k: getattr(self, k).summon_sub(rsc) if getattr(self, k) else None for k in ['auth_pool', 'maica_pool', 'mcore_conn', 'mfocus_conn', 'mvista_conn', 'mnerve_conn']}
        return ConnSocketsContainer(**sub_kwargs)

@dataclass
class FullSocketsContainer():
    """For all convenience consideration."""
    rsc: Optional[RealtimeSocketsContainer]=None
    csc: Optional[ConnSocketsContainer]=None

    def __post_init__(self):
        if not self.rsc:
            self.rsc = RealtimeSocketsContainer()
        if not self.csc:
            self.csc = ConnSocketsContainer()

    rsc_proxied = ['websocket', 'traceray_id', 'maica_settings']
    csc_proxied = ['auth_pool', 'maica_pool', 'mcore_conn', 'mfocus_conn', 'mvista_conn', 'mnerve_conn']

    # websocket: ClassVar[Optional[ServerConnection]] = None
    # traceray_id: ClassVar[TracerayId] = None
    # maica_settings: ClassVar[MaicaSettings] = None
    # auth_pool: ClassVar[Optional[AiConnectionManager]] = None
    # maica_pool: ClassVar[Optional[AiConnectionManager]] = None
    # mcore_conn: ClassVar[Optional[AiConnectionManager]] = None
    # mfocus_conn: ClassVar[Optional[AiConnectionManager]] = None
    # mvista_conn: ClassVar[Optional[AiConnectionManager]] = None
    # mnerve_conn: ClassVar[Optional[AiConnectionManager]] = None

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
