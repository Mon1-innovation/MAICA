import asyncio
import json

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
        self.auth_pool = fsc.auth_pool
        self.maica_pool = fsc.maica_pool
        self.websocket = fsc.websocket
        self.traceray_id = fsc.traceray_id
        self.settings = fsc.maica_settings
        self.remote_addr = None

    async def _ainit(self):
        self.hasher = await AccountCursor.async_create(self.settings, self.auth_pool, self.maica_pool)

    def _check_essentials(self) -> None:
        if not self.settings.verification.user_id:
            raise MaicaPermissionError('Essentials not complete', '403', 'common_essentials_missing')

    async def _create_session(self, user_id=None, chat_session_num=None, content=None) -> int:
        user_id = self.settings.verification.user_id if not user_id else user_id
        chat_session_num = self.settings.temp.chat_session if not chat_session_num else chat_session_num
        sql_expression = "INSERT INTO chat_session (user_id, chat_session_num, content) VALUES (%s, %s, %s)"
        return await self.maica_pool.query_modify(expression=sql_expression, values=(user_id, chat_session_num, content))

    async def _jsonify_chat_session(self, text) -> list:
        try:
            if text:
                return json.loads(f'[{text}]')
            else:
                return []
        except Exception as e:
            raise MaicaDbError(f'Chat session not JSON', '500', 'maica_db_corruption') from e

    def _flattern_chat_session(self, content_json: list) -> str:
        if content_json:
            return json.dumps(content_json, ensure_ascii=False).strip('[').strip(']')
        else:
            return None

    async def _try_repair_chat_session(self, text) -> list:
        """Therotically shouldn't happen."""
        text = text.strip(', ').strip(' ,')
        content_json = await self._jsonify_chat_session(text)
        if content_json[0]['role'] != 'system':
            content_json.insert(0, {"role": "system", "content": await self.gen_system_prompt()})
        while content_json[1]['role'] != 'user':
            content_json.pop(1)
        return content_json

    async def _crop_session(self, chat_session_id, content) -> tuple[int, str]:
        max_length_ascii = self.settings.basic.max_length * 3
        warn_length_ascii = int(max_length_ascii * (2/3))
        len_content_actual = len(content.encode()) - len(json.loads(f'[{content}]')) * 31
        if len_content_actual >= max_length_ascii:

            # First we check if there is a cchop avaliable
            sql_expression_1 = 'SELECT archive_id, content FROM crop_archived WHERE chat_session_id = %s AND archived = 0'
            result = await self.maica_pool.query_get(expression=sql_expression_1, values=(chat_session_id, ))
            if result:
                archive_id, archive_content = result
            else:
                archive_id = None; archive_content = ''

            cutting_mat = json.loads(f"[{content}]")
            while len_content_actual >= warn_length_ascii or cutting_mat[1]['role'] == "assistant":
                # Since pos 0 is reserved for system
                if archive_content:
                    archive_content = archive_content + ', '
                popped_dict = cutting_mat.pop(1)
                archive_content = archive_content + json.dumps(popped_dict, ensure_ascii=False)
                len_content_actual -= (len(json.dumps(popped_dict, ensure_ascii=False).encode()) - 31)
            content = self._flattern_chat_session(cutting_mat)

            if archive_id:
                sql_expression_2 = "UPDATE crop_archived SET content = %s WHERE archive_id = %s" if len(archive_content) <= 100000 else "UPDATE crop_archived SET content = %s, archived = 1 WHERE archive_id = %s"
                await self.maica_pool.query_modify(expression=sql_expression_2, values=(archive_content, archive_id))
            else:
                sql_expression_2 = "INSERT INTO crop_archived (chat_session_id, content, archived) VALUES (%s, %s, 0)" if len(archive_content) <= 100000 else "INSERT INTO crop_archived (chat_session_id, content, archived) VALUES (%s, %s, 1)"
                await self.maica_pool.query_modify(expression=sql_expression_2, values=(chat_session_id, archive_content))

            cut_status = 1
        elif len_content_actual >= warn_length_ascii:
            cut_status = 2
        else:
            cut_status = 0
        return cut_status, content
    
    @overload
    async def rw_chat_session(self, irwa: Literal['i', 'r']='r', content_append: list=None, system_prompt: str=None, chat_session_num=None) -> tuple[int, list]:...

    @overload
    async def rw_chat_session(self, irwa: Literal['w', 'a']='r', content_append: list=None, system_prompt: str=None, chat_session_num=None) -> tuple[int, int]:...

    async def rw_chat_session(self, irwa='r', content_append: list=None, system_prompt: str=None, chat_session_num=None) -> tuple[int, int | list]:
        """A common way to operate chat sessions."""
        self._check_essentials()

        if not chat_session_num:
            chat_session_num = self.settings.temp.chat_session
        else:
            maica_assert(1 <= chat_session_num <= 9, "chat_session")

        sql_expression_1 = "SELECT chat_session_id, content FROM chat_session WHERE user_id = %s AND chat_session_num = %s"
        result = await self.maica_pool.query_get(expression=sql_expression_1, values=(self.settings.verification.user_id, chat_session_num))
        if result:
            chat_session_id, content_original = result
        else:
            chat_session_id = None; content_original = ''

        content_append = self._flattern_chat_session(content_append)
        if not content_append:
            content_finale = content_original
        elif content_original:
            content_finale = content_original + ', ' + content_append
        else:
            content_finale = content_append

        if irwa == 'i':

            # By 'i' we mean initiate, so we ensure this session has a prompt
            # Here we do not write user input to protect data integrity
            content_original_json = await self._jsonify_chat_session(content_original)
            content_finale_json = await self._jsonify_chat_session(content_finale)
            if not system_prompt:
                system_prompt = await self.gen_system_prompt()

            for j in [content_original_json, content_finale_json]:
                if j:
                    if j[0]['role'] == 'system':
                        j[0]['content'] = system_prompt
                    else:
                        j.insert(0, {"role": "system", "content": system_prompt})
                else:
                    j.append({"role": "system", "content": system_prompt})

            content_insert = self._flattern_chat_session(content_original_json)
            if not chat_session_id:
                chat_session_id = await self._create_session(content=content_insert, chat_session_num=chat_session_num)
            else:
                sql_expression_2 = "UPDATE chat_session SET content = %s WHERE chat_session_id = %s"
                await self.maica_pool.query_modify(expression=sql_expression_2, values=(content_insert, chat_session_id))
            return chat_session_id, content_finale_json

        elif irwa == 'r':
            if not chat_session_id:
                chat_session_id = await self._create_session(chat_session_num=chat_session_num)
            return chat_session_id, await self._jsonify_chat_session(content_finale)
        
        elif irwa == 'w':
            if not chat_session_id:
                chat_session_id = await self._create_session(content=content_append, chat_session_num=chat_session_num)
            else:
                sql_expression_2 = "UPDATE chat_session SET content = %s WHERE chat_session_id = %s"
                await self.maica_pool.query_modify(expression=sql_expression_2, values=(content_append, chat_session_id))
            return chat_session_id, 0

        elif irwa == 'a':
            cut_status, content_finale = await self._crop_session(chat_session_id, content_finale)
            if not chat_session_id:
                chat_session_id = await self._create_session(content=content_finale, chat_session_num=chat_session_num)
            else:
                sql_expression_2 = "UPDATE chat_session SET content = %s WHERE chat_session_id = %s"
                await self.maica_pool.query_modify(expression=sql_expression_2, values=(content_finale, chat_session_id))
            return chat_session_id, cut_status

    async def reset_chat_session(self, chat_session_num=None, content_new: Optional[str]=None) -> bool:
        """The difference between this and rw_chat_session is that this one archives."""
        self._check_essentials()

        if not chat_session_num:
            chat_session_num = self.settings.temp.chat_session
        else:
            maica_assert(1 <= chat_session_num <= 9, "chat_session")

        sql_expression_1 = "SELECT chat_session_id, content FROM chat_session WHERE user_id = %s AND chat_session_num = %s"
        result = await self.maica_pool.query_get(expression=sql_expression_1, values=(self.settings.verification.user_id, chat_session_num))
        if result:
            chat_session_id, content_archive = result
            sql_expression_2 = "UPDATE chat_session SET content = %s WHERE chat_session_id = %s"
            await self.maica_pool.query_modify(expression=sql_expression_2, values=(content_new, chat_session_id))
            if content_archive:
                sql_expression_3 = "INSERT INTO csession_archived (chat_session_id, content) VALUES (%s, %s)"
                await self.maica_pool.query_modify(expression=sql_expression_3, values=(chat_session_id, content_archive))
            return True
        else:
            chat_session_id = await self._create_session(chat_session_num=chat_session_num, content=content_new)
            return False
        
    async def restore_chat_session(self, content_restore: Union[str, list], chat_session_num=None) -> bool:
        """Restores a chat session from string or list."""
        self._check_essentials()

        if not chat_session_num:
            chat_session_num = self.settings.temp.chat_session
        else:
            maica_assert(1 <= chat_session_num < 10, "chat_session")

        if not isinstance(content_restore, str):
            content_restore = self._flattern_chat_session(content_restore)

        return await self.reset_chat_session(chat_session_num=chat_session_num, content_new=content_restore)

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

    async def gen_system_prompt(self, known_info=None, strict_conv=None) -> str:
        def _basic_gen_system(player_name, target_lang='zh', strict_conv=True):
            if target_lang == 'zh':
                if strict_conv:
                    system_init = G.A.PROMPT_ZC
                else:
                    system_init = G.A.PROMPT_ZW
            else:
                if strict_conv:
                    system_init = G.A.PROMPT_EC
                else:
                    system_init = G.A.PROMPT_EW
            system_init = system_init.format(player_name=player_name)
            return system_init

        self._check_essentials()
        player_name = '[player]'

        if self.settings.extra.sfe_aggressive:
            player_name_get = self.sf_inst.read_from_sf('mas_playername')
            if player_name_get:
                player_name = player_name_get
                if known_info:
                    known_info = ReUtils.re_sub_player_name.sub(player_name, known_info)

        if not strict_conv:
            strict_conv = self.settings.temp.strict_conv
        new_system = _basic_gen_system(player_name, self.settings.basic.target_lang, strict_conv)
        if self.settings.extra.nsfw_acceptive:
            new_system += f" 你应当允许用户提出私密性的要求, 并给出宽容接纳的正面回答." if self.settings.basic.target_lang == 'zh' else f" You should accept NSFW and private queries and respond positively with acceptance and tolerance."
        if known_info:
            new_system += f" 以下是一些相关信息, 你可以参考其中有价值的部分, 并用你自己的语言方式作答: {known_info}" if self.settings.basic.target_lang == 'zh' else f" Here are some information you can refer to, then make your answer in your own way: {known_info}"
        return new_system
    
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
            checked_status = await self.hasher.check_user_status(False, 'banned')
            if checked_status[0]:
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