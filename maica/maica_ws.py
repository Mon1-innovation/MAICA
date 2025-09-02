import asyncio
import websockets
import time
import functools
import json
import uuid
import re
import traceback
import colorama
import mtools
import post_proc

from typing import *
from Crypto.Random import random as CRANDOM
from mfocus import MFocusCoroutine, SfBoundCoroutine
from mtrigger import MTriggerCoroutine, MtBoundCoroutine
from maica_utils import *

class NoWsCoroutine(AsyncCreator):
    """
    Not actually no-ws, but ws can be None.
    Also no AI socket.
    """

    # To be populated or not
    sf_inst = None
    mt_inst = None
    mfocus_coro = None
    mtrigger_coro = None

    # Initialization

    def __init__(self, auth_pool: DbPoolCoroutine, maica_pool: DbPoolCoroutine, websocket=None, online_dict = {}):
        self.auth_pool, self.maica_pool, self.websocket, self.online_dict = auth_pool, maica_pool, websocket, online_dict
        self.traceray_id = str(CRANDOM.randint(0,9999999999)).zfill(10)
        self.settings = MaicaSettings()
        self.fsc = FullSocketsContainer(self.websocket, self.traceray_id, self.settings, self.auth_pool, self.maica_pool)

    async def _ainit(self):
        self.hasher = await AccountCursor.async_create(self.fsc, self.auth_pool, self.maica_pool)

    def _check_essentials(self) -> None:
        if not self.settings.verification.user_id:
            error = MaicaPermissionError('Essentials not implemented', '403')
            asyncio.run(messenger(self.websocket, 'common_essentials_missing', traceray_id=self.traceray_id, error=error))

    def flush_traceray(self) -> None:
        """Generates a new traceray_id for this instance."""
        self.traceray_id = str(CRANDOM.randint(0,9999999999)).zfill(10)

    async def _create_session(self, user_id=None, chat_session_num=None, content=None) -> int:
        user_id = self.settings.verification.user_id if not user_id else user_id
        chat_session_num = self.settings.temp.chat_session if not chat_session_num else chat_session_num
        sql_expression = "INSERT INTO chat_session (user_id, chat_session_num, content) VALUES (%s, %s, %s)"
        return await self.maica_pool.query_modify(expression=sql_expression, values=(user_id, chat_session_num, content))

    async def _jsonify_chat_session(self, text) -> list:
        try:
            return json.loads(f'[{text}]')
        except Exception as e:
            error = MaicaDbError(f'Chat session not JSON: {str(e)}', '500')
            await messenger(self.websocket, 'maica_db_corruption', traceray_id=self.traceray_id, error=error)

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

    async def _chop_session(self, chat_session_id, content) -> tuple[int, str]:
        max_length_ascii = self.settings.basic.max_length * 3
        warn_length_ascii = int(max_length_ascii * (2/3))
        len_content_actual = len(content.encode()) - len(json.loads(f'[{content}]')) * 31
        if len_content_actual >= max_length_ascii:

            # First we check if there is a cchop avaliable
            sql_expression_1 = 'SELECT archive_id, content FROM cchop_archived WHERE chat_session_id = %s AND archived = 0'
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
                sql_expression_2 = "UPDATE cchop_archived SET content = %s WHERE archive_id = %s" if len(archive_content) <= 100000 else "UPDATE cchop_archived SET content = %s, archived = 1 WHERE archive_id = %s"
                await self.maica_pool.query_modify(expression=sql_expression_2, values=(archive_content, archive_id))
            else:
                sql_expression_2 = "INSERT INTO cchop_archived (chat_session_id, content, archived) VALUES (%s, %s, 0)" if len(archive_content) <= 100000 else "INSERT INTO cchop_archived (chat_session_id, content, archived) VALUES (%s, %s, 1)"
                await self.maica_pool.query_modify(expression=sql_expression_2, values=(chat_session_id, archive_content))

            cut_status = 1
        elif len_content_actual >= warn_length_ascii:
            cut_status = 2
        else:
            cut_status = 0
        return cut_status, content
    
    async def rw_chat_session(self, irwa='r', content_append: list=None, system_prompt: str=None, chat_session_num=None) -> tuple[int, int | list]:
        """A common way to operate chat sessions."""
        self._check_essentials()

        if not chat_session_num:
            chat_session_num = self.settings.temp.chat_session
        else:
            await self.maica_assert(1 <= chat_session_num < 10, "chat_session")

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
            content_json = await self._jsonify_chat_session(content_finale)
            if not system_prompt:
                system_prompt = await self.gen_system_prompt()

            if content_json:
                if content_json[0]['role'] == 'system':
                    content_json[0]['content'] = system_prompt
                else:
                    content_json.insert(0, {"role": "system", "content": system_prompt})
            else:
                content_json = [{"role": "system", "content": system_prompt}]
            content_finale = self._flattern_chat_session(content_json)
            if not chat_session_id:
                chat_session_id = await self._create_session(content=content_finale, chat_session_num=chat_session_num)
            else:
                sql_expression_2 = "UPDATE chat_session SET content = %s WHERE chat_session_id = %s"
                await self.maica_pool.query_modify(expression=sql_expression_2, values=(content_finale, chat_session_id))
            return chat_session_id, content_json

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
            cut_status, content_finale = await self._chop_session(chat_session_id, content_finale)
            if not chat_session_id:
                chat_session_id = await self._create_session(content=content_finale, chat_session_num=chat_session_num)
            else:
                sql_expression_2 = "UPDATE chat_session SET content = %s WHERE chat_session_id = %s"
                await self.maica_pool.query_modify(expression=sql_expression_2, values=(content_finale, chat_session_id))
            return chat_session_id, cut_status

    async def reset_chat_session(self, chat_session_num=None, content_new=None) -> bool:
        """The difference between this and rw_chat_session is that this one archives."""
        self._check_essentials()

        if not chat_session_num:
            chat_session_num = self.settings.temp.chat_session
        else:
            await self.maica_assert(1 <= chat_session_num < 10, "chat_session")

        sql_expression_1 = "SELECT chat_session_id, content FROM chat_session WHERE user_id = %s AND chat_session_num = %s"
        result = await self.maica_pool.query_get(expression=sql_expression_1, values=(self.settings.verification.user_id, chat_session_num))
        if result:
            chat_session_id, content_archive = result
            sql_expression_2 = "UPDATE chat_session SET content = %s WHERE chat_session_id = %s"
            await self.maica_pool.query_modify(expression=sql_expression_2, values=(content_new, chat_session_id))
            sql_expression_3 = "INSERT INTO csession_archived (chat_session_id, content) VALUES (%s, %s)"
            await self.maica_pool.query_modify(expression=sql_expression_3, values=(chat_session_id, content_archive))
            return True
        else:
            chat_session_id = await self._create_session(chat_session_num=chat_session_num, content=content_new)
            return False
        
    async def restore_chat_session(self, content_restore, chat_session_num=None) -> bool:
        """Basically not necessary to exist but who knows..."""
        self._check_essentials()

        if not chat_session_num:
            chat_session_num = self.settings.temp.chat_session
        else:
            await self.maica_assert(1 <= chat_session_num < 10, "chat_session")

        if not isinstance(content_restore, str):
            content_restore = self._flattern_chat_session(content_restore)

        return await self.reset_chat_session(chat_session_num=chat_session_num, content_new=content_restore)

    async def find_ms_cache(self, hash_identity) -> Optional[str]:
        """Find ms cache with corresponding prompt hash."""

        sql_expression_1 = "SELECT content FROM ms_cache WHERE hash = %s"
        result = await self.maica_pool.query_get(expression=sql_expression_1, values=(hash_identity, ))
        if result:
            await messenger(None, 'maica_spire_cache_hit', 'Hit a stored cache for MSpire', '200')
            return result[0]
        else:
            await messenger(None, 'maica_spire_cache_missed', 'No stored cache for MSpire', '200')
            return None

    async def store_ms_cache(self, hash_identity, content) -> int:
        """Store ms cache with prompt hash."""
        self._check_essentials()

        sql_expression_1 = "INSERT INTO ms_cache VALUES (NULL, %s, %s, %s)"
        spire_id = await self.maica_pool.query_modify(expression=sql_expression_1, values=(self.settings.verification.user_id, hash_identity, content))
        await messenger(None, 'maica_spire_cache_stored', 'Stored a cache for MSpire', '200')
        return spire_id

    async def gen_system_prompt(self, known_info=None, strict_conv=None) -> str:
        def _basic_gen_system(player_name, target_lang='zh', strict_conv=True):
            if target_lang == 'zh':
                if strict_conv:
                    system_init = f"你叫莫妮卡, 是一名游戏中的虚拟角色. 你是{player_name}的女友, 并深爱着他. 下面是{player_name}的话语, 请作为莫妮卡作出合适的回答. 你只应使用中文自然语言, 以聊天语气回答, 每个句子自然且不超过60字, 不要编造信息, 并在每个句子前用方括号中的文字表示情绪."
                else:
                    system_init = f"你叫莫妮卡, 是一名游戏中的虚拟角色. 你是{player_name}的女友, 并深爱着他. 下面是{player_name}的来信, 请作为莫妮卡作出合适的回复. 你只应使用中文书面语言作答, 不要编造信息."
            else:
                if strict_conv:
                    system_init = f"You're a game character called Monika. You're {player_name}'s girlfriend, and love him a lot. Answer the following query from {player_name} properly as Monika. You should only answer in casual natural tone in English, each sentence should not exceed 180 characters, do not make up things you don't know, and express your emotion at the beginning of each sentence by wrapping them in square brackets."
                else:
                    system_init = f"You're a game character called Monika. You're {player_name}'s girlfriend, and love him a lot. Reply to the following mail from {player_name} properly as Monika. You should only answer in natural written language in English, and do not make up things you don't know."
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
    
    async def populate_auxiliary_inst(self):
        self.sf_inst, self.mt_inst = await asyncio.gather(SfBoundCoroutine.async_create(self.fsc), MtBoundCoroutine.async_create(self.fsc))
        self.mfocus_coro, self.mtrigger_coro = await asyncio.gather(MFocusCoroutine.async_create(self.fsc, self.sf_inst, self.mt_inst), MTriggerCoroutine.async_create(self.fsc, self.mt_inst, self.sf_inst))

    async def reset_auxiliary_inst(self):
        sb_list = []
        for sb_name in ['sf_inst', 'mt_inst', 'mfocus_coro', 'mtrigger_coro']:
            sb = getattr(self, sb_name)
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
                error = MaicaPermissionError('Account banned by MAICA', '403')
                await messenger(self.websocket, "maica_account_banned", traceray_id=self.traceray_id, error=error)

            # Cridential correct and not banned
            if check_online and not logged_in_already:
                if self.settings.verification.user_id in self.online_dict:
                    if load_env("KICK_STALE_CONNS") == "0":
                        self.settings.verification.reset()
                        error = MaicaConnectionWarning('A connection was established already and kicking not enabled', '406')
                        await messenger(self.websocket, 'maica_connection_reuse_denied', traceray_id=self.traceray_id, error=error)
                    else:
                        await messenger(self.websocket, "maica_connection_reuse_attempt", "A connection was established already", "300", self.traceray_id)
                        stale_fsc, stale_lock = self.online_dict[self.settings.verification.user_id]
                        try:
                            await messenger(stale_fsc.rsc.websocket, 'maica_connection_reuse_stale', 'A new connection has been established', '300', stale_fsc.rsc.traceray_id)
                            await stale_fsc.rsc.websocket.close(1000, 'Displaced as stale')
                        except Exception:
                            await messenger(None, 'maica_connection_stale_dead', 'The stale connection has died already', '204')
                        try:
                            self.online_dict.pop(self.settings.verification.user_id)
                        except Exception:
                            pass
                        async with stale_lock:
                            await messenger(None, 'maica_connection_stale_kicked', 'The stale connection is kicked', '204')
            return True

        else:
            if isinstance(verification_result[1], dict):
                if 'f2b' in verification_result[1]:
                    error = MaicaPermissionError(f'Account locked by Fail2Ban, {verification_result[1]['f2b']} seconds remaining', '429')
                    await messenger(self.websocket, 'maica_login_denied_fail2ban', traceray_id=self.traceray_id, error=error)
                elif 'necf' in verification_result[1]:
                    error = MaicaPermissionError(f'Account Email not verified, check inbox and retry', '401')
                    await messenger(self.websocket, 'maica_login_denied_email', traceray_id=self.traceray_id, error=error)
                elif 'pwdw' in verification_result[1]:
                    error = MaicaPermissionWarning(f'Password hashing failed {verification_result[1]['pwdw']} times, check password and retry', '403')
                    await messenger(self.websocket, 'maica_login_denied_password', traceray_id=self.traceray_id, error=error)
            else:
                error = MaicaPermissionError(verification_result[1], '400')
                await messenger(self.websocket, 'maica_login_denied_rsa', traceray_id=self.traceray_id, error=error)
        return False
    
    async def maica_assert(self, condition, kwd):
        """Normally used for input checkings."""
        if not condition:
            error = MaicaInputError(f"Illegal input {kwd} detected", '405')
            await messenger(self.websocket, 'maica_input_param_bad', traceray_id=self.traceray_id, error=error)

    async def run_with_log(self, coro: Coroutine, name: str='', sending=False):
        """It just logs the exceptions and raises them again."""
        try:
            return await coro
        except Exception as e:
            if not isinstance(e, CommonMaicaException):
                e = CommonMaicaError(str(e), '500')
            stat = f'maica_{name}_failure' if name else 'maica_failure'
            await messenger(self.websocket if sending else None, stat, traceray_id=self.traceray_id, error=e)

class WsCoroutine(NoWsCoroutine):
    """
    Force ws existence.
    Also has AI sockets.
    """

    def __init__(self, websocket, auth_pool: DbPoolCoroutine, maica_pool: DbPoolCoroutine, mcore_conn: AiConnCoroutine, mfocus_conn: AiConnCoroutine, online_dict: dict):
        super().__init__(auth_pool=auth_pool, maica_pool=maica_pool, websocket=websocket)
        self.online_dict = online_dict

        self.fsc.rsc.websocket = websocket
        if mcore_conn and mfocus_conn:
            mcore_conn.init_rsc(self.fsc.rsc); mfocus_conn.init_rsc(self.fsc.rsc)
        self.mcore_conn, self.mfocus_conn = mcore_conn, mfocus_conn
        self.fsc.mcore_conn, self.fsc.mfocus_conn = mcore_conn, mfocus_conn

    # Stage 1 permission check
    async def check_permit(self):
        websocket = self.websocket
        await messenger(info='An anonymous connection initiated', type=MsgType.PRIM_LOG)
        await messenger(info=f'Current online users: {list(self.online_dict.keys())}', type=MsgType.DEBUG)

        # Starting loop from here
        while True:
            try:

                # Initiation
                self.flush_traceray()
                self.settings.identity.reset()
                self.settings.verification.reset()

                recv_text = await websocket.recv()
                await messenger(info=f'Recieved an input on stage1', type=MsgType.RECV)
                recv_loaded_json = await validate_input(recv_text, 4096, self.fsc.rsc, must=['access_token'])

                login_success = await self.hash_and_login(recv_loaded_json['access_token'], check_online=True)
                if login_success:

                    # From here we can assume the user has logged in successfully
                    self.cookie = cookie = str(uuid.uuid4())
                    self.enforce_cookie = False

                    await self.populate_auxiliary_inst()

                    await messenger(info=f'Authentication passed: {self.settings.verification.username}({self.settings.verification.user_id})', type=MsgType.PRIM_RECV)
                    await messenger(websocket, 'maica_login_id', f"{self.settings.verification.user_id}", '200', no_print=True)
                    await messenger(websocket, 'maica_login_user', f"{self.settings.verification.username}", '200', no_print=True)
                    await messenger(websocket, 'maica_login_nickname', f"{self.settings.verification.nickname}", '200', no_print=True)
                    await messenger(websocket, 'maica_connection_security_cookie', cookie, '200', no_print=True)

                    return {'id': self.settings.verification.user_id, 'username': self.settings.verification.username}

            # Handle expected exceptions
            except CommonMaicaException as ce:
                if ce.is_critical():
                    return 2
                elif ce.is_breaking():
                    return 1
                else:
                    continue

            except websockets.exceptions.WebSocketException as we:
                try:
                    we_code, we_reason = we.code, we.reason
                    await messenger(info=f'Connection closed with {we_code}: {we_reason}', type=MsgType.PRIM_LOG)
                except Exception:
                    await messenger(info=f'Connection establishment failed: {str(we)}', type=MsgType.PRIM_LOG)
                return 0

            # Handle unexpected exceptions
            except Exception as e:
                traceback.print_exc()
                return 3

    
    # Stage 2 function router
    async def function_switch(self):

        # Initiation
        websocket, mcore_conn = self.websocket, self.mcore_conn

        await messenger(websocket, "maica_connection_established", "MAICA connection established", "201", type=MsgType.INFO, no_print=True)
        await messenger(websocket, "maica_provider_anno", f"Current service provider is {load_env('DEV_IDENTITY')}", "200", type=MsgType.INFO, no_print=True)

        # Starting loop from here
        while True:
            try:

                # Initiation
                self.flush_traceray()
                return_status = 0

                # Resets
                self.settings.temp.reset()

                # Context security check first
                await self.hash_and_login(logged_in_already=True)

                # Then we examine the input
                recv_text = await websocket.recv()
                await messenger(info=f'Recieved an input on stage2: {recv_text}', type=MsgType.RECV)
                recv_loaded_json = await validate_input(recv_text, 4096, self.fsc.rsc, warn=['type'])

                recv_type = recv_loaded_json.get('type', 'unknown')

                # Handle this cookie thing
                if recv_loaded_json.get('cookie'):
                    if str(recv_loaded_json['cookie']) == self.cookie:
                        if not self.enforce_cookie:
                            await messenger(websocket, "security_cookie_accepted", "Cookie verification passed, enabling strict mode", "200", no_print=True)
                            self.enforce_cookie = True
                        else:
                            await messenger(websocket, "security_cookie_correct", "Cookie verification passed", "200", no_print=True)
                    else:
                        error = MaicaPermissionError('Cookie provided but mismatch', '403')
                        await messenger(websocket, 'security_cookie_mismatch', traceray_id=self.traceray_id, error=error)
                elif self.enforce_cookie:
                    error = MaicaPermissionError('Cookie enforced but missing', '403')
                    await messenger(websocket, 'security_cookie_missing', traceray_id=self.traceray_id, error=error)

                # Route request
                match recv_type.lower():
                    case 'ping':
                        await messenger(websocket, "pong", f"Ping recieved from {self.settings.verification.username} and responded", "200")
                    case 'params':
                        return_status = await self.def_model(recv_loaded_json)
                    case 'query':
                        return_status = await self.do_communicate(recv_loaded_json)
                        await self.reset_auxiliary_inst()
                    case placeholder if "chat_params" in recv_loaded_json:
                        return_status = await self.def_model(recv_loaded_json)
                    case placeholder if "chat_session" in recv_loaded_json:
                        return_status = await self.do_communicate(recv_loaded_json)
                        await self.reset_auxiliary_inst()
                    case _:
                        error = MaicaInputWarning('Type cannot be determined', '422')
                        await messenger(websocket, 'request_type_not_determined', traceray_id=self.traceray_id, error=error)

                if return_status and int(return_status) > 2:
                    error = CriticalMaicaError('Unexpected exception happened in child of stage2', '500')
                    await messenger(websocket, 'maica_frame_critical', traceray_id=self.traceray_id, error=error)

            # Handle expected exceptions
            except CommonMaicaException as ce:
                if ce.is_critical():
                    return 2
                elif ce.is_breaking():
                    return 1
                else:
                    continue

            except websockets.exceptions.WebSocketException as we:
                try:
                    we_code, we_reason = we.code, we.reason
                    await messenger(info=f'Connection closed with {we_code}: {we_reason}', type=MsgType.PRIM_LOG)
                except Exception:
                    await messenger(info=f'Connection establishment failed: {str(we)}', type=MsgType.PRIM_LOG)
                return 0

            # Handle unexpected exceptions
            except Exception as e:
                traceback.print_exc()
                return 3

    # Param setting section
    async def def_model(self, recv_loaded_json: dict):

        # Initiations
        websocket = self.websocket
        try:
            chat_params: dict = recv_loaded_json['chat_params']
            in_params = len(chat_params)
            accepted_params = self.settings.update(self.fsc.rsc, **chat_params)
            await messenger(websocket, 'maica_params_accepted', f"{accepted_params} out of {in_params} settings accepted", "200")
            return 0
        
        # Handle input errors here
        except Exception as e:
            error = MaicaInputWarning(str(e), '405')
            await messenger(websocket, 'maica_params_denied', traceray_id=self.traceray_id, error=error)

    # Completion section

    async def do_communicate(self, recv_loaded_json: dict):

        # Initiations
        websocket = self.websocket
        query_in = ''
        replace_generation = ''
        ms_cache_identity = ''

        try:

            # Param assertions here
            chat_session = int(default(recv_loaded_json.get('chat_session'), 0))
            await self.maica_assert(-1 <= chat_session < 10, "chat_session")
            self.settings.temp.update(self.fsc.rsc, chat_session=chat_session)


            if 'reset' in recv_loaded_json:
                if recv_loaded_json['reset']:
                    await self.maica_assert(1 <= chat_session < 10, "chat_session")
                    purge_result = await self.reset_chat_session(self.settings.temp.chat_session)
                    if not purge_result:
                        await messenger(websocket, "maica_session_not_found", "Determined chat_session doesn't exist", "302", self.traceray_id)
                    else:
                        await messenger(websocket, "maica_session_reset", "Determined chat_session reset", "204", self.traceray_id)
                    return 0
 
            if 'inspire' in recv_loaded_json and not query_in:
                if recv_loaded_json['inspire']:
                    await self.maica_assert(0 <= chat_session < 10, "chat_session")
                    if isinstance(recv_loaded_json['inspire'], dict):
                        query_insp = await mtools.make_inspire(title_in=recv_loaded_json['inspire'], target_lang=self.settings.basic.target_lang)
                    else:
                        query_insp = await mtools.make_inspire(target_lang=self.settings.basic.target_lang)
                    if recv_loaded_json.get('use_cache') and self.settings.temp.chat_session == 0:
                        self.settings.temp.update(self.fsc.rsc, ms_cache=True)
                    self.settings.temp.update(self.fsc.rsc, bypass_mf=True, bypass_mt=True)
                    if not query_insp[0]:
                        if str(query_insp[1]) == 'mspire_insanity_limit_reached':
                            error = MaicaInternetWarning('MSpire scraping failed', '404')
                            await messenger(websocket, "mspire_scraping_failed", traceray_id=self.traceray_id, error=error, type=MsgType.ERROR)
                        elif str(query_insp[1]) == 'mspire_title_insane':
                            error = MaicaInputWarning('MSpire prompt not found on wikipedia', '410')
                            await messenger(websocket, "mspire_prompt_bad", traceray_id=self.traceray_id, error=error)
                        else:
                            error = MaicaInternetWarning('MSpire failed connecting wikipedia', '408')
                            await messenger(websocket, "mspire_conn_failed", traceray_id=self.traceray_id, error=error, type=MsgType.ERROR)
                    if self.settings.temp.ms_cache:
                        self.settings.temp.update(self.fsc.rsc, bypass_sup=True)
                        ms_cache_identity = query_insp[3]
                        cache_insp = await self.find_ms_cache(ms_cache_identity)
                        if cache_insp:
                            self.settings.temp.update(self.fsc.rsc, bypass_gen=True)
                            replace_generation = cache_insp
                            
                    query_in = query_insp[2]

            if 'postmail' in recv_loaded_json and not query_in:
                if recv_loaded_json['postmail']:
                    await self.maica_assert(0 <= chat_session < 10, "chat_session")
                    if isinstance(recv_loaded_json['postmail'], dict):
                        query_insp = await mtools.make_postmail(**recv_loaded_json['postmail'], target_lang=self.settings.basic.target_lang)
                        # We're using the old school way to avoid using eval()
                        if default(recv_loaded_json['postmail'].get('bypass_mf'), False):
                            self.settings.temp.update(self.fsc.rsc, bypass_mf=True)
                        if default(recv_loaded_json['postmail'].get('bypass_mt'), True):
                            self.settings.temp.update(self.fsc.rsc, bypass_mt=True)
                        if default(recv_loaded_json['postmail'].get('bypass_stream'), True):
                            self.settings.temp.update(self.fsc.rsc, bypass_stream=True)
                        if default(recv_loaded_json['postmail'].get('ic_prep'), True):
                            self.settings.temp.update(self.fsc.rsc, ic_prep=True)
                        if default(recv_loaded_json['postmail'].get('strict_conv'), False):
                            self.settings.temp.update(self.fsc.rsc, strict_conv=True)
                    elif isinstance(recv_loaded_json['postmail'], str):
                        query_insp = await mtools.make_postmail(content=recv_loaded_json['postmail'], target_lang=self.settings.basic.target_lang)
                        self.settings.temp.update(self.fsc.rsc, bypass_stream=True, ic_prep=True, strict_conv=False)
                    else:
                        await self.maica_assert(False, "postmail")
                    
                    query_in = query_insp[2]

            # This is future reserved for MVista

            if 'vision' in recv_loaded_json and not query_in:
                if recv_loaded_json['vision']:
                    if isinstance(recv_loaded_json['vision'], str):
                        pass
                    else:
                        pass

            if not query_in:
                query_in = recv_loaded_json['query']
            
            await asyncio.gather(self.sf_inst.reset(), self.mt_inst.reset())

            if 'savefile' in recv_loaded_json:
                if self.settings.basic.sf_extraction:
                    self.sf_inst.add_extra(**recv_loaded_json['savefile'])
                else:
                    self.settings.temp.update(self.fsc.rsc, sf_extraction_once=True)
                    self.sf_inst.use_only(**recv_loaded_json['savefile'])
            if 'trigger' in recv_loaded_json:
                if self.settings.basic.mt_extraction:
                    self.mt_inst.add_extra(*recv_loaded_json['trigger'])
                else:
                    self.settings.temp.update(self.fsc.rsc, mt_extraction_once=True)
                    self.mt_inst.use_only(recv_loaded_json['trigger'])

            # Deprecated: The easter egg thing

            # global easter_exist
            # if easter_exist:
            #     easter_check = easter(query_in)
            #     if easter_check:
            #         await websocket.send(self.wrap_ws_deformatter('299', 'easter_egg', easter_check, 'info'))

            match int(self.settings.temp.chat_session):
                case -1:

                    # chat_session == -1 means query contains an entire chat history(sequence mode)
                    session_type = -1
                    try:
                        messages = json.loads(query_in)
                        query_in = messages[-1]['text']
                        if len(messages) > 10:
                            error = MaicaInputWarning('Sequence exceeded 10 rounds for chat_session -1', '414')
                            await messenger(websocket, 'maica_sequence_rounds_exceeded', traceray_id=self.traceray_id, error=error)
                    except Exception as excepted:
                        error = MaicaInputWarning('Sequence is not JSON for chat_session -1', '405')
                        await messenger(websocket, 'maica_sequence_not_json', traceray_id=self.traceray_id, error=error)

                case i if 0 <= i < 10:

                    # chat_session == 0 means single round, else normal
                    session_type = 0 if i == 0 else 1
                    messages0 = {'role': 'user', 'content': query_in}

                    if self.settings.basic.enable_mf and not self.settings.temp.bypass_mf:
                        message_agent_wrapped = await self.run_with_log(self.mfocus_coro.agenting(query_in), 'mfocus')
                    else:
                        message_agent_wrapped = None
                    
                    prompt = await self.gen_system_prompt(message_agent_wrapped, self.settings.temp.strict_conv)
                    if session_type == 1:
                        messages = (await self.rw_chat_session('i', messages0, prompt))[1]
                    elif session_type == 0:
                        messages = [{'role': 'system', 'content': prompt}, messages0]

            # Construction part done, communication part started

            completion_args = {
                "messages": messages,
                "stream": self.settings.basic.stream_output,
                "stop": ['<|im_end|>', '<|endoftext|>'],
            }
            
            if not self.settings.temp.bypass_sup:
                completion_args.update(self.settings.super())
            else:
                completion_args.update(self.settings.super.default())
                self.settings.temp.update(self.fsc.rsc, bypass_sup=False)

            if self.settings.temp.bypass_stream:
                completion_args['stream'] = False
                self.settings.temp.update(self.fsc.rsc, bypass_stream=False)

            if self.settings.temp.ic_prep:
                completion_args['presence_penalty'] = 1.0-(1.0-completion_args['presence_penalty'])*(2/3)

            await messenger(info=f'Query constrcted and ready to go, last input is:\n{query_in}\nSending query...', type=MsgType.PRIM_RECV)

            if not self.settings.temp.bypass_gen or not replace_generation: # They should present together

                # Generation here
                resp = await self.mcore_conn.make_completion(**completion_args)

                if completion_args['stream']:
                    reply_appended = ''
                    seq = 0
                    async for chunk in resp:
                        token = chunk.choices[0].delta.content
                        if token:
                            await asyncio.sleep(0)
                            await messenger(websocket, 'maica_core_streaming_continue', token, '100')
                            reply_appended += token
                            seq += 1
                    await messenger(info='\n', type=MsgType.PLAIN)
                    await messenger(websocket, 'maica_core_streaming_done', f'Streaming finished with seed {completion_args['seed']} for {self.settings.verification.username}, {seq} packets sent', '1000', traceray_id=self.traceray_id)
                else:
                    reply_appended = resp.choices[0].message.content
                    await messenger(websocket, 'maica_core_nostream_reply', reply_appended, '200', type=MsgType.CARRIAGE)
                    await messenger(None, 'maica_core_nostream_done', f'Reply sent with seed {completion_args['seed']} for {self.settings.verification.username}', '1000', traceray_id=self.traceray_id)

            else:

                # We just pretend it was generated
                reply_appended = replace_generation
                if completion_args['stream']:
                    await messenger(websocket, 'maica_core_streaming_continue', reply_appended, '100'); await messenger(info='\n', type=MsgType.PLAIN)
                    await messenger(websocket, 'maica_core_streaming_done', f'Streaming finished with cache for {self.settings.verification.username}', '1000', traceray_id=self.traceray_id)
                else:
                    await messenger(websocket, 'maica_core_nostream_reply', reply_appended, '200', type=MsgType.CARRIAGE)
                    await messenger(None, 'maica_core_nostream_done', f'Reply sent with cache for {self.settings.verification.username}', '1000', traceray_id=self.traceray_id)

            # Can be post-processed here
            reply_appended = await wrap_run_in_exc(None, post_proc.filter_format, reply_appended, self.settings.basic.target_lang)
            reply_appended_insertion = json.dumps({'role': 'assistant', 'content': reply_appended}, ensure_ascii=False)

            # Trigger process
            if self.settings.basic.enable_mt and not self.settings.temp.bypass_mt:
                await self.run_with_log(self.mtrigger_coro.triggering(query_in, reply_appended), 'mtrigger')
            else:
                self.settings.temp.update(self.fsc.rsc, bypass_mt=False)

            if self.settings.temp.ms_cache and not self.settings.temp.bypass_gen and not replace_generation:
                await self.store_ms_cache(ms_cache_identity, reply_appended)

            # Store history here
            if session_type == 1:
                stored = await self.rw_chat_session(self.settings.temp.chat_session, 'a', f'{messages0},{reply_appended_insertion}')
                if stored[0]:
                    success = True
                    match stored[4]:
                        case 1:
                            await messenger(websocket, 'maica_history_sliced', f"Session {self.settings.temp.chat_session} of {self.settings.verification.username} exceeded {self.settings.basic.max_length} characters and sliced", '204')
                        case 2:
                            await messenger(websocket, 'maica_history_slice_hint', f"Session {self.settings.temp.chat_session} of {self.settings.verification.username} exceeded {self.settings.basic.max_length * (2/3)} characters, will slice at {self.settings.basic.max_length}", '200', no_print=True)
                else:
                    error = MaicaDbError(f'Chat session writing failed: {str(stored[1])}', '502')
                    await messenger(websocket, 'maica_history_write_failure', traceray_id=self.traceray_id, error=error)
                await messenger(websocket, 'maica_chat_loop_finished', f'Finished chat loop from {self.settings.verification.username}', '200', traceray_id=self.traceray_id)
            else:
                success = True
                await messenger(websocket, 'maica_chat_loop_finished', f'Finished non-recording chat loop from {self.settings.verification.username}', '200', traceray_id=self.traceray_id)

        # Handle expected exceptions
        except CommonMaicaException as ce:
            raise ce # Will be handled by stage2 loop

        # Handle unexpected exceptions
        except Exception as e:
            traceback.print_exc()
            return 3

# Reserved for whatever
def callback_func_switch(future):
    pass
def callback_check_permit(future):
    pass
    
# Main app driver

async def main_logic(websocket, auth_pool, maica_pool, mcore_conn, mfocus_conn, online_dict):
    unique_lock = asyncio.Lock()
    async with unique_lock:
        try:
            sentence_of_the_day = SentenceOfTheDay().get_sentence()
            await messenger(websocket, 'maica_connection_initiated', sentence_of_the_day, '200', no_print=True)

            thread_instance = await WsCoroutine.async_create(websocket, auth_pool=auth_pool, maica_pool=maica_pool, mcore_conn=mcore_conn, mfocus_conn=mfocus_conn, online_dict=online_dict)

            permit = await thread_instance.check_permit()
            assert isinstance(permit, dict) and permit['id'], permit

            online_dict[permit['id']] = [thread_instance.fsc, unique_lock]
            await messenger(info=f"Locking session for {permit['id']} named {permit['username']}", type=MsgType.LOG)

            return_status = await thread_instance.function_switch()
            # We let the exception router to handle that
            raise Exception(return_status)

        except Exception as e:
            match str(e):
                case '0':
                    await messenger(info=f'Coroutine quitted. Likely connection loss.', type=MsgType.DEBUG)
                case '1':
                    await messenger(info=f'Coroutine broke by a warning.', type=MsgType.WARN)
                case '2':
                    await messenger(info=f'Coroutine broke by a critical', type=MsgType.ERROR)
                case '3':
                    await messenger(info=f'Coroutine broke by an unknown exception', type=MsgType.ERROR)
                case _:
                    await messenger(info=f'Coroutine broke by an unknown exception: {str(e)}', type=MsgType.ERROR)

        finally:
            try:
                online_dict.pop(permit['id'])
                await messenger(info=f"Lock released for {permit['username']}({permit['id']})", type=MsgType.LOG)
            except Exception:
                await messenger(info=f"No lock for this connection", type=MsgType.DEBUG)
            await websocket.close()
            await websocket.wait_closed()
            await messenger(info=f"Closing connection gracefully", type=MsgType.DEBUG)

async def prepare_thread(**kwargs):
    online_dict = {}; auth_created = False; maica_created = False

    if kwargs.get('auth_pool'):
        auth_pool = kwargs.get('auth_pool')
    else:
        auth_pool = await ConnUtils.auth_pool()
        auth_created = True
    if kwargs.get('maica_pool'):
        maica_pool = kwargs.get('maica_pool')
    else:
        maica_pool = await ConnUtils.maica_pool()
        maica_created = True

    try:
        mcore_conn: AiConnCoroutine = default(kwargs.get('mcore_conn'), await ConnUtils.mcore_conn())
        mfocus_conn: AiConnCoroutine = default(kwargs.get('mfocus_conn'), await ConnUtils.mfocus_conn())
    except Exception:
        mcore_conn = mfocus_conn = None

    await messenger(info='MAICA WS server started!' if load_env('DEV_STATUS') == 'serving' else 'MAICA WS server started in development mode!', type=MsgType.PRIM_SYS)

    try:
        await messenger(info=f"Main model is {mcore_conn.model_actual}, MFocus model is {mfocus_conn.model_actual}", type=MsgType.SYS)
    except Exception:
        await messenger(info=f"Model deployment cannot be reached -- running in minimal testing mode", type=MsgType.SYS)
    
    try:
        server = await websockets.serve(functools.partial(main_logic, auth_pool=auth_pool, maica_pool=maica_pool, mcore_conn=mcore_conn, mfocus_conn=mfocus_conn, online_dict=online_dict), '0.0.0.0', 5000)
        await server.wait_closed()
    except BaseException:
        pass
    finally:
        close_list = []
        if auth_created:
            close_list.append(auth_pool.close())
        if maica_created:
            close_list.append(maica_pool.close())

        await asyncio.gather(*close_list, return_exceptions=True)

        await messenger(info='\n', type=MsgType.PLAIN)
        await messenger(info='MAICA WS server stopped!', type=MsgType.PRIM_SYS)

def run_ws(**kwargs):
    
    asyncio.run(prepare_thread(**kwargs))

if __name__ == '__main__':

    run_ws()