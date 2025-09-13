from typing import *
from maica.maica_utils import *
from .setting_utils import *
from .connection_utils import *
"""Import layer 4"""

class FullSocketsContainer():
    """For convenience consideration."""
    class RealtimeSocketsContainer():
        """For no-setting usage."""
        def __init__(self, websocket=None, traceray_id=''):
            self.websocket, self.traceray_id = websocket, traceray_id
    
    def __init__(self, websocket=None, traceray_id='', maica_settings=None, auth_pool=None, maica_pool=None, mcore_conn=None, mfocus_conn=None):
        self.rsc = self.RealtimeSocketsContainer(websocket, traceray_id)
        self.maica_settings: MaicaSettings = maica_settings() if not maica_settings else maica_settings
        self.auth_pool: Optional[DbPoolCoroutine] = auth_pool
        self.maica_pool: Optional[DbPoolCoroutine] = maica_pool
        self.mcore_conn: Optional[AiConnCoroutine] = mcore_conn
        self.mfocus_conn: Optional[AiConnCoroutine] = mfocus_conn