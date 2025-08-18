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
from typing import Union, Optional
from Crypto.Random import random as CRANDOM
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
        self.fsc = FullSocketsContainer(self.websocket, self.traceray_id, self.settings)
        self.acc = AccountCursor(self.fsc, self.auth_pool, self.maica_pool)

    def check_essentials(self) -> None:
        if not self.settings.verification.user_id:
            error = MaicaPermissionError('Essentials not implemented', '403')
            asyncio.run(common_context_handler(self.websocket, 'common_essentials_missing', traceray_id=self.traceray_id, error=error))

    async def chop_session(self, chat_session_id, content) -> list[int, str]:
        max_length_ascii = self.settings.basic.max_length * 3
        warn_length_ascii = int(max_length_ascii * (2/3))
        len_content_actual = len(content.encode()) - len(json.loads(f'[{content}]')) * 31
        if len_content_actual >= max_length_ascii:
            # First we check if there is a cchop avaliable
            sql_expression = 'SELECT * FROM cchop_archived WHERE chat_session_id = %s ORDER BY archive_id DESC'
            result = await self.maica_pool.query_get(expression=sql_expression, values=(chat_session_id))
            # We create a dummy for empty sql result case
            use_result = []
            if result and not result[3]:
                use_result = result
                archive_id = use_result[0]
            if not use_result:
                sql_expression2 = 'INSERT INTO cchop_archived (chat_session_id, content, archived) VALUES (%s, "", 0)'
                archive_id = await self.maica_pool.query_modify(expression=sql_expression2, values=(chat_session_id))
                use_result = [archive_id, chat_session_id, '', 0]
            archive_content = use_result[2]
            # Now an avaliable cchop should be ready

            def cpub_chop_session():
                nonlocal content, len_content_actual, warn_length_ascii, archive_content
                cutting_mat = json.loads(f"[{content}]")
                while len_content_actual >= warn_length_ascii or cutting_mat[1]['role'] == "assistant":
                    if archive_content:
                        archive_content = archive_content + ', '
                    popped_dict = cutting_mat.pop(1)
                    archive_content = archive_content + json.dumps(popped_dict, ensure_ascii=False)
                    len_content_actual -= (len(json.dumps(popped_dict, ensure_ascii=False).encode()) - 31)
                content = json.dumps(cutting_mat, ensure_ascii=False).strip('[').strip(']')

            # Wrapping this makes it non-blocking
            await wrap_run_in_exc(None, cpub_chop_session)
            sql_expression3 = 'UPDATE cchop_archived SET content = %s WHERE archive_id = %s' if len(archive_content) <= 100000 else 'UPDATE cchop_archived SET content = %s, archived = 1 WHERE archive_id = %s'
            await self.maica_pool.query_modify(expression=sql_expression3, values=(archive_content, archive_id))
            cutted = 1
        elif len_content_actual >= warn_length_ascii:
            cutted = 2
        else:
            cutted = 0
        return cutted, content

    def flush_traceray(self) -> None:
        self.traceray_id = str(CRANDOM.randint(0,9999999999)).zfill(10)

    async def init_side_instance(self) -> None:
        success = False
        user_id = self.settings.verification.user_id
        try:
            self.check_essentials()
            self.sf_inst, self.mt_inst = mfocus.SfBoundCoroutine(user_id, 1), mtrigger.MtBoundCoroutine(user_id, 1)
            await asyncio.gather(self.sf_inst.init1(), self.mt_inst.init1())
        except Exception as excepted:
            #traceback.print_exc()
            success = False
            return success, excepted

    async def rw_chat_session(self, chat_session_num, rw, content_append) -> list[bool, Exception, int, str, int]:
        success = False
        user_id = self.settings.verification.user_id
        try:
            self.check_essentials()
            if rw == 'r':
                sql_expression = "SELECT * FROM chat_session WHERE user_id = %s AND chat_session_num = %s"
                try:
                    result = await self.maica_pool.query_get(expression=sql_expression, values=(user_id, chat_session_num))
                    if content_append is None:
                        content_append = ''
                    elif len(result[3]) != 0:
                        content_append = ',' + content_append
                    chat_session_id = result[0]
                    content = result[3] + content_append
                    success = True
                    return success, None, chat_session_id, content
                except Exception as excepted:
                    success = False
                    return success, excepted
            elif rw == 'w':
                sql_expression1 = "SELECT * FROM chat_session WHERE user_id = %s AND chat_session_num = %s"
                try:
                    result = await self.maica_pool.query_get(expression=sql_expression1, values=(user_id, chat_session_num))
                    #success = True
                    chat_session_id = result[0]
                    content = result[3]
                except Exception as excepted:
                    success = False
                    return success, excepted
                if len(content) != 0:
                    content = content + ',' + content_append
                else:
                    content = content_append

                cutted, content = await self.chop_session(chat_session_id, content)

                sql_expression2 = "UPDATE chat_session SET content = %s WHERE chat_session_id = %s"
                try:
                    await self.maica_pool.query_modify(expression=sql_expression2, values=(content, chat_session_id))
                    success = True
                    return success, None, chat_session_id, None, cutted
                except Exception as excepted:
                    success = False
                    return success, excepted
        except Exception as excepted:
            success = False
            return success, excepted
        
    async def reset_chat_session(self, chat_session_num) -> list[bool, Exception, bool]:
        success = False
        user_id = self.settings.verification.user_id
        try:
            self.check_essentials()
            sql_expression1 = "SELECT chat_session_id, content FROM chat_session WHERE user_id = %s AND chat_session_num = %s"
            result = await self.maica_pool.query_get(expression=sql_expression1, values=(user_id, chat_session_num))
            if not result or len(result) == 0:
                success = True
                inexist = True
                return success, None, inexist
            else:
                chat_session_id = result[0]
                content_to_archive = result[1]
                sql_expression2 = "UPDATE chat_session SET content = %s WHERE chat_session_id = %s"
                content = f'{{"role": "system", "content": "{global_init_system('[player]', self.settings.basic.target_lang)}"}}'
                await self.maica_pool.query_modify(expression=sql_expression2, values=(content, chat_session_id))
                sql_expression3 = "INSERT INTO csession_archived (chat_session_id, content) VALUES (%s, %s)"
                await self.maica_pool.query_modify(expression=sql_expression3, values=(chat_session_id, content_to_archive))
                sql_expression4 = "UPDATE cchop_archived SET archived = 1 WHERE chat_session_id = %s"
                await self.maica_pool.query_modify(expression=sql_expression4, values=(chat_session_id))
                success = True
                inexist = False
                return success, None, inexist
        except Exception as excepted:
            success = False
            return success, excepted
        
    async def restore_chat_session(self, chat_session_num, restore_content) -> list[bool, Exception]:
        success = False
        user_id = self.settings.verification.user_id
        try:
            self.check_essentials()
            sql_expression1 = "UPDATE chat_session SET content = %s WHERE chat_session_id = %s"
            if not isinstance(restore_content, str):
                restore_content = json.dumps(restore_content, ensure_ascii=False).strip('[').strip(']')
            await self.check_create_chat_session(chat_session_num)
            await self.maica_pool.query_modify(expression=sql_expression1, values=(restore_content, chat_session_num))
            success = True
            return success, None
        except Exception as excepted:
            success = False
            return success, excepted
        
    async def check_create_chat_session(self, chat_session_num) -> list[bool, Exception, bool, int]:
        success = False
        exist = None
        chat_session_id = None
        user_id = self.settings.verification.user_id
        try:
            self.check_essentials()
            sql_expression1 = "SELECT chat_session_id FROM chat_session WHERE user_id = %s AND chat_session_num = %s"
            result = await self.maica_pool.query_get(expression=sql_expression1, values=(user_id, chat_session_num))
            if result:
                chat_session_id = result[0]
                success = True
                exist = True
            else:
                sql_expression2 = "INSERT INTO chat_session VALUES (NULL, %s, %s, '')"
                chat_session_id = await self.maica_pool.query_modify(expression=sql_expression2, values=(user_id, chat_session_num))
                sql_expression3 = "UPDATE chat_session SET content = %s WHERE chat_session_id = %s"
                content = f'{{"role": "system", "content": "{global_init_system('[player]', self.settings.basic.target_lang)}"}}'
                await self.maica_pool.query_modify(expression=sql_expression3, values=(content, chat_session_id))
                success = True
                exist = False
            return success, None, exist, chat_session_id
        except Exception as excepted:
            success = False
            return success, excepted, exist, chat_session_id

    async def check_get_hashed_cache(self, hash_identity) -> list[bool, Exception, bool, str]:
        success = False
        exist = None
        content = ''
        timestamp = str(time.time())
        try:
            sql_expression1 = "SELECT spire_id, content FROM ms_cache WHERE hash = %s"
            result = await self.maica_pool.query_get(expression=sql_expression1, values=(hash_identity))
            if result:
                spire_id, content = result
                sql_expression2 = "UPDATE ms_cache SET timestamp = %s WHERE spire_id = %s"
                await self.maica_pool.query_modify(expression=sql_expression2, values=(timestamp, spire_id))
                success = True
                exist = True
                await common_context_handler(None, 'maica_spire_cache_hit', 'Hit a stored cache for MSpire', '200')
            else:
                success = True
                exist = False
                await common_context_handler(None, 'maica_spire_cache_missed', 'No stored cache for MSpire', '200')
            return success, None, exist, content
        except Exception as excepted:
            traceback.print_exc()
            success = False
            return success, excepted, exist, content
        
    async def store_hashed_cache(self, hash_identity, content) -> list[bool, Exception]:
        success = False
        timestamp = str(time.time())
        try:
            sql_expression1 = "INSERT INTO ms_cache VALUES (NULL, %s, %s, %s)"
            spire_id = await self.maica_pool.query_modify(expression=sql_expression1, values=(hash_identity, timestamp, content))
            success = True
            await common_context_handler(None, 'maica_spire_cache_stored', 'Stored a cache for MSpire', '200')
            return success, None
        except Exception as excepted:
            traceback.print_exc()
            success = False
            return success, excepted

    async def mod_chat_session_system(self, chat_session_num, new_system_init) -> list[bool, Exception, int]:
        success = False
        chat_session_id = None
        user_id = self.settings.verification.user_id
        sql_expression1 = "SELECT * FROM chat_session WHERE user_id = %s AND chat_session_num = %s"
        try:
            self.check_essentials()
            result = await self.maica_pool.query_get(expression=sql_expression1, values=(user_id, chat_session_num))
            if not result:
                chat_session_id = (await self.check_create_chat_session(chat_session_num))[3]
                sql_expression2 = "SELECT * FROM chat_session WHERE chat_session_id = %s"
                result = await self.maica_pool.query_get(expression=sql_expression2, values=(chat_session_id))
            chat_session_id = result[0]
            content = result[3]
            modding_mat = json.loads(f'[{content}]')
            modding_mat[0]['content'] = new_system_init
            content = json.dumps(modding_mat, ensure_ascii=False).strip('[').strip(']')
            sql_expression3 = "UPDATE chat_session SET content = %s WHERE chat_session_id = %s"
            await self.maica_pool.query_modify(expression=sql_expression3, values=(content, chat_session_id))
            success = True
            return success, None, chat_session_id
        except Exception as excepted:
            traceback.print_exc()
            success = False
            return success, excepted

    async def gen_a_system(self, chat_session_num, known_info, strict_conv=True) -> list[bool, Exception, str]:
        user_id = self.settings.verification.user_id
        try:
            self.check_essentials()
            if self.settings.basic.sf_extraction or self.settings.temp.sf_extraction_once:
                player_name_get = await wrap_run_in_exc(None, self.sf_inst.read_from_sf, 'mas_playername')
                if player_name_get[0]:
                    if self.settings.extra.sfe_aggressive:
                        player_name = player_name_get[2]
                        if known_info:
                            known_info = re.sub(r'\[player\]', player_name, known_info)
                    else:
                        player_name = '[player]'
                else:
                    player_name = '[player]'
                    # continue on failure - playername may not be specified
            else:
                player_name = '[player]'
            new_system = global_init_system(player_name, self.settings.basic.target_lang, strict_conv)
            if self.settings.extra.nsfw_acceptive:
                new_system += f" 你应当允许用户提出私密性的要求, 并给出宽容接纳的正面回答." if self.settings.basic.target_lang == 'zh' else f" You should accept NSFW and private queries and respond positively with acceptance and tolerance."
            if known_info:
                new_system += f" 以下是一些相关信息, 你可以参考其中有价值的部分, 并用你自己的语言方式作答: {known_info}" if self.settings.basic.target_lang == 'zh' else f" Here are some information you can refer to, then make your answer in your own way: {known_info}"
            success = True
            return success, None, new_system
        except Exception as excepted:
            success = False
            #traceback.print_exc()
            return success, excepted

    async def wrap_mod_system(self, chat_session_num, known_info, strict_conv=True) -> list[bool, Exception, int]:
        new_system_res = await self.gen_a_system(chat_session_num, known_info, strict_conv)
        try:
            new_system = new_system_res[2]
            return await self.mod_chat_session_system(chat_session_num, new_system)
        except Exception as excepted:
            success = False
            #traceback.print_exc()
            return success, excepted
        
    async def mod_once_system(self, chat_session_num, known_info, strict_conv=True) -> list[bool, Exception, str]:
        return await self.gen_a_system(chat_session_num, known_info, strict_conv)
    

#没有必要实例化的方法

def global_init_system(player_name, target_lang='zh', strict_conv=True):
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

#与websocket绑定的异步化类, 继承sql类

class WsCoroutine(NoWsCoroutine):
    """
    Force ws existence.
    Also has AI sockets.
    """

    def __init__(self, websocket, auth_pool: DbPoolCoroutine, maica_pool: DbPoolCoroutine, mcore_conn: AiConnCoroutine, mfocus_conn: AiConnCoroutine):
        super().__init__(auth_pool=auth_pool, maica_pool=maica_pool, websocket=websocket)
        self.fsc.rsc.websocket = websocket
        self.mcore_conn, self.mfocus_conn = mcore_conn, mfocus_conn

    # Stage 1 permission check

    async def check_permit(self):
        global online_dict
        websocket = self.websocket
        await common_context_handler(info='An anonymous connection initiated', color=colorama.Fore.LIGHTBLUE_EX)
        await common_context_handler(info=f'Current online users: {list(online_dict.keys())}', color=colorama.Fore.LIGHTBLUE_EX)

        # Starting loop from here

        while True:
            try:

                # Initiation

                self.flush_traceray()
                self.settings.identity.reset()
                self.settings.verification.reset()
                recv_text = await websocket.recv()
                await common_context_handler(info=f'Recieved an input on stage1.', color=colorama.Fore.CYAN)

                # Context security check first

                if len(recv_text) > 4096:
                    error = MaicaInputWarning('Input length exceeded', '413')
                    await common_context_handler(websocket, "input_length_exceeded", traceray_id=self.traceray_id, error=error)
                try:
                    recv_loaded_json = json.loads(recv_text)
                except Exception:
                    error = MaicaInputWarning('Request body not JSON', '400')
                    await common_context_handler(websocket, "request_body_not_json", traceray_id=self.traceray_id, error=error)
                try:
                    recv_token = recv_loaded_json['token']
                except Exception:
                    error = MaicaInputWarning('Request contains no token', '405')
                    await common_context_handler(websocket, "request_body_no_token", traceray_id=self.traceray_id, error=error)

                # Initiate account check

                verification_result = await self.acc.hashing_verify(access_token=recv_token)
                if verification_result[0]:

                    # Account security check

                    checked_status = await self.check_user_status(key='banned')
                    if not checked_status[0]:
                        error = MaicaDbError('Account service failed', '502')
                        try:
                            error.message += f": {str(checked_status[1])}"
                        except Exception:
                            error.message += ", no reason provided"
                        await common_context_handler(websocket, "auth_db_failure", traceray_id=self.traceray_id, error=error)
                    elif checked_status[3]:
                        error = MaicaPermissionError('Account banned by MAICA', '403')
                        await common_context_handler(websocket, "maica_account_banned", traceray_id=self.traceray_id, error=error)
                    else:
                        if self.settings.verification.user_id in online_dict:
                            if load_env("KICK_STALE_CONNS") == "0":
                                self.settings.verification.reset()
                                error = MaicaConnectionWarning('A connection was established already and kicking not enabled', '406')
                                await common_context_handler(websocket, 'maica_connection_reuse_denied', traceray_id=self.traceray_id, error=error)
                            else:
                                await common_context_handler(websocket, "maica_connection_reuse_attempt", "A connection was established already", "300", self.traceray_id)
                                stale_conn, stale_lock = online_dict[self.settings.verification.user_id]
                                try:
                                    await common_context_handler(stale_conn, 'maica_connection_reuse_stale', 'A new connection has been established', '300', self.traceray_id)
                                    await stale_conn.close(1000, 'Displaced as stale')
                                except Exception:
                                    await common_context_handler(None, 'maica_connection_stale_dead', 'The stale connection has died already', '204')
                                try:
                                    online_dict.pop(self.settings.verification.user_id)
                                except Exception:
                                    pass
                                async with stale_lock:
                                    await common_context_handler(None, 'maica_connection_stale_kicked', 'The stale connection is kicked', '204')
                        self.cookie = cookie = str(uuid.uuid4())
                        self.enforce_cookie = False
                        await common_context_handler(websocket, 'maica_login_succeeded', 'Authentication passed', '201', type='info', color=colorama.Fore.LIGHTCYAN_EX)
                        await common_context_handler(websocket, 'maica_login_id', f"{self.settings.verification.user_id}", '200')
                        await common_context_handler(websocket, 'maica_login_user', f"{self.settings.verification.username}", '200')
                        await common_context_handler(websocket, 'maica_login_nickname', f"{self.settings.verification.nickname}", '200', no_print=True)
                        await common_context_handler(websocket, 'maica_connection_security_cookie', cookie, '200', no_print=True)

                        return {'id': self.settings.verification.user_id, 'username': self.settings.verification.username}
                else:
                    if isinstance(verification_result[1], dict):
                        if 'f2b' in verification_result[1]:
                            error = MaicaPermissionError(f'Account locked by Fail2Ban, {verification_result[1]['f2b']} seconds remaining', '429')
                            await common_context_handler(websocket, 'maica_login_denied_fail2ban', traceray_id=self.traceray_id, error=error)
                        elif 'necf' in verification_result[1]:
                            error = MaicaPermissionError(f'Account Email not verified, check inbox and retry', '401')
                            await common_context_handler(websocket, 'maica_login_denied_email', traceray_id=self.traceray_id, error=error)
                        elif 'pwdw' in verification_result[1]:
                            error = MaicaPermissionWarning(f'Password hashing failed {verification_result[1]['pwdw']} times, check password and retry', '403')
                            await common_context_handler(websocket, 'maica_login_denied_password', traceray_id=self.traceray_id, error=error)
                    else:
                        error = MaicaPermissionError(verification_result[1], '400')
                        await common_context_handler(websocket, 'maica_login_denied_rsa', traceray_id=self.traceray_id, error=error)

            # Handle expected exceptions

            except CommonMaicaException as ce:
                if ce.is_critical():
                    return 2
                elif ce.is_breaking():
                    return 1
                else:
                    continue

            except websockets.exceptions.WebSocketException:
                await common_context_handler(None, 'maica_connection_terminated', 'Connection passively terminated', '204')
                return 0

            # Handle unexpected exceptions

            except Exception as e:
                traceback.print_exc()
                return 3

    
    # Stage 2 function router

    async def function_switch(self):

        # Initiation

        websocket, mcore_conn = self.websocket, self.mcore_conn

        await common_context_handler(websocket, "maica_connection_established", "MAICA connection established", "201", type='info', no_print=True)
        await common_context_handler(websocket, "maica_provider_anno", f"Current service provider is {load_env('DEV_IDENTITY')}", "200", type='info', no_print=True)

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
                    await common_context_handler(websocket, "auth_db_failure", traceray_id=self.traceray_id, error=error)
                elif checked_status[3]:
                    error = MaicaPermissionError('Account banned by MAICA', '403')
                    await common_context_handler(websocket, "maica_account_banned", traceray_id=self.traceray_id, error=error)

                # Then we examine the input

                recv_text = await websocket.recv()
                await common_context_handler(info=f'Recieved an input on stage2: {recv_text}', color=colorama.Fore.CYAN)

                # Then context validation

                if len(recv_text) > 4096:
                    error = MaicaInputWarning('Input length exceeded', '413')
                    await common_context_handler(websocket, "input_length_exceeded", traceray_id=self.traceray_id, error=error)
                try:
                    recv_loaded_json: dict = json.loads(recv_text)
                except Exception:
                    error = MaicaInputWarning('Request body not JSON', '400')
                    await common_context_handler(websocket, "request_body_not_json", traceray_id=self.traceray_id, error=error)
                try:
                    recv_type = recv_loaded_json['type']
                except Exception:
                    recv_type = 'unknown'
                    await common_context_handler(websocket, "future_warning", "Requests with no type declaration will be deprecated in the future", "426")

                # Handle this cookie thing

                if recv_loaded_json.get('cookie'):
                    if str(recv_loaded_json['cookie']) == self.cookie:
                        if not self.enforce_cookie:
                            await common_context_handler(websocket, "security_cookie_accepted", "Cookie verification passed, enabling strict mode", "200", no_print=True)
                            self.enforce_cookie = True
                        else:
                            await common_context_handler(websocket, "security_cookie_correct", "Cookie verification passed", "200", no_print=True)
                    else:
                        error = MaicaPermissionError('Cookie provided but mismatch', '403')
                        await common_context_handler(websocket, 'security_cookie_mismatch', traceray_id=self.traceray_id, error=error)
                elif self.enforce_cookie:
                    error = MaicaPermissionError('Cookie enforced but missing', '403')
                    await common_context_handler(websocket, 'security_cookie_missing', traceray_id=self.traceray_id, error=error)

                # Route request

                match recv_type.lower():
                    case 'ping':
                        await common_context_handler(websocket, "pong", f"Ping recieved from {self.settings.verification.username} and responded", "200")
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
                        await common_context_handler(websocket, 'request_type_not_determined', traceray_id=self.traceray_id, error=error)

                if return_status and int(return_status) > 2:
                    error = CriticalMaicaError('Unexpected exception happened in child of stage2', '500')
                    await common_context_handler(websocket, 'maica_frame_critical', traceray_id=self.traceray_id, error=error)

            # Handle expected exceptions

            except CommonMaicaException as ce:
                if ce.is_critical():
                    return 2
                elif ce.is_breaking():
                    return 1
                else:
                    continue

            except websockets.exceptions.WebSocketException:
                await common_context_handler(None, 'maica_connection_terminated', 'Connection passively terminated', '204')
                return 0

            # Handle unexpected exceptions

            except Exception as e:
                traceback.print_exc()
                return 3



    #交互设置

    async def def_model(self, recv_loaded_json: dict):

        # Initiations

        websocket = self.websocket
        try:
            chat_params: dict = recv_loaded_json['chat_params']
            in_params = len(chat_params)
            accepted_params = self.settings.update(self.fsc.rsc, **chat_params)
            await common_context_handler(websocket, 'maica_params_accepted', f"{accepted_params} out of {in_params} settings accepted", "200")
            return 0
        
        # Handle input errors here

        except Exception as e:
            error = MaicaInputWarning(str(e), '405')
            await common_context_handler(websocket, 'maica_params_denied', traceray_id=self.traceray_id, error=error)

    #交互会话

    async def do_communicate(self, recv_loaded_json: dict):

        # Initiations

        websocket = self.websocket
        query_in = ''

        overall_info_system = ''; replace_generation = ''; ms_cache_identity = ''
        self.settings.temp.reset()
        try:

            # Param assertions here

            try:
                chat_session = int(default(recv_loaded_json.get('chat_session'), 0))
                assert -1 <= chat_session < 10, "Wrong chat_session range"
                self.settings.temp.update(self.fsc.rsc, chat_session=chat_session)
            except Exception as e:
                error = MaicaInputWarning(str(e), '405')
                await common_context_handler(websocket, 'maica_query_denied', traceray_id=self.traceray_id, error=error)

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
                        await common_context_handler(websocket, "maica_db_failure", traceray_id=self.traceray_id, error=error)
                    elif purge_result[2]:
                        await common_context_handler(websocket, "maica_session_nout_found", "Determined chat_session doesn't exist", "302", self.traceray_id)
                        return 0
                    else:
                        await common_context_handler(websocket, "maica_session_reset", "Determined chat_session reset", "204", self.traceray_id)
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
                            await common_context_handler(websocket, "mspire_scraping_failed", traceray_id=self.traceray_id, error=error, type="error")
                        elif str(query_insp[1]) == 'mspire_title_insane':
                            error = MaicaInputWarning('MSpire prompt not found on wikipedia', '410')
                            await common_context_handler(websocket, "mspire_prompt_bad", traceray_id=self.traceray_id, error=error)
                        else:
                            error = MaicaInternetWarning('MSpire failed connecting wikipedia', '408')
                            await common_context_handler(websocket, "mspire_conn_failed", traceray_id=self.traceray_id, error=error, type="error")
                    if self.settings.temp.ms_cache:
                        self.settings.temp.update(self.fsc.rsc, bypass_sup=True)
                        ms_cache_identity = query_insp[3]
                        cache_insp = await self.check_get_hashed_cache(ms_cache_identity)
                        if cache_insp[0] and cache_insp[2]:
                            self.settings.temp.update(self.fsc.rsc, bypass_gen=True)
                            replace_generation = cache_insp[3]
                            
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
                        await common_context_handler(websocket, 'mpostal_input_bad', traceray_id=self.traceray_id, error=error)
                    
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
            if self.settings.basic.sf_extraction and not self.settings.temp.bypass_mf:
                await self.sf_inst.init2(chat_session_num=self.settings.temp.chat_session)
                if 'savefile' in recv_loaded_json:
                    await wrap_run_in_exc(None, self.sf_inst.add_extra, recv_loaded_json['savefile'])
            elif 'savefile' in recv_loaded_json:
                self.settings.temp.update(self.fsc.rsc, sf_extraction_once=True)
                self.sf_inst.use_only(recv_loaded_json['savefile'])
            if self.settings.basic.mt_extraction and not self.settings.temp.bypass_mt:
                await self.mt_inst.init2(chat_session_num=self.settings.temp.chat_session)
                if 'trigger' in recv_loaded_json:
                    await wrap_run_in_exc(None, self.mt_inst.add_extra, recv_loaded_json['trigger'])
            elif 'trigger' in recv_loaded_json:
                self.settings.temp.update(self.fsc.rsc, mt_extraction_once=True)
                self.mt_inst.use_only(recv_loaded_json['trigger'])

            # Deprecated: The easter egg thing

            # global easter_exist
            # if easter_exist:
            #     easter_check = easter(query_in)
            #     if easter_check:
            #         await websocket.send(self.wrap_ws_deformatter('299', 'easter_egg', easter_check, 'info'))

            messages0 = json.dumps({'role': 'user', 'content': query_in}, ensure_ascii=False)
            match int(self.settings.temp.chat_session):
                case -1:

                    # chat_session == -1 means query contains an entire chat history(sequence mode)

                    session_type = -1
                    try:
                        messages = json.loads(query_in)
                        query_in = messages[-1]['text']
                        if len(messages) > 10:
                            error = MaicaInputWarning('Sequence exceeded 10 rounds for chat_session -1', '414')
                            await common_context_handler(websocket, 'maica_sequence_rounds_exceeded', traceray_id=self.traceray_id, error=error)
                    except Exception as excepted:
                        error = MaicaInputWarning('Sequence is not JSON for chat_session -1', '405')
                        await common_context_handler(websocket, 'maica_sequence_not_json', traceray_id=self.traceray_id, error=error)

                case i if 0 <= i < 10:

                    # chat_session == 0 means single round, else normal

                    session_type = 0 if i == 0 else 1

                    # Introducing MFocus

                    if self.settings.basic.enable_mf and not self.settings.temp.bypass_mf:

                        # From here MFocus is surely enabled

                        message_agent_wrapped = await mfocus.agenting(self.settings, )

                        if message_agent_wrapped[0] == 'EMPTY':
                            if len(message_agent_wrapped[1]) > 5:
                                await common_context_handler(websocket, 'maica_agent_using_inst', 'MFocus got instruction and used', '200')
                                info_agent_grabbed = message_agent_wrapped[1]
                            else:
                                await common_context_handler(websocket, 'maica_agent_no_inst', 'MFocus got no instruction, falling back and proceeding', '404', traceray_id=self.traceray_id)
                                info_agent_grabbed = ''
                        elif message_agent_wrapped[0] == 'FAIL':
                            await common_context_handler(websocket, 'maica_agent_no_tool', 'MFocus called no tool', '204')
                            info_agent_grabbed = ''
                        else:
                            # We are defaulting instructed guidance because its more clear pattern
                            # But if pointer entered this section, user must used mf_aggressive or something went wrong
                            if len(message_agent_wrapped[1]) > 5 and len(message_agent_wrapped[0]) > 5:
                                await common_context_handler(websocket, 'maica_agent_using_conc', 'MFocus got conclusion and used', '200')
                                info_agent_grabbed = message_agent_wrapped[0]
                            elif len(message_agent_wrapped[1]) > 5:
                                # Conclusion likely failed, but at least there is instruction
                                await common_context_handler(websocket, 'maica_agent_no_conc', 'MFocus got no conclusion, likely failed', '404', traceray_id=self.traceray_id)
                                info_agent_grabbed = ''
                            else:
                                await common_context_handler(websocket, 'maica_agent_no_inst', 'MFocus got no instruction, falling back and proceeding', '404', traceray_id=self.traceray_id)
                                info_agent_grabbed = ''

                        # Everything should be grabbed by now

                        overall_info_system += info_agent_grabbed

                        if session_type == 1:
                            agent_insertion = await self.wrap_mod_system(chat_session_num=self.settings.temp.chat_session, known_info=overall_info_system, strict_conv=self.settings.temp.strict_conv)
                            if not agent_insertion[0]:
                                error = MaicaDbError('Chat session modding failed', '502')
                                try:
                                    error.message += f": {str(agent_insertion[1])}"
                                except Exception:
                                    error.message += ", no reason provided"
                                await common_context_handler(websocket, "maica_db_failure", traceray_id=self.traceray_id, error=error)

                        elif session_type == 0:
                            messages = [{'role': 'system', 'content': (await self.mod_once_system(chat_session_num=self.settings.temp.chat_session, known_info=overall_info_system, strict_conv=self.settings.temp.strict_conv))[2]}, {'role': 'user', 'content': query_in}]

                    else:
                        self.settings.temp.update(self.fsc.rsc, bypass_mf=False)
                        if session_type == 1:
                            agent_insertion = await self.wrap_mod_system(chat_session_num=self.settings.temp.chat_session, known_info=None, strict_conv=self.settings.temp.strict_conv)
                            if not agent_insertion[0]:
                                error = MaicaDbError('Chat session modding failed', '502')
                                try:
                                    error.message += f": {str(agent_insertion[1])}"
                                except Exception:
                                    error.message += ", no reason provided"
                                await common_context_handler(websocket, "maica_db_failure", traceray_id=self.traceray_id, error=error)

                        elif session_type == 0:
                            messages = [{'role': 'system', 'content': global_init_system('[player]', self.settings.basic.target_lang)}, {'role': 'user', 'content': query_in}]

                    if session_type == 1:
                        try:
                            check_result = await self.check_create_chat_session(self.settings.temp.chat_session)
                            if check_result[0]:
                                rw_result = await self.rw_chat_session(self.settings.temp.chat_session, 'r', messages0)
                                if rw_result[0]:
                                    messages = f'[{rw_result[3]}]'
                                else:
                                    raise Exception('Chat session reading failed')
                            else:
                                raise Exception('Chat session creation failed')
                        except Exception as e:
                            error = MaicaDbError(str(e), '500')
                            await common_context_handler(websocket, 'maica_db_failure', traceray_id=self.traceray_id, error=error)
                        try:
                            messages = json.loads(messages)
                        except Exception as e:
                            error = MaicaDbError(f'Chat session not JSON: {str(e)}', '500')
                            await common_context_handler(websocket, 'maica_db_corruption', traceray_id=self.traceray_id, error=error)

            # Construction part done, communication part started

            completion_args = {
                "model": self.settings.basic.model_actual,
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
            await common_context_handler(None, 'maica_chat_query_ready', f'Query constrcted and ready to go, last input is:\n{query_in}\nSending query...', '206', color=colorama.Fore.LIGHTCYAN_EX)

            if not self.settings.temp.bypass_gen or not replace_generation: # They should present together

                # Generation here

                stream_resp = await self.mcore_conn.make_completion(**completion_args)

                if completion_args['stream']:
                    reply_appended = ''

                    async for chunk in stream_resp:
                        token = chunk.choices[0].delta.content
                        if token:
                            await asyncio.sleep(0)
                            await common_context_handler(websocket, 'maica_core_streaming_continue', token, '100')
                            reply_appended += token
                    await common_context_handler(info='\n', type='plain')
                    await common_context_handler(websocket, 'maica_core_streaming_done', f'Streaming finished with seed {completion_args['seed']} for {self.settings.verification.username}', '1000', traceray_id=self.traceray_id)
                else:
                    reply_appended = stream_resp.choices[0].message.content
                    await common_context_handler(websocket, 'maica_core_nostream_reply', reply_appended, '200', type='carriage')
                    await common_context_handler(None, 'maica_core_nostream_done', f'Reply sent with seed {completion_args['seed']} for {self.settings.verification.username}', '1000', traceray_id=self.traceray_id)

            else:

                # We just pretend it was generated

                reply_appended = replace_generation
                if completion_args['stream']:
                    await common_context_handler(websocket, 'maica_core_streaming_continue', reply_appended, '100'); await common_context_handler(info='\n', type='plain')
                    await common_context_handler(websocket, 'maica_core_streaming_done', f'Streaming finished with cache for {self.settings.verification.username}', '1000', traceray_id=self.traceray_id)
                else:
                    await common_context_handler(websocket, 'maica_core_nostream_reply', reply_appended, '200', type='carriage')
                    await common_context_handler(None, 'maica_core_nostream_done', f'Reply sent with cache for {self.settings.verification.username}', '1000', traceray_id=self.traceray_id)

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
                await self.store_hashed_cache(ms_cache_identity, reply_appended)

            trigger_succ, trigger_sce = trigger_resp
            if trigger_succ:
                await common_context_handler(websocket, 'maica_trigger_done', trigger_sce, '1010')
            else:
                if trigger_sce:
                    error = MaicaResponseError('MTrigger failed to response', '502')
                    await common_context_handler(websocket, 'maica_trigger_failed', traceray_id=self.traceray_id, error=error)
                else:
                    await common_context_handler(None, 'maica_trigger_empty', 'No trigger passed in', '200')

            # Store history here

            if session_type == 1:
                stored = await self.rw_chat_session(self.settings.temp.chat_session, 'w', f'{messages0},{reply_appended_insertion}')
                if stored[0]:
                    success = True
                    match stored[4]:
                        case 1:
                            await common_context_handler(websocket, 'maica_history_sliced', f"Session {self.settings.temp.chat_session} of {self.settings.verification.username} exceeded {self.settings.basic.max_length} characters and sliced", '204')
                        case 2:
                            await common_context_handler(websocket, 'maica_history_slice_hint', f"Session {self.settings.temp.chat_session} of {self.settings.verification.username} exceeded {self.settings.basic.max_length * (2/3)} characters, will slice at {self.settings.basic.max_length}", '200', no_print=True)
                else:
                    error = MaicaDbError(f'Chat session writing failed: {str(stored[1])}', '502')
                    await common_context_handler(websocket, 'maica_history_write_failure', traceray_id=self.traceray_id, error=error)
                await common_context_handler(websocket, 'maica_chat_loop_finished', f'Finished chat loop from {self.settings.verification.username}', '200', traceray_id=self.traceray_id)
            else:
                success = True
                await common_context_handler(websocket, 'maica_chat_loop_finished', f'Finished non-recording chat loop from {self.settings.verification.username}', '200', traceray_id=self.traceray_id)

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
            await common_context_handler(info=f"Locking session for {permit['id']} named {permit['username']}")

            return_status = await thread_instance.function_switch()
            # If function switch returned, something must have went wrong
            if return_status:
                raise Exception(return_status)

        except Exception as excepted:
            match str(excepted):
                case '0':
                    await common_context_handler(info=f'Function quitted. Likely connection loss.', color=colorama.Fore.LIGHTBLUE_EX)
                case '1':
                    await common_context_handler(info=f'Function broke by a warning.', type='warn')
                case '2':
                    await common_context_handler(info=f'Function broke by a critical', type='error')
                case '3':
                    await common_context_handler(info=f'Function broke by an unknown exception', type='error')

        finally:
            try:
                online_dict.pop(permit[2])
                await common_context_handler(info=f"Lock released for {permit[2]} as {permit[3]}")
            except Exception:
                await common_context_handler(info=f"No lock for this connection")
            await websocket.close()
            await websocket.wait_closed()
            await common_context_handler(info=f"Closing connection gracefully")



async def prepare_thread(**kwargs):
    auth_pool = default(kwargs.get('auth_pool'), ConnUtils.auth_pool())
    maica_pool = default(kwargs.get('maica_pool'), ConnUtils.maica_pool())
    mcore_conn: AiConnCoroutine = default(kwargs.get('mcore_conn'), ConnUtils.mcore_conn())
    mfocus_conn: AiConnCoroutine = default(kwargs.get('mfocus_conn'), ConnUtils.mfocus_conn())

    try:
        await common_context_handler(info=f"Main model is {mcore_conn.model_actual}, MFocus model is {mfocus_conn.model_actual}", color=colorama.Fore.MAGENTA)
    except Exception:
        await common_context_handler(info=f"Model deployment cannot be reached -- running in minimal testing mode", color=colorama.Fore.MAGENTA)
    
    server = await websockets.serve(functools.partial(main_logic, **kwargs), '0.0.0.0', 5000)
    await server.wait_closed()

def run_ws(**kwargs):
    global online_dict
    online_dict = {}

    asyncio.run(common_context_handler(info='Starting WS server!' if load_env('DEV_STATUS') == 'serving' else 'Starting WS server in development mode!', color=colorama.Fore.LIGHTMAGENTA_EX))
    asyncio.run(prepare_thread(**kwargs))

    asyncio.run(common_context_handler(info='Stopping WS server!', color=colorama.Fore.MAGENTA))

if __name__ == '__main__':

    # Pool wrappings init here

    auth_pool, maica_pool, mcore_conn, mfocus_conn = ConnUtils.auth_pool(), ConnUtils.maica_pool(), ConnUtils.mcore_conn(), ConnUtils.mfocus_conn()

    run_ws(auth_pool=auth_pool, maica_pool=maica_pool, mcore_conn=mcore_conn, mfocus_conn=mfocus_conn)