from typing import *
from dataclasses import dataclass
from websockets import ServerConnection
from Crypto.Random import random as crandom
from maica.maica_utils import *
from .setting_utils import MaicaSettings
from .fsc_early import RealtimeSocketsContainer, TracerayId
from .connection_utils import DbPoolManager, AiConnectionManager

@dataclass
class ConnSocketsContainer():
    auth_pool: Optional[DbPoolManager]
    maica_pool: Optional[DbPoolManager]
    mcore_conn: Optional[AiConnectionManager]
    mfocus_conn: Optional[AiConnectionManager]
    mvista_conn: Optional[AiConnectionManager]
    mnerve_conn: Optional[AiConnectionManager]
    def spawn_sub(self, rsc: RealtimeSocketsContainer) -> ConnSocketsContainer:...

@dataclass
class FullSocketsContainer():
    rsc: Optional[RealtimeSocketsContainer]
    csc: Optional[ConnSocketsContainer]

    websocket: ClassVar[Optional[ServerConnection]]
    traceray_id: ClassVar[TracerayId]
    maica_settings: ClassVar[MaicaSettings]
    auth_pool: ClassVar[Optional[DbPoolManager]]
    maica_pool: ClassVar[Optional[DbPoolManager]]
    mcore_conn: ClassVar[Optional[AiConnectionManager]]
    mfocus_conn: ClassVar[Optional[AiConnectionManager]]
    mvista_conn: ClassVar[Optional[AiConnectionManager]]
    mnerve_conn: ClassVar[Optional[AiConnectionManager]]

    def __getattr__(self, k: str) -> any:...

    def __setattr__(self, k: str, v: any) -> any:...