"""Import layer 4"""
from typing import *
from dataclasses import dataclass, field
from websockets import ServerConnection
from pymilvus import AsyncMilvusClient
from Crypto.Random import random as crandom
from .maica_utils import *
from .setting_utils import MaicaSettings
from .fsc_early import RealtimeSocketsContainer, TracerayId
from .connection_utils import *

@dataclass
class ConnSocketsContainer():
    """Why so many connections."""
    auth_pool: Optional[DbPoolManager]=None
    maica_pool: Optional[DbPoolManager]=None
    vector_pool: Optional[MilvusDbConnectionManager]=None
    mcore_conn: Optional[AiConnectionManager]=None
    mfocus_conn: Optional[AiConnectionManager]=None
    mvista_conn: Optional[AiConnectionManager]=None
    mnerve_conn: Optional[AiConnectionManager]=None
    embedding_conn: Optional[AiConnectionManager]=None
    reranking_conn: Optional[AiConnectionManager]=None

    def spawn_sub(self, rsc=None):
        """Spawns a per-user sub instance."""
        sub_kwargs = {k: getattr(self, k).summon_sub(rsc) if getattr(self, k) else None for k in ['auth_pool', 'maica_pool', 'vector_pool', 'mcore_conn', 'mfocus_conn', 'mvista_conn', 'mnerve_conn']}
        return ConnSocketsContainer(**sub_kwargs)

@dataclass
class FullSocketsContainer():
    """
    For all convenience consideration.
    This is, like an important concept since it carries almost everything around.
    So when we add functions, we only need to pass in this. It's a live id card.
    """

    session: ClassVar[Optional[MaicaSession]]
    websocket: ClassVar[Optional[ServerConnection]]
    tracker_id: ClassVar[TracerayId]
    maica_settings: ClassVar[MaicaSettings]
    miscellaneous: dict = field(default_factory=lambda: {})
    """
    Why this?
    We want to add extra flexibility to fsc, especially things like session_rel.
    This way we easily track them through entire lifecycle. At least easier.
    Also this way we don't need to manage way too many classes and instances, like mfocus_sfe.
    If we implement mfocus_sfe as class for db + methods for build and sync, it might be prettier.
    """
    auth_pool: ClassVar[Optional[DbPoolManager]]
    maica_pool: ClassVar[Optional[DbPoolManager]]
    vector_pool: ClassVar[Optional[MilvusDbConnectionManager | AsyncMilvusClient]]
    mcore_conn: ClassVar[Optional[AiConnectionManager]]
    mfocus_conn: ClassVar[Optional[AiConnectionManager]]
    mvista_conn: ClassVar[Optional[AiConnectionManager]]
    mnerve_conn: ClassVar[Optional[AiConnectionManager]]
    embedding_conn: ClassVar[Optional[AiConnectionManager]]
    reranking_conn: ClassVar[Optional[AiConnectionManager]]

    rsc: Optional[RealtimeSocketsContainer]=None
    csc: Optional[ConnSocketsContainer]=None

    def __post_init__(self):
        if not self.rsc:
            self.rsc = RealtimeSocketsContainer()
        if not self.csc:
            self.csc = ConnSocketsContainer()

    rsc_proxied = ['session', 'websocket', 'tracker_id', 'maica_settings']
    csc_proxied = ['auth_pool', 'maica_pool', 'vector_pool', 'mcore_conn', 'mfocus_conn', 'mvista_conn', 'mnerve_conn', 'embedding_conn', 'reranking_conn']

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
