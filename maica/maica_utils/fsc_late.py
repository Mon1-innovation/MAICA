"""Import layer 4"""
from typing import *
from pydantic import BaseModel, Field, model_validator
from pydantic.dataclasses import dataclass as pdataclass
from websockets import ServerConnection
from pymilvus import AsyncMilvusClient
from .maica_utils import *
from .setting_utils import MaicaSettings
from .fsc_early import AllowArb, RealtimeSocketsContainer, TrackerId
from .connection_utils import *
from .users_utils import FscUsersFuncMixin


class ConnSocketsContainer(AllowArb):
    """Why so many connections."""
    vector_pool: Optional[MilvusDbConnectionManager]=None
    mcore_conn: Optional[AiConnectionManager]=None
    mfocus_conn: Optional[AiConnectionManager]=None
    mvista_conn: Optional[AiConnectionManager]=None
    mnerve_conn: Optional[AiConnectionManager]=None
    embedding_conn: Optional[AiConnectionManager]=None
    reranking_conn: Optional[AiConnectionManager]=None

    def spawn_sub(self, rsc=None):
        """Spawns a per-user sub instance."""
        sub_kwargs = {k: getattr(self, k) if getattr(self, k) else None for k in _csc_proxied}
        return ConnSocketsContainer(**sub_kwargs)

    @property
    def is_vector_ready(self):
        return bool(
            self.vector_pool
            and self.embedding_conn
        )
    
    @property
    def is_reranking_ready(self):
        return bool(
            self.reranking_conn
            and self.is_vector_ready
        )


_rsc_proxied = ['websocket', 'tracker_id', 'messenger', 'maica_settings']
_csc_proxied = [
    'vector_pool', 'mcore_conn', 'mfocus_conn', 'mvista_conn', 'mnerve_conn', 'embedding_conn', 'reranking_conn',
    'is_vector_ready', 'is_reranking_ready',
    ]

class FullSocketsContainer(FscUsersFuncMixin, AllowArb):
    """
    For all convenience consideration.
    This is, like an important concept since it carries almost everything around.
    So when we add functions, we only need to pass in this. It's a live id card.
    """

    # Discarded, do not use
    # session: ClassVar[Optional[MaicaSession]]
    
    websocket: ClassVar[Optional[ServerConnection]]
    tracker_id: ClassVar[TrackerId]
    messenger: ClassVar[RealtimeSocketsContainer.RscMessenger]
    maica_settings: ClassVar[MaicaSettings]
    # Discarded, do not use
    # miscellaneous: dict = field(default_factory=lambda: {})

    vector_pool: ClassVar[Optional[MilvusDbConnectionManager | AsyncMilvusClient]]
    mcore_conn: ClassVar[Optional[AiConnectionManager]]
    mfocus_conn: ClassVar[Optional[AiConnectionManager]]
    mvista_conn: ClassVar[Optional[AiConnectionManager]]
    mnerve_conn: ClassVar[Optional[AiConnectionManager]]
    embedding_conn: ClassVar[Optional[AiConnectionManager]]
    reranking_conn: ClassVar[Optional[AiConnectionManager]]

    rsc: Optional[RealtimeSocketsContainer]=None
    csc: Optional[ConnSocketsContainer]=None

    @model_validator(mode="after")
    def auto_init(self):
        if not self.rsc:
            self.rsc = RealtimeSocketsContainer()
        if not self.csc:
            self.csc = ConnSocketsContainer()
        return self

    def __getattr__(self, k):
        if k in _rsc_proxied:
            return getattr(self.rsc, k)
        elif k in _csc_proxied:
            return getattr(self.csc, k)
        else:
            return super().__getattr__(k)

    def __setattr__(self, k, v):
        if k in _rsc_proxied:
            setattr(self.rsc, k, v)
        elif k in _csc_proxied:
            setattr(self.csc, k, v)
        else:
            super().__setattr__(k, v)
    
    @property
    def real_sf_access_impl(self):
        match self.maica_settings.extra.mf_sf_access_impl:
            case 1 if self.is_reranking_ready:
                return 1
            case 2 if self.is_vector_ready:
                return 2
            case _:
                return 0
