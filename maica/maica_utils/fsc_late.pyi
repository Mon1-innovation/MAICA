from typing import *
from dataclasses import dataclass
from websockets import ServerConnection
from Crypto.Random import random as crandom
from maica.maica_utils import *
from .setting_utils import MaicaSettings
from .fsc_early import RealtimeSocketsContainer, TracerayId
from .connection_utils import DbPoolCoroutine, AiConnCoroutine

@dataclass
class ConnSocketsContainer():
    auth_pool: Optional[DbPoolCoroutine]
    maica_pool: Optional[DbPoolCoroutine]
    mcore_conn: Optional[AiConnCoroutine]
    mfocus_conn: Optional[AiConnCoroutine]
    mvista_conn: Optional[AiConnCoroutine]
    mnerve_conn: Optional[AiConnCoroutine]
    def spawn_sub(self, rsc: RealtimeSocketsContainer) -> ConnSocketsContainer:...

@dataclass
class FullSocketsContainer():
    rsc: Optional[RealtimeSocketsContainer]
    csc: Optional[ConnSocketsContainer]

    websocket: ClassVar[Optional[ServerConnection]]
    traceray_id: ClassVar[TracerayId]
    maica_settings: ClassVar[MaicaSettings]
    auth_pool: ClassVar[Optional[DbPoolCoroutine]]
    maica_pool: ClassVar[Optional[DbPoolCoroutine]]
    mcore_conn: ClassVar[Optional[AiConnCoroutine]]
    mfocus_conn: ClassVar[Optional[AiConnCoroutine]]
    mvista_conn: ClassVar[Optional[AiConnCoroutine]]
    mnerve_conn: ClassVar[Optional[AiConnCoroutine]]

    def __getattr__(self, k: str) -> any:...

    def __setattr__(self, k: str, v: any) -> any:...