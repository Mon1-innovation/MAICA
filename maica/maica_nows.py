import asyncio
import json
import orjson

from typing import *
from Crypto.Random import random as crandom

from maica.mtools import ProcessingImg
from maica.mfocus import MFocusManager, SfPersistentManager
from maica.mtrigger import MTriggerManager, MtPersistentManager
from maica.maica_utils import *

class NoWsCoroutine(AsyncCreator):
    """
    Not actually no-ws, but ws can be None.
    Also no AI socket.
    """

    # To be populated or not
    sf_inst: Optional[SfPersistentManager] = None
    mt_inst: Optional[MtPersistentManager] = None
    mfocus_coro: Optional[MFocusManager] = None
    mtrigger_coro: Optional[MTriggerManager] = None

    # Initialization

    def __init__(
            self,
            fsc: FullSocketsContainer
        ):
        self.fsc = fsc
        self.auth_pool = fsc.auth_pool
        self.maica_pool = fsc.maica_pool
        self.websocket = fsc.websocket
        self.traceray_id = fsc.traceray_id
        self.settings = fsc.maica_settings
        self.sessions: Dict[int, MaicaSession] = {}
        self.remote_addr = None

    async def _ainit(self):
        self.hasher = await AccountCursor.async_create(self.settings, self.auth_pool, self.maica_pool)

    def _check_essentials(self) -> None:
        if not self.settings.verification.user_id:
            raise MaicaPermissionError('Essentials not complete', '403', 'common_essentials_missing')

    # Here we have V2 session methods
    def acquire_session(self, session_num) -> MaicaSession | List[MaicaSessionItem]:
        self._check_essentials()
        session_num = int(session_num)
        assert -1 <= session_num < 10, "Determined session_num out of range"

        # Ensure it exists in index
        if not session_num in self.sessions.keys():
            self.sessions[session_num] = MaicaSession()
            session = self.sessions[session_num]

        match session_num:
            case -1 | 0:
                # Disposable sessions
                session.clear()
                return session
            case _:
                # Persistent sessions
                session.user_id = self.settings.verification.user_id
                session.session_num = session_num
                session.fsc = self.fsc
                return session

    async def find_ms_cache(self, hash: str) -> Optional[str]:
        """Find ms cache with corresponding prompt hash."""

        sql_expression_1 = "SELECT content FROM ms_cache WHERE hash = %s"
        result = await self.maica_pool.query_get(expression=sql_expression_1, values=(hash, ))
        if result:
            await messenger(None, 'maica_spire_cache_hit', 'Hit a stored cache for MSpire', '200')
            return result[0]
        else:
            await messenger(None, 'maica_spire_cache_missed', 'No stored cache for MSpire', '200')
            return None

    async def store_ms_cache(self, hash: str, content: str) -> int:
        """Store ms cache with prompt hash."""
        self._check_essentials()

        sql_expression_1 = "INSERT INTO ms_cache (user_id, hash, content) VALUES (%s, %s, %s)"
        spire_id = (await self.maica_pool.query_modify(expression=sql_expression_1, values=(self.settings.verification.user_id, hash, content)))[1]
        await messenger(None, 'maica_spire_cache_stored', 'Stored a cache for MSpire', '200')
        return spire_id

    @overload
    async def delete_mv(self, input: str) -> None:
        """Delete mv according to uuid."""

    @overload
    async def delete_mv(self, input: int) -> None:
        """Delete mv according to per-user sequence (from 0)."""

    async def delete_mv(self, input) -> None:
        """Delete a mv meta and try to delete its file."""
        self._check_essentials()
        if isinstance(input, int):
            assert input < int(G.A.KEEP_MVISTA), f"Sequence must be smaller than {G.A.KEEP_MVISTA}"
            uuids = [(await self.list_user_mv())[input]]
        elif isinstance(input, str):
            uuids = [input]
        else:
            uuids = await self.list_user_mv()
        
        for uuid in uuids:
            processing_img = ProcessingImg()
            processing_img.det_path(uuid)

            sql_expression_1 = "SELECT vista_id FROM mv_meta WHERE user_id = %s AND uuid = %s"
            result = await self.maica_pool.query_get(expression=sql_expression_1, values=(self.settings.verification.user_id, uuid))
            if not result:
                raise MaicaInputWarning(f'{uuid} not available for this account')
            vista_id = result[0]

            processing_img.delete()
            sql_expression_2 = "DELETE FROM mv_meta WHERE vista_id = %s"
            await self.maica_pool.query_modify(expression=sql_expression_2, values=(vista_id, ))
        
    async def store_mv(self, input: bytes) -> int:
        """Register a mv meta and store as file."""

        async def delete_mv_if_exceeds():
            """Empties one slot for storage."""
            nonlocal self
            mvs = await self.list_user_mv()
            mv_count = len(mvs)
            if mv_count >= int(G.A.KEEP_MVISTA):
                for i in mvs[int(G.A.KEEP_MVISTA) - 1:]:
                    await self.delete_mv(i)

        self._check_essentials()
        await delete_mv_if_exceeds()

        processing_img = ProcessingImg(input)
        uuid = processing_img.det_path()
        
        sql_expression_1 = "INSERT INTO mv_meta (user_id, uuid) VALUES (%s, %s)"
        vista_id = (await self.maica_pool.query_modify(expression=sql_expression_1, values=(self.settings.verification.user_id, uuid)))[1]
        processing_img.save()

        return uuid
    
    async def list_user_mv(self) -> list[str]:
        """List current user's available mvs."""
        self._check_essentials()

        sql_expression_1 = "SELECT uuid FROM mv_meta WHERE user_id = %s ORDER BY timestamp DESC"
        result = await self.maica_pool.query_get(expression=sql_expression_1, values=(self.settings.verification.user_id, ), fetchall=True)
        result_list = [l[0] for l in result]
        return result_list

    async def populate_auxiliary_inst(self) -> None:
        self.sf_inst, self.mt_inst = await asyncio.gather(SfPersistentManager.async_create(self.fsc), MtPersistentManager.async_create(self.fsc))
        self.mfocus_coro, self.mtrigger_coro = await asyncio.gather(MFocusManager.async_create(self.fsc, self.sf_inst, self.mt_inst), MTriggerManager.async_create(self.fsc, self.mt_inst, self.sf_inst))

    async def reset_auxiliary_inst(self) -> None:
        sb_list = []
        for sb_name in ['sf_inst', 'mt_inst', 'mfocus_coro', 'mtrigger_coro']:
            sb = getattr(self, sb_name, None)
            if sb:
                sb_list.append(sb.reset())
        await asyncio.gather(*sb_list)

    async def hash_and_login(self, access_token: str=None, logged_in_already: bool=False, check_online: bool=False) -> bool:
        """Use this to login a NoWs instance."""
        if not logged_in_already:
            verification_result = await self.hasher.hashing_verify(access_token)
        else:
            verification_result = [True, None]
        if verification_result[0]:

            # Account security check
            banned = await self.hasher.is_banned()
            if banned:
                raise MaicaPermissionError('Account banned by MAICA', '403', 'maica_account_banned')

            # Cridential correct and not banned
            if check_online and not logged_in_already:
                if self.settings.verification.user_id in online_dict:
                    if G.A.KICK_STALE_CONNS != "1":
                        self.settings.verification.reset()
                        raise MaicaConnectionWarning('A connection was established already and kicking not enabled', '406', 'maica_connection_reuse_denied')
                    else:
                        await messenger(self.websocket, "maica_connection_reuse_attempt", "A connection was established already", "300", self.traceray_id)
                        stale_fsc, stale_lock = online_dict[self.settings.verification.user_id]
                        try:
                            await messenger(stale_fsc.rsc.websocket, 'maica_connection_reuse_stale', 'A new connection has been established', '300', stale_fsc.rsc.traceray_id)
                            await stale_fsc.rsc.websocket.close(1000, 'Displaced as stale')
                        except Exception:
                            await messenger(None, 'maica_connection_stale_dead', 'The stale connection has died already', '204')
                        try:
                            online_dict.pop(self.settings.verification.user_id)
                        except Exception:
                            pass
                        async with stale_lock:
                            await messenger(None, 'maica_connection_stale_kicked', 'The stale connection is kicked', '204')
            return True

        else:
            if isinstance(verification_result[1], dict):
                if 'f2b' in verification_result[1]:
                    raise MaicaPermissionError(f'Account locked by Fail2Ban, {verification_result[1]['f2b']} seconds remaining', '429', 'maica_login_denied_fail2ban')
                elif 'necf' in verification_result[1]:
                    raise MaicaPermissionWarning(f'Account Email not verified, check inbox and retry', '401', 'maica_login_denied_email')
                elif 'pwdw' in verification_result[1]:
                    raise MaicaPermissionWarning(f'Password hashing failed {verification_result[1]['pwdw']} times, check password and retry', '403', 'maica_login_denied_password')
            elif isinstance(verification_result[1], CommonMaicaException):
                raise verification_result[1]
            else:
                raise MaicaPermissionWarning(verification_result[1], '400', 'maica_login_denied_rsa')
        return False
    
if __name__ == "__main__":
    pass