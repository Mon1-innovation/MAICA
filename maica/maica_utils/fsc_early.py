"""Import layer 2.5"""
import colorama
from typing import *
from functools import partial
from dataclasses import dataclass, field
from websockets import ServerConnection, WebSocketException
from Crypto.Random import random as crandom
from .setting_utils import MaicaSettings
from .maica_utils import *

if TYPE_CHECKING:
    from maica.maica_utils import *
else:
    class MaicaSession(): ...
    class RealtimeSocketsContainer(): ...

class TrackerId():
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
    class RscMessenger():
        """
        A wrapped messenger.
        We're making this since passing websocket and things is too troublesome.
        And also, there're places we need a buffered messenger. This is better.
        """
        def __init__(self, parent: RealtimeSocketsContainer):
            self._parent = parent
            self._w_buffer = None
            self._acom = None
            self.ws_died: Optional[Exception] = None
            """We store it here for convenience."""

        async def acquire_buffer(self):
            self._acom = acquire_buffer(self._parent.maica_settings.verification.user_id)
            self._w_buffer = await self._acom.__aenter__()
            self._w_buffer.clear()

        async def release_buffer(self):
            """Always execute to release resource!"""
            if len(self._w_buffer):
                self._w_buffer.kill()

            self._w_buffer = None
            if self._acom:
                await self._acom.__aexit__(None, None, None)
            self._acom = None

            if self.ws_died:
                raise self.ws_died

        async def exhaust_buffer(self):
            """Send all buffered msgs to current websocket connection."""
            user_id = self._parent.maica_settings.verification.user_id
            r_buffer = no_lock_acquire_buffer(user_id)
            websocket = self._parent.websocket

            # If the buffer is not occupied and being empty, there's nothing to read.
            if (
                not r_buffer.lock.locked()
                and not len(r_buffer)
            ):
                await self.__call__(
                    'maica_reconn_buffer_empty',
                    f"Reconnection buffer not present for user id {user_id}.",
                    204,
                )

            else:
                await self.__call__(
                    'maica_reconn_buffer_started',
                    f"Reconnection buffer started for user id {user_id}",
                    200,
                    # type=MsgType.INFO,
                )

                sent = 0
                async for ws_packet in r_buffer:
                    # There could be a None
                    if ws_packet:
                        sent += 1
                        await websocket.send(wrap_ws_formatter(*ws_packet))
                
                await self.__call__(
                    'maica_reconn_buffer_drained',
                    f"Reconnection buffer drained for user id {user_id}, {sent} packets sent",
                    200,
                    # type=MsgType.INFO,
                )

        async def __call__(
                self,
                status: str = '',
                info: str = '',
                code: int = 0,
                **kwargs,
            ):
            """These default values are for directly passing exception."""
            websocket = self._parent.websocket
            tracker_id = self._parent.tracker_id
            if not self.ws_died:
                try:
                    await messenger(
                        websocket=self._parent.websocket,
                        status=status,
                        info=info,
                        code=code,
                        tracker_id=self._parent.tracker_id,
                        **kwargs
                    )
                except WebSocketException as we:
                    # The connection terminated unexpectedly
                    if not self._w_buffer:
                        raise we
                    else:
                        self.ws_died = we
                        sync_messenger(info=f"<{tracker_id}WS_DIED, storing remaining to buffer>", type=MsgType.PLAIN, color=colorama.Fore.LIGHTYELLOW_EX)

            if self.ws_died:
                ws_packet = sync_messenger(
                    status=status,
                    info=info,
                    code=code,
                    tracker_id=self._parent.tracker_id,
                    **kwargs
                )
                self._w_buffer.put_nowait(ws_packet)

    session: Optional[MaicaSession] = None
    websocket: Optional[ServerConnection] = None
    tracker_id: TrackerId = field(default_factory=TrackerId)
    messenger: Optional[RscMessenger] = None
    maica_settings: MaicaSettings = field(default_factory=MaicaSettings)

    def __post_init__(self):
        if not self.messenger:
            self.messenger = self.RscMessenger(self)

    def rotate_tid(self):
        """Rotate tracker_id."""
        self.tracker_id.rotate()