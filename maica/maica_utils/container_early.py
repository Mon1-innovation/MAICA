"""Import layer 2.5"""
from typing import *
from dataclasses import dataclass
from websockets import ServerConnection
from Crypto.Random import random as crandom
from .setting_utils import MaicaSettings

class TracerayId():
    """String-like."""
    var: str=''
    def __init__(self):
        self.var = str(crandom.randint(0,9999999999)).zfill(10)
    def rotate(self):
        self.__init__()
    def __str__(self):
        return self.var

@dataclass
class RealtimeSocketsContainer():
    """For no-setting usage."""
    websocket: Optional[ServerConnection]=None
    traceray_id: TracerayId=None
    maica_settings: MaicaSettings=None

    def __post_init__(self):
        if not self.traceray_id:
            self.traceray_id = TracerayId()
        if not self.maica_settings:
            self.maica_settings = MaicaSettings()

    def rotate_tid(self):
        """Rotate traceray_id."""
        self.traceray_id = TracerayId()