import nest_asyncio
nest_asyncio.apply()
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
import mfocus
import mtrigger
import post_proc
#import maica_http
from typing import *
from Crypto.Random import random as CRANDOM
from mfocus import MFocusCoroutine, SfBoundCoroutine
# mtrigger...
from maica_utils import *

class NoWsCoroutine():
    """
    Not actually no-ws, but ws can be None.
    Also no AI socket.
    """

    # Initialization

    def __init__(self, auth_pool: DbPoolCoroutine, maica_pool: DbPoolCoroutine, websocket=None):
        self.auth_pool, self.maica_pool, self.websocket = auth_pool, maica_pool, websocket
        self.traceray_id = str(CRANDOM.randint(0,9999999999)).zfill(10)
        self.settings = MaicaSettings()
        self.fsc = FullSocketsContainer(self.websocket, self.traceray_id, self.settings, self.auth_pool, self.maica_pool)
        self.hasher = AccountCursor(self.fsc, self.auth_pool, self.maica_pool)

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

    def _flattern_chat_session(content_json: list) -> str:
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
            result = await self.maica_pool.query_get(expression=sql_expression_1, values=(chat_session_id))
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
    
    async def rw_chat_session(self, irwa='r', content_append: list=None, system_prompt: str=None) -> tuple[int, int | list]:
        """A common way to operate chat sessions."""
        self._check_essentials()

        sql_expression_1 = "SELECT chat_session_id, content FROM chat_session WHERE user_id = %s AND chat_session_num = %s"
        result = await self.maica_pool.query_get(expression=sql_expression_1, values=(self.settings.verification.user_id, self.settings.temp.chat_session))
        if result:
            chat_session_id, content_original = result
        else:
            chat_session_id = None, content_original = ''

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
                chat_session_id = await self._create_session(content=content_finale)
            else:
                sql_expression_2 = "UPDATE chat_session SET content = %s WHERE chat_session_id = %s"
                await self.maica_pool.query_modify(expression=sql_expression_2, values=(content_finale, chat_session_id))
            return chat_session_id, content_json

        elif irwa == 'r':
            if not chat_session_id:
                chat_session_id = await self._create_session()
            return chat_session_id, await self._jsonify_chat_session(content_finale)
        
        elif irwa == 'w':
            if not chat_session_id:
                chat_session_id = await self._create_session(content=content_append)
            else:
                sql_expression_2 = "UPDATE chat_session SET content = %s WHERE chat_session_id = %s"
                await self.maica_pool.query_modify(expression=sql_expression_2, values=(content_append, chat_session_id))
            return chat_session_id, 0

        elif irwa == 'a':
            cut_status, content_finale = await self._chop_session(chat_session_id, content_finale)
            if not chat_session_id:
                chat_session_id = await self._create_session(content=content_finale)
            else:
                sql_expression_2 = "UPDATE chat_session SET content = %s WHERE chat_session_id = %s"
                await self.maica_pool.query_modify(expression=sql_expression_2, values=(content_finale, chat_session_id))
            return chat_session_id, cut_status

    async def reset_chat_session(self, chat_session_num=None, content_new=None) -> bool:
        """The difference between this and rw_chat_session is that this one archives."""
        self._check_essentials()

        if not chat_session_num:
            chat_session_num = self.settings.temp.chat_session
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
        if not isinstance(content_restore, str):
            content_restore = self._flattern_chat_session(content_restore)

        return await self.reset_chat_session(content_new=content_restore)

    async def find_ms_cache(self, hash_identity) -> Optional[str]:
        """Find ms cache with corresponding prompt hash."""

        sql_expression_1 = "SELECT content FROM ms_cache WHERE hash = %s"
        result = await self.maica_pool.query_get(expression=sql_expression_1, values=(hash_identity))
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
        self.sf_inst = SfBoundCoroutine(self.fsc)
        self.mfocus_coro = MFocusCoroutine(self.fsc, self.mf_p, )



class WsCoroutine(NoWsCoroutine):
    """
    Force ws existence.
    Also has AI sockets.
    """

    def __init__(self, websocket, auth_pool: DbPoolCoroutine, maica_pool: DbPoolCoroutine, mcore_conn: AiConnCoroutine, mfocus_conn: AiConnCoroutine):
        super().__init__(auth_pool=auth_pool, maica_pool=maica_pool, websocket=websocket)
        
        self.fsc.rsc.websocket = websocket
        mcore_conn.init_rsc(self.fsc.rsc); mfocus_conn.init_rsc(self.fsc.rsc)
        self.mcore_conn, self.mfocus_conn = mcore_conn, mfocus_conn
        self.fsc.mcore_conn, self.fsc.mfocus_conn = mcore_conn, mfocus_conn

    # Stage 1 permission check

    async def check_permit(self):
        global online_dict
        websocket = self.websocket
        await messenger(info='An anonymous connection initiated', color=colorama.Fore.LIGHTBLUE_EX)
        await messenger(info=f'Current online users: {list(online_dict.keys())}', color=colorama.Fore.LIGHTBLUE_EX)

        # Starting loop from here

        while True:
            try:

                # Initiation
                self.flush_traceray()
                self.settings.identity.reset()
                self.settings.verification.reset()
                recv_text = await websocket.recv()
                await messenger(info=f'Recieved an input on stage1.', color=colorama.Fore.CYAN)

                # Context security check first
                if len(recv_text) > 4096:
                    error = MaicaInputWarning('Input length exceeded', '413')
                    await messenger(websocket, "input_length_exceeded", traceray_id=self.traceray_id, error=error)
                try:
                    recv_loaded_json = json.loads(recv_text)
                except Exception:
                    error = MaicaInputWarning('Request body not JSON', '400')
                    await messenger(websocket, "request_body_not_json", traceray_id=self.traceray_id, error=error)
                try:
                    recv_token = recv_loaded_json['token']
                except Exception:
                    error = MaicaInputWarning('Request contains no token', '405')
                    await messenger(websocket, "request_body_no_token", traceray_id=self.traceray_id, error=error)

                # Initiate account check
                verification_result = await self.hasher.hashing_verify(access_token=recv_token)
                if verification_result[0]:

                    # Account security check
                    checked_status = await self.check_user_status(key='banned')
                    if not checked_status[0]:
                        error = MaicaDbError('Account service failed', '502')
                        try:
                            error.message += f": {str(checked_status[1])}"
                        except Exception:
                            error.message += ", no reason provided"
                        await messenger(websocket, "auth_db_failure", traceray_id=self.traceray_id, error=error)
                    elif checked_status[3]:
                        error = MaicaPermissionError('Account banned by MAICA', '403')
                        await messenger(websocket, "maica_account_banned", traceray_id=self.traceray_id, error=error)
                    else:
                        if self.settings.verification.user_id in online_dict:
                            if load_env("KICK_STALE_CONNS") == "0":
                                self.settings.verification.reset()
                                error = MaicaConnectionWarning('A connection was established already and kicking not enabled', '406')
                                await messenger(websocket, 'maica_connection_reuse_denied', traceray_id=self.traceray_id, error=error)
                            else:
                                await messenger(websocket, "maica_connection_reuse_attempt", "A connection was established already", "300", self.traceray_id)
                                stale_conn, stale_lock = online_dict[self.settings.verification.user_id]
                                try:
                                    await messenger(stale_conn, 'maica_connection_reuse_stale', 'A new connection has been established', '300', self.traceray_id)
                                    await stale_conn.close(1000, 'Displaced as stale')
                                except Exception:
                                    await messenger(None, 'maica_connection_stale_dead', 'The stale connection has died already', '204')
                                try:
                                    online_dict.pop(self.settings.verification.user_id)
                                except Exception:
                                    pass
                                async with stale_lock:
                                    await messenger(None, 'maica_connection_stale_kicked', 'The stale connection is kicked', '204')
                        self.cookie = cookie = str(uuid.uuid4())
                        self.enforce_cookie = False
                        await messenger(websocket, 'maica_login_succeeded', 'Authentication passed', '201', type='info', color=colorama.Fore.LIGHTCYAN_EX)
                        await messenger(websocket, 'maica_login_id', f"{self.settings.verification.user_id}", '200')
                        await messenger(websocket, 'maica_login_user', f"{self.settings.verification.username}", '200')
                        await messenger(websocket, 'maica_login_nickname', f"{self.settings.verification.nickname}", '200', no_print=True)
                        await messenger(websocket, 'maica_connection_security_cookie', cookie, '200', no_print=True)

                        return {'id': self.settings.verification.user_id, 'username': self.settings.verification.username}
                else:
                    if isinstance(verification_result[1], dict):
                        if 'f2b' in verification_result[1]:
                            error = MaicaPermissionError(f'Account locked by Fail2Ban, {verification_result[1]['f2b']} seconds remaining', '429')
                            await messenger(websocket, 'maica_login_denied_fail2ban', traceray_id=self.traceray_id, error=error)
                        elif 'necf' in verification_result[1]:
                            error = MaicaPermissionError(f'Account Email not verified, check inbox and retry', '401')
                            await messenger(websocket, 'maica_login_denied_email', traceray_id=self.traceray_id, error=error)
                        elif 'pwdw' in verification_result[1]:
                            error = MaicaPermissionWarning(f'Password hashing failed {verification_result[1]['pwdw']} times, check password and retry', '403')
                            await messenger(websocket, 'maica_login_denied_password', traceray_id=self.traceray_id, error=error)
                    else:
                        error = MaicaPermissionError(verification_result[1], '400')
                        await messenger(websocket, 'maica_login_denied_rsa', traceray_id=self.traceray_id, error=error)

            # Handle expected exceptions

            except CommonMaicaException as ce:
                if ce.is_critical():
                    return 2
                elif ce.is_breaking():
                    return 1
                else:
                    continue

            except websockets.exceptions.WebSocketException:
                await messenger(None, 'maica_connection_terminated', 'Connection passively terminated', '204')
                return 0

            # Handle unexpected exceptions

            except Exception as e:
                traceback.print_exc()
                return 3

    
    # Stage 2 function router

    async def function_switch(self):

        # Initiation

        websocket, mcore_conn = self.websocket, self.mcore_conn

        await messenger(websocket, "maica_connection_established", "MAICA connection established", "201", type='info', no_print=True)
        await messenger(websocket, "maica_provider_anno", f"Current service provider is {load_env('DEV_IDENTITY')}", "200", type='info', no_print=True)

        # Starting loop from here

        while True:
            try:

                # Initiation

                self.flush_traceray()
                return_status = 0

                # Context security check first

                checked_status = await self.check_user_status(key='banned')
                if not checked_status[0]:
                    error = MaicaDbError('Account service failed', '502')
                    try:
                        error.message += f": {str(checked_status[1])}"
                    except Exception:
                        error.message += ", no reason provided"
                    await messenger(websocket, "auth_db_failure", traceray_id=self.traceray_id, error=error)
                elif checked_status[3]:
                    error = MaicaPermissionError('Account banned by MAICA', '403')
                    await messenger(websocket, "maica_account_banned", traceray_id=self.traceray_id, error=error)

                # Then we examine the input

                recv_text = await websocket.recv()
                await messenger(info=f'Recieved an input on stage2: {recv_text}', color=colorama.Fore.CYAN)

                # Then context validation

                if len(recv_text) > 4096:
                    error = MaicaInputWarning('Input length exceeded', '413')
                    await messenger(websocket, "input_length_exceeded", traceray_id=self.traceray_id, error=error)
                try:
                    recv_loaded_json: dict = json.loads(recv_text)
                except Exception:
                    error = MaicaInputWarning('Request body not JSON', '400')
                    await messenger(websocket, "request_body_not_json", traceray_id=self.traceray_id, error=error)
                try:
                    recv_type = recv_loaded_json['type']
                except Exception:
                    recv_type = 'unknown'
                    await messenger(websocket, "future_warning", "Requests with no type declaration will be deprecated in the future", "426")

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
                    case placeholder if "chat_params" in recv_loaded_json:
                        return_status = await self.def_model(recv_loaded_json)
                    case placeholder if "chat_session" in recv_loaded_json:
                        return_status = await self.do_communicate(recv_loaded_json)
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

            except websockets.exceptions.WebSocketException:
                await messenger(None, 'maica_connection_terminated', 'Connection passively terminated', '204')
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

        replace_generation = ''; ms_cache_identity = ''
        self.settings.temp.reset()
        try:

            # Param assertions here

            try:
                chat_session = int(default(recv_loaded_json.get('chat_session'), 0))
                assert -1 <= chat_session < 10, "Wrong chat_session range"
                self.settings.temp.update(self.fsc.rsc, chat_session=chat_session)
            except Exception as e:
                error = MaicaInputWarning(str(e), '405')
                await messenger(websocket, 'maica_query_denied', traceray_id=self.traceray_id, error=error)

            if 'reset' in recv_loaded_json:
                if recv_loaded_json['reset']:
                    user_id = self.settings.verification.user_id
                    purge_result = await self.reset_chat_session(self.settings.temp.chat_session)
                    if not purge_result[0]:
                        error = MaicaDbError('Chat session resetting failed', '502')
                        try:
                            error.message += f": {str(purge_result[1])}"
                        except Exception:
                            error.message += ", no reason provided"
                        await messenger(websocket, "maica_db_failure", traceray_id=self.traceray_id, error=error)
                    elif purge_result[2]:
                        await messenger(websocket, "maica_session_nout_found", "Determined chat_session doesn't exist", "302", self.traceray_id)
                        return 0
                    else:
                        await messenger(websocket, "maica_session_reset", "Determined chat_session reset", "204", self.traceray_id)
                        return 0
 
            if 'inspire' in recv_loaded_json and not query_in:
                if recv_loaded_json['inspire']:
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
                            await messenger(websocket, "mspire_scraping_failed", traceray_id=self.traceray_id, error=error, type="error")
                        elif str(query_insp[1]) == 'mspire_title_insane':
                            error = MaicaInputWarning('MSpire prompt not found on wikipedia', '410')
                            await messenger(websocket, "mspire_prompt_bad", traceray_id=self.traceray_id, error=error)
                        else:
                            error = MaicaInternetWarning('MSpire failed connecting wikipedia', '408')
                            await messenger(websocket, "mspire_conn_failed", traceray_id=self.traceray_id, error=error, type="error")
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
                    if isinstance(recv_loaded_json['postmail'], dict):
                        query_insp = await mtools.make_postmail(**recv_loaded_json['postmail'], target_lang=self.settings.basic.target_lang)
                        # We're using the old school way to avoid using eval()
                        if default(recv_loaded_json['postmail'].get('bypass_mf'), False):
                            self.settings.temp.update(self.fsc.rsc, bypass_mf=True)
                        if default(recv_loaded_json['postmail'].get('bypass_mt'), False):
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
                        error = MaicaInputWarning('Wrong MPostal request format', '405')
                        await messenger(websocket, 'mpostal_input_bad', traceray_id=self.traceray_id, error=error)
                    
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
                    self.mt_inst.add_extra(**recv_loaded_json['trigger'])
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
                        message_agent_wrapped = await mfocus.agenting(self.fsc, query_in)

                        if message_agent_wrapped[0] == 'EMPTY':
                            if len(message_agent_wrapped[1]) > 5:
                                await messenger(websocket, 'maica_agent_using_inst', 'MFocus got instruction and used', '200')
                                agent_info = message_agent_wrapped[1]
                            else:
                                await messenger(websocket, 'maica_agent_no_inst', 'MFocus got no instruction, falling back and proceeding', '404', traceray_id=self.traceray_id)
                                agent_info = ''

                        elif message_agent_wrapped[0] == 'FAIL':
                            await messenger(websocket, 'maica_agent_no_tool', 'MFocus called no tool', '204')
                            agent_info = ''

                        else:
                            # We are defaulting instructed guidance because its more clear pattern
                            # But if pointer entered this section, user must used mf_aggressive or something went wrong
                            if len(message_agent_wrapped[1]) > 5 and len(message_agent_wrapped[0]) > 5:
                                await messenger(websocket, 'maica_agent_using_conc', 'MFocus got conclusion and used', '200')
                                agent_info = message_agent_wrapped[0]
                            elif len(message_agent_wrapped[1]) > 5:
                                # Conclusion likely failed, but at least there is instruction
                                await messenger(websocket, 'maica_agent_no_conc', 'MFocus got no conclusion, likely failed', '404', traceray_id=self.traceray_id)
                                agent_info = ''
                            else:
                                await messenger(websocket, 'maica_agent_no_inst', 'MFocus got no instruction, falling back and proceeding', '404', traceray_id=self.traceray_id)
                                agent_info = ''
                        # Everything should be grabbed by now

                    else:
                        self.settings.temp.update(self.fsc.rsc, bypass_mf=False)
                        agent_info=''
                    
                    prompt = await self.gen_system_prompt
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
            await messenger(None, 'maica_chat_query_ready', f'Query constrcted and ready to go, last input is:\n{query_in}\nSending query...', '206', color=colorama.Fore.LIGHTCYAN_EX)

            if not self.settings.temp.bypass_gen or not replace_generation: # They should present together

                # Generation here

                resp = await self.mcore_conn.make_completion(**completion_args)

                if completion_args['stream']:
                    reply_appended = ''

                    async for chunk in resp:
                        token = chunk.choices[0].delta.content
                        if token:
                            await asyncio.sleep(0)
                            await messenger(websocket, 'maica_core_streaming_continue', token, '100')
                            reply_appended += token
                    await messenger(info='\n', type='plain')
                    await messenger(websocket, 'maica_core_streaming_done', f'Streaming finished with seed {completion_args['seed']} for {self.settings.verification.username}', '1000', traceray_id=self.traceray_id)
                else:
                    reply_appended = resp.choices[0].message.content
                    await messenger(websocket, 'maica_core_nostream_reply', reply_appended, '200', type='carriage')
                    await messenger(None, 'maica_core_nostream_done', f'Reply sent with seed {completion_args['seed']} for {self.settings.verification.username}', '1000', traceray_id=self.traceray_id)

            else:

                # We just pretend it was generated

                reply_appended = replace_generation
                if completion_args['stream']:
                    await messenger(websocket, 'maica_core_streaming_continue', reply_appended, '100'); await messenger(info='\n', type='plain')
                    await messenger(websocket, 'maica_core_streaming_done', f'Streaming finished with cache for {self.settings.verification.username}', '1000', traceray_id=self.traceray_id)
                else:
                    await messenger(websocket, 'maica_core_nostream_reply', reply_appended, '200', type='carriage')
                    await messenger(None, 'maica_core_nostream_done', f'Reply sent with cache for {self.settings.verification.username}', '1000', traceray_id=self.traceray_id)

            # Can be post-processed here

            reply_appended = await wrap_run_in_exc(None, post_proc.filter_format, reply_appended, self.settings.basic.target_lang)
            reply_appended_insertion = json.dumps({'role': 'assistant', 'content': reply_appended}, ensure_ascii=False)

            if self.settings.basic.enable_mt and not self.settings.temp.bypass_mt:
                task_trigger_resp = asyncio.create_task(mtrigger.wrap_triggering(self, query_in, reply_appended, self.settings.temp.chat_session))
                await task_trigger_resp
                trigger_resp = task_trigger_resp.result()
            else:
                self.settings.temp.update(self.fsc.rsc, bypass_mt=False)
                trigger_resp = (False, None)

            if self.settings.temp.ms_cache and not self.settings.temp.bypass_gen and not replace_generation:
                await self.store_ms_cache(ms_cache_identity, reply_appended)

            trigger_succ, trigger_sce = trigger_resp
            if trigger_succ:
                await messenger(websocket, 'maica_trigger_done', trigger_sce, '1010')
            else:
                if trigger_sce:
                    error = MaicaResponseError('MTrigger failed to response', '502')
                    await messenger(websocket, 'maica_trigger_failed', traceray_id=self.traceray_id, error=error)
                else:
                    await messenger(None, 'maica_trigger_empty', 'No trigger passed in', '200')

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



#异步标记程序, 不是必要的. 万一要用呢?

def callback_func_switch(future):
    pass

def callback_check_permit(future):
    pass
    
#主要线程驱动器

async def main_logic(websocket, auth_pool, maica_pool, mcore_conn, mfocus_conn):
    unique_lock = asyncio.Lock()
    async with unique_lock:
        try:
            global online_dict
            loop = asyncio.get_event_loop()
            thread_instance = WsCoroutine(websocket, auth_pool=auth_pool, maica_pool=maica_pool, mcore_conn=mcore_conn, mfocus_conn=mfocus_conn)

            permit = await thread_instance.check_permit()
            assert isinstance(permit, dict) and permit[0], "Recieved a return state"

            online_dict[permit['id']] = [websocket, unique_lock]
            await messenger(info=f"Locking session for {permit['id']} named {permit['username']}")

            return_status = await thread_instance.function_switch()
            # If function switch returned, something must have went wrong
            if return_status:
                raise Exception(return_status)

        except Exception as excepted:
            match str(excepted):
                case '0':
                    await messenger(info=f'Function quitted. Likely connection loss.', color=colorama.Fore.LIGHTBLUE_EX)
                case '1':
                    await messenger(info=f'Function broke by a warning.', type='warn')
                case '2':
                    await messenger(info=f'Function broke by a critical', type='error')
                case '3':
                    await messenger(info=f'Function broke by an unknown exception', type='error')

        finally:
            try:
                online_dict.pop(permit[2])
                await messenger(info=f"Lock released for {permit[2]} as {permit[3]}")
            except Exception:
                await messenger(info=f"No lock for this connection")
            await websocket.close()
            await websocket.wait_closed()
            await messenger(info=f"Closing connection gracefully")



async def prepare_thread(**kwargs):
    auth_pool = default(kwargs.get('auth_pool'), ConnUtils.auth_pool())
    maica_pool = default(kwargs.get('maica_pool'), ConnUtils.maica_pool())
    mcore_conn: AiConnCoroutine = default(kwargs.get('mcore_conn'), ConnUtils.mcore_conn())
    mfocus_conn: AiConnCoroutine = default(kwargs.get('mfocus_conn'), ConnUtils.mfocus_conn())

    try:
        await messenger(info=f"Main model is {mcore_conn.model_actual}, MFocus model is {mfocus_conn.model_actual}", color=colorama.Fore.MAGENTA)
    except Exception:
        await messenger(info=f"Model deployment cannot be reached -- running in minimal testing mode", color=colorama.Fore.MAGENTA)
    
    server = await websockets.serve(functools.partial(main_logic, **kwargs), '0.0.0.0', 5000)
    await server.wait_closed()

def run_ws(**kwargs):
    global online_dict
    online_dict = {}

    asyncio.run(messenger(info='Starting WS server!' if load_env('DEV_STATUS') == 'serving' else 'Starting WS server in development mode!', color=colorama.Fore.LIGHTMAGENTA_EX))
    asyncio.run(prepare_thread(**kwargs))

    asyncio.run(messenger(info='Stopping WS server!', color=colorama.Fore.MAGENTA))

if __name__ == '__main__':

    # Pool wrappings init here

    auth_pool, maica_pool, mcore_conn, mfocus_conn = ConnUtils.auth_pool(), ConnUtils.maica_pool(), ConnUtils.mcore_conn(), ConnUtils.mfocus_conn()

    run_ws(auth_pool=auth_pool, maica_pool=maica_pool, mcore_conn=mcore_conn, mfocus_conn=mfocus_conn)