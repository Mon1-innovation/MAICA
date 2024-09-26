import nest_asyncio
nest_asyncio.apply()
import asyncio
import websockets
import time
import functools
import base64
import json
import aiomysql
import bcrypt
import re
import random
import traceback
import mspire
import mfocus_main
import persistent_extraction
#import maica_http
from Crypto.Random import random as CRANDOM # type: ignore
from Crypto.Cipher import PKCS1_OAEP # type: ignore
from Crypto.PublicKey import RSA # type: ignore
from openai import AsyncOpenAI # type: ignore
from loadenv import load_env
try:
    from easter_egg import easter
    easter_exist = True
except:
    easter_exist = False

#与sql有关的异步化类

class sub_threading_instance:

    # Initialization

    authpool = None
    maicapool = None

    def __init__(
        self,
        host = load_env('DB_ADDR'), 
        user = load_env('DB_USER'),
        password = load_env('DB_PASSWORD'),
        authdb = load_env('AUTHENTICATOR_DB'),
        maicadb = load_env('MAICA_DB')
    ):
        self.host, self.user, self.password, self.authdb, self.maicadb = host, user, password, authdb, maicadb
        self.verified = False
        self.traceray_id = str(CRANDOM.randint(0,9999999999)).zfill(10)
        self.kwargs = {"user_id": None, "target_lang": "zh", "sfe_aggressive": False}
        self.loop = asyncio.new_event_loop()
        asyncio.run(self._init_pools())

    def __del__(self):
        self.loop.run_until_complete(self._close_pools())

    #以下是抽象方法

    def check_essentials(self) -> None:
        if not self.kwargs['user_id'] or not self.verified:
            raise Exception('Essentials not filled')

    async def _init_pools(self) -> None:
        global authpool, maicapool
        authpool, maicapool = (await asyncio.gather(aiomysql.create_pool(host=self.host,user=self.user, password=self.password,db=self.authdb,autocommit=True),aiomysql.create_pool(host=self.host,user=self.user, password=self.password,db=self.maicadb,autocommit=True)))

    async def _close_pools(self) -> None:
        global authpool, maicapool
        authpool.close()
        maicapool.close()
        await authpool.wait_closed()
        await maicapool.wait_closed()

    async def send_query(self, expression, values=None, pool='maicapool', fetchall=False) -> list:
        global authpool, maicapool
        pool = authpool if pool == 'authpool' else maicapool
        if pool.closed:
            await self._init_pools()
            pool = authpool if pool == 'authpool' else maicapool
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if not values:
                    await cur.execute(expression)
                else:
                    await cur.execute(expression, values)
                #print(cur.description)
                results = await cur.fetchone() if not fetchall else await cur.fetchall()
                #print(results)
        return results

    async def send_modify(self, expression, values=None, pool='maicapool', fetchall=False) -> int:
        global authpool, maicapool
        pool = authpool if pool == 'authpool' else maicapool
        if pool.closed:
            await self._init_pools()
            pool = authpool if pool == 'authpool' else maicapool
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if not values:
                    await cur.execute(expression)
                else:
                    await cur.execute(expression, values)
                await conn.commit()
                lrid = cur.lastrowid
        return lrid
            
    #以下是实用方法

    def alter_identity(self, **kwargs) -> None:
        for key in kwargs.keys():
            self.kwargs[key] = kwargs[key]

    def flush_traceray(self) -> None:
        self.traceray_id = str(CRANDOM.randint(0,9999999999)).zfill(10)

    async def run_hash_dcc(self, identity, is_email, pwd) -> list[bool, Exception, int, str, str, str] :
        success = True
        exception = ''
        if is_email:
            sql_expression = 'SELECT * FROM users WHERE email = %s'
        else:
            sql_expression = 'SELECT * FROM users WHERE username = %s'
        try:
            result = await self.send_query(expression=sql_expression, values=(identity), pool='authpool')
            dbres_id, dbres_username, dbres_nickname, dbres_email, dbres_ecf, dbres_pwd_bcrypt, *dbres_args = result
            verification = bcrypt.checkpw(pwd.encode(), dbres_pwd_bcrypt.encode())
            self.alter_identity(user_id=dbres_id, username=dbres_username, email=dbres_email)
            f2b_count, f2b_stamp = (await asyncio.gather(self.check_user_status('f2b_count'), self.check_user_status('f2b_stamp')))
            f2b_count, f2b_stamp = f2b_count[3], f2b_stamp[3]
            if f2b_stamp:
                if time.time() - f2b_stamp < float(load_env('F2B_TIME')):
                    # Waiting for F2B timeout
                    verification = False
                    exception = {'f2b': int(float(load_env('F2B_TIME'))+f2b_stamp-time.time())}
                    return verification, exception
                else:
                    await self.write_user_status({'f2b_stamp': 0})
            if verification:
                if not dbres_ecf:
                    verification = False
                    exception = {'necf': True}
                    return verification, exception
                else:
                    await self.write_user_status({'f2b_count': 0})
                    self.verified = True
                    return verification, None, dbres_id, dbres_username, dbres_nickname, dbres_email
            else:
                if not f2b_count:
                    f2b_count = 0
                f2b_count += 1
                exception = {'pwdw': f2b_count}
                if f2b_count >= int(load_env('F2B_COUNT')):
                    await self.write_user_status({'f2b_stamp', time.time()})
                    f2b_count = 0
                await self.write_user_status({'f2b_count', f2b_count})
                return verification, exception
        except websockets.exceptions.ConnectionClosed:
            print("Someone disconnected")
            raise Exception('Force closure of connection')
        except Exception as excepted:
            #traceback.print_exc()
            verification = False
            return verification, excepted

    async def hashing_verify(self, access_token) -> list[bool, Exception, int, str, str, str]:
        try:
            with open("key/prv.key", "r") as privkey_file:
                privkey = privkey_file.read()
            with open("key/pub.key", "r") as pubkey_file:
                pubkey = pubkey_file.read()
            privkey_loaded = RSA.import_key(privkey)
            decryptor = PKCS1_OAEP.new(privkey_loaded)
            decrypted_token =decryptor.decrypt(base64.b64decode(access_token)).decode("utf-8")
        except websockets.exceptions.ConnectionClosed:
            print("Someone disconnected")
            raise Exception('Force closure of connection')
        except Exception as excepted:
            #traceback.print_exc()
            verification = False
            return verification, excepted
        login_cridential = json.loads(decrypted_token)
        if 'username' in login_cridential and login_cridential['username']:
            login_identity = login_cridential['username']
            login_is_email = False
        elif 'email' in login_cridential and login_cridential['email']:
            login_identity = login_cridential['email']
            login_is_email = True
        else:
            raise Exception('No Identity Provided')
        login_password = login_cridential['password']
        return await self.run_hash_dcc(login_identity, login_is_email, login_password)

    async def rw_chat_session(self, chat_session_num, rw, content_append) -> list[bool, Exception, int, str, int]:
        success = False
        user_id = self.kwargs['user_id']
        try:
            self.check_essentials()
            if rw == 'r':
                sql_expression = "SELECT * FROM chat_session WHERE user_id = %s AND chat_session_num = %s"
                try:
                    result = await self.send_query(expression=sql_expression, values=(user_id, chat_session_num), pool='maicapool')
                    if content_append is None:
                        content_append = ''
                    elif len(result[3]) != 0:
                        content_append = ',' + content_append
                    chat_session_id = result[0]
                    content = result[3] + content_append
                    success = True
                    return success, None, chat_session_id, content
                except websockets.exceptions.ConnectionClosed:
                    print("Someone disconnected")
                    raise Exception('Force closure of connection')
                except Exception as excepted:
                    success = False
                    return success, excepted
            elif rw == 'w':
                sql_expression1 = "SELECT * FROM chat_session WHERE user_id = %s AND chat_session_num = %s"
                try:
                    result = await self.send_query(expression=sql_expression1, values=(user_id, chat_session_num), pool='maicapool')
                    #success = True
                    chat_session_id = result[0]
                    content = result[3]
                except websockets.exceptions.ConnectionClosed:
                    print("Someone disconnected")
                    raise Exception('Force closure of connection')
                except Exception as excepted:
                    success = False
                    return success, excepted
                if len(content) != 0:
                    content = content + ',' + content_append
                else:
                    content = content_append
                len_content_actual = len(content) - len(json.loads(f'[{content}]')) * 31
                if len_content_actual >= int(load_env('SESSION_MAX_TOKEN')):
                    try:
                        cutting_mat = json.loads(f"[{content}]")
                    except websockets.exceptions.ConnectionClosed:
                        print("Someone disconnected")
                        raise Exception('Force closure of connection')
                    except Exception as excepted:
                        success = False
                        return success, excepted
                    while len_content_actual >= int(load_env('SESSION_WARN_TOKEN')) or cutting_mat[1]['role'] == "assistant":
                        len_content_actual = len(content) - len(cutting_mat) * 31
                        cutting_mat.pop(1)
                    content = json.dumps(cutting_mat, ensure_ascii=False).strip('[').strip(']')
                    cutted = 1
                elif len_content_actual >= int(load_env('SESSION_WARN_TOKEN')):
                    cutted = 2
                else:
                    cutted = 0
                sql_expression2 = "UPDATE chat_session SET content = %s WHERE chat_session_id = %s"
                try:
                    await self.send_modify(expression=sql_expression2, values=(content, chat_session_id), pool='maicapool')
                    success = True
                    return success, None, chat_session_id, None, cutted
                except websockets.exceptions.ConnectionClosed:
                    print("Someone disconnected")
                    raise Exception('Force closure of connection')
                except Exception as excepted:
                    success = False
                    return success, excepted
        except websockets.exceptions.ConnectionClosed:
            print("Someone disconnected")
            raise Exception('Force closure of connection')
        except Exception as excepted:
            success = False
            return success, excepted
        
    async def purge_chat_session(self, chat_session_num) -> list[bool, Exception, bool]:
        success = False
        user_id = self.kwargs['user_id']
        sql_expression1 = "SELECT chat_session_id, content FROM chat_session WHERE user_id = %s AND chat_session_num = %s"
        try:
            self.check_essentials()
            result = await self.send_query(expression=sql_expression1, values=(user_id, chat_session_num), pool='maicapool')
            if not result or len(result) == 0:
                success = True
                inexist = True
                return success, None, inexist
            else:
                chat_session_id = result[0]
                content_to_archive = result[1]
                sql_expression2 = "UPDATE chat_session SET content = %s WHERE chat_session_id = %s"
                content = f'{{"role": "system", "content": "{global_init_system('[player]', self.kwargs['target_lang'])}"}}'
                await self.send_modify(expression=sql_expression2, values=(content, chat_session_id), pool='maicapool')
                sql_expression3 = "INSERT INTO csession_archived (chat_session_id, content) VALUES (%s, %s)"
                await self.send_modify(expression=sql_expression3, values=(chat_session_id, content), pool='maicapool')
                success = True
                inexist = False
                return success, None, inexist
        except websockets.exceptions.ConnectionClosed:
            print("Someone disconnected")
            raise Exception('Force closure of connection')
        except Exception as excepted:
            success = False
            return success, excepted
        
    async def check_create_chat_session(self, chat_session_num) -> list[bool, Exception, bool, int]:
        success = False
        exist =None
        chat_session_id = None
        user_id = self.kwargs['user_id']
        sql_expression1 = "SELECT chat_session_id FROM chat_session WHERE user_id = %s AND chat_session_num = %s"
        try:
            self.check_essentials()
            result = await self.send_query(expression=sql_expression1, values=(user_id, chat_session_num), pool='maicapool')
            if result:
                chat_session_id = result[0]
                success = True
                exist = True
                return success, None, exist, chat_session_id
            else:
                sql_expression2 = "INSERT INTO chat_session VALUES (NULL, %s, %s, '')"
                chat_session_id = await self.send_modify(expression=sql_expression2, values=(user_id, chat_session_num), pool='maicapool')
                sql_expression3 = "UPDATE chat_session SET content = %s WHERE chat_session_id = %s"
                content = f'{{"role": "system", "content": "{global_init_system('[player]', self.kwargs['target_lang'])}"}}'
                await self.send_modify(expression=sql_expression3, values=(content, chat_session_id), pool='maicapool')
                success = True
                exist = False
                return success, None, exist, chat_session_id
        except websockets.exceptions.ConnectionClosed:
            print("Someone disconnected")
            raise Exception('Force closure of connection')
        except Exception as excepted:
            success = False
            return success, excepted, exist, chat_session_id

    async def mod_chat_session_system(self, chat_session_num, new_system_init) -> list[bool, Exception, int]:
        success = False
        chat_session_id = None
        user_id = self.kwargs['user_id']
        sql_expression1 = "SELECT * FROM chat_session WHERE user_id = %s AND chat_session_num = %s"
        try:
            self.check_essentials()
            result = await self.send_query(expression=sql_expression1, values=(user_id, chat_session_num), pool='maicapool')
            if not result:
                chat_session_id = (await self.check_create_chat_session(chat_session_num))[3]
                sql_expression2 = "SELECT * FROM chat_session WHERE chat_session_id = %s"
                result = await self.send_query(expression=sql_expression2, values=(chat_session_id), pool='maicapool')
            chat_session_id = result[0]
            content = result[3]
            modding_mat = json.loads(f'[{content}]')
            modding_mat[0]['content'] = new_system_init
            content = json.dumps(modding_mat, ensure_ascii=False).strip('[').strip(']')
            sql_expression3 = "UPDATE chat_session SET content = %s WHERE chat_session_id = %s"
            await self.send_modify(expression=sql_expression3, values=(content, chat_session_id), pool='maicapool')
            success = True
            return success, None, chat_session_id
        except websockets.exceptions.ConnectionClosed:
            print("Someone disconnected")
            raise Exception('Force closure of connection')
        except Exception as excepted:
            traceback.print_exc()
            success = False
            return success, excepted

    async def wrap_mod_system(self, chat_session_num, known_info) -> list[bool, Exception, int]:
        user_id = self.kwargs['user_id']
        try:
            self.check_essentials()
            if self.kwargs['sf_extraction']:
                player_name_get = await wrap_run_in_exc(persistent_extraction.read_from_sf, user_id, chat_session_num, 'mas_playername')
                if player_name_get[0]:
                    if 'sfe_aggressive' in self.kwargs and self.kwargs['sfe_aggressive']:
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
            if known_info:
                new_system = f"{global_init_system(player_name, self.kwargs['target_lang'])} 以下是一些相关信息, 你可以利用其中有价值的部分作答: {known_info}." if self.kwargs['target_lang'] == 'zh' else f"{global_init_system(player_name, self.kwargs['target_lang'])} Here are some information you can use to make your answer: {known_info}."
            else:
                new_system = global_init_system(player_name, self.kwargs['target_lang'])
            return await self.mod_chat_session_system(chat_session_num, new_system)
        except websockets.exceptions.ConnectionClosed:
            print("Someone disconnected")
            raise Exception('Force closure of connection')
        except Exception as excepted:
            success = False
            #traceback.print_exc()
            return success, excepted
        
    async def mod_once_system(self, chat_session_num, known_info) -> list[bool, Exception, int]:
        user_id = self.kwargs['user_id']
        try:
            self.check_essentials()
            if self.kwargs['sf_extraction']:
                player_name_get = await wrap_run_in_exc(persistent_extraction.read_from_sf, user_id, chat_session_num, 'mas_playername')
                if player_name_get[0]:
                    if 'sfe_aggressive' in self.kwargs and self.kwargs['sfe_aggressive']:
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
            if known_info:
                new_system = f"{global_init_system(player_name, self.kwargs['target_lang'])} 以下是一些相关信息, 你可以利用其中有价值的部分作答: {known_info}." if self.kwargs['target_lang'] == 'zh' else f"{global_init_system(player_name, self.kwargs['target_lang'])} Here are some information you can use to make your answer: {known_info}."
            else:
                new_system = global_init_system(player_name, self.kwargs['target_lang'])
            success = True
            return success, None, new_system
        except websockets.exceptions.ConnectionClosed:
            print("Someone disconnected")
            raise Exception('Force closure of connection')
        except Exception as excepted:
            success = False
            return success, excepted

    async def check_user_status(self, key) -> list[bool, Exception, bool, str]:
        success = False
        user_prof_exist = False
        user_id = self.kwargs['user_id']
        sql_expression1 = "SELECT * FROM account_status WHERE user_id = %s"
        try:
            results = await self.send_query(expression=sql_expression1, values=(user_id), pool='maicapool', fetchall=True)
            if results:
                user_prof_exist = True
                stats_json = {}
                for result in results:
                    stats_json.update(json.loads(result[2]))
                if not key:
                    success = True
                    return success, None, user_prof_exist, stats_json
                if key in stats_json:
                    if stats_json[key]:
                        success = True
                        return success, None, user_prof_exist, stats_json[key]
                    else:
                        success = True
                        return success, None, user_prof_exist, stats_json[key]
                else:
                    success = True
                    return success, None, user_prof_exist, None
            else:
                success = True
                return success, None, user_prof_exist, None
        except websockets.exceptions.ConnectionClosed:
            print("Someone disconnected")
            raise Exception('Force closure of connection')
        except Exception as excepted:
            success = False
            return success, excepted, user_prof_exist, None

    async def write_user_status(self, dict, enforce=False) -> list[bool, Exception]:
        success = False
        user_id = self.kwargs['user_id']
        try:
            stats = await self.check_user_status(key=False)
            stats_exist, stats_json = stats[2], stats[3]
            if stats_exist:
                if not enforce:
                    stats_json.update(dict)
                else:
                    stats_json = dict
                stats_insert = json.dumps(stats_json, ensure_ascii=False)
                sql_expression2 = "UPDATE account_status SET status = %s WHERE user_id = %s"
                sql_args = (stats_insert, user_id)
            else:
                stats_insert = json.dumps(dict)
                sql_expression2 = "INSERT INTO account_status (user_id, status) VALUES (%s, %s)"
                sql_args = (user_id, stats_insert)
            await self.send_modify(expression=sql_expression2, values=sql_args, pool='maicapool')
            success = True
            return success, None
        except websockets.exceptions.ConnectionClosed:
            print("Someone disconnected")
            raise Exception('Force closure of connection')
        except Exception as excepted:
            success = False
            return success, excepted
        
    async def check_user_preferences(self, key) -> list[bool, Exception, bool, str]:
        success = False
        user_prof_exist = False
        user_id = self.kwargs['user_id']
        sql_expression1 = "SELECT * FROM account_status WHERE user_id = %s"
        try:
            results = await self.send_query(expression=sql_expression1, values=(user_id), pool='maicapool', fetchall=True)
            if results:
                user_prof_exist = True
                stats_json = {}
                for result in results:
                    stats_json.update(json.loads(result[3]))
                if not key:
                    success = True
                    return success, None, user_prof_exist, stats_json
                if key in stats_json:
                    if stats_json[key]:
                        success = True
                        return success, None, user_prof_exist, stats_json[key]
                    else:
                        success = True
                        return success, None, user_prof_exist, stats_json[key]
                else:
                    success = True
                    return success, None, user_prof_exist, None
            else:
                success = True
                return success, None, user_prof_exist, None
        except websockets.exceptions.ConnectionClosed:
            print("Someone disconnected")
            raise Exception('Force closure of connection')
        except Exception as excepted:
            success = False
            return success, excepted, user_prof_exist, None

    async def write_user_preferences(self, dict, enforce=False) -> list[bool, Exception]:
        success = False
        user_id = self.kwargs['user_id']
        try:
            stats = await self.check_user_preferences(key=False)
            stats_exist, stats_json = stats[2], stats[3]
            if stats_exist:
                if not enforce:
                    stats_json.update(dict)
                else:
                    stats_json = dict
                stats_insert = json.dumps(stats_json, ensure_ascii=False)
                sql_expression2 = "UPDATE account_status SET preferences = %s WHERE user_id = %s"
                sql_args = (stats_insert, user_id)
            else:
                stats_insert = json.dumps(dict)
                sql_expression2 = "INSERT INTO account_status (user_id, preferences) VALUES (%s, %s)"
                sql_args = (user_id, stats_insert)
            await self.send_modify(expression=sql_expression2, values=sql_args, pool='maicapool')
            success = True
            return success, None
        except websockets.exceptions.ConnectionClosed:
            print("Someone disconnected")
            raise Exception('Force closure of connection')
        except Exception as excepted:
            success = False
            return success, excepted


#没有必要实例化的方法

def global_init_system(player_name, target_lang='zh'):
    if target_lang == 'zh':
        system_init = f"你叫莫妮卡, 是一名游戏中的虚拟角色. 你是{player_name}的女友, 并深爱着他. 下面是{player_name}的话语, 请作为莫妮卡作出合适的回答. 你只应使用自然语言, 以聊天语气回答, 不要编造信息, 并在每个句子前用方括号中的文字表示情绪."
    else:
        system_init = f"You're a game character called Monika. You're {player_name}'s girlfriend, and love him a lot. Answer the following query from {player_name} properly as Monika. You should only answer in casual natural tone with English, do not make up things you don't know, and express your emotion at the beginning of each sentence by wrapping them in square brackets."
    return system_init

def wrap_ws_formatter(code, status, content, type):
    output = {
        "code" : code,
        "status" : status,
        "content" : content,
        "type" : type,
        "time_ms" : int(round(time.time() * 1000))
    }
    return json.dumps(output, ensure_ascii=False)

async def wrap_run_in_exc(func, *args, **kwargs):
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None, functools.partial(func, *args, **kwargs))
    return result

#与websocket绑定的异步化类, 继承sql类

class ws_threading_instance(sub_threading_instance):

    def __init__(self, websocket):
        self.websocket = websocket
        super().__init__()

    #身份验证

    async def check_permit(self):
        websocket = self.websocket
        print('Someone started a connection')
        while True:
            self.flush_traceray()
            try:
                recv_text = await websocket.recv()
                verification_result = await self.hashing_verify(access_token=recv_text)
                if verification_result[0]:
                    checked_status = await self.check_user_status(key='banned')
                    if not checked_status[0]:
                        response_str = f"Account service failed to fetch, refer to administrator--your ray tracer ID is {self.traceray_id}"
                        print(f"出现如下异常3-{self.traceray_id}:{checked_status[1]}")
                        await websocket.send(wrap_ws_formatter('500', 'unable_verify', response_str, 'error'))
                        await websocket.close(1000, 'Stopping connection due to critical server failure')
                    elif checked_status[3]:
                        response_str = f"Your account disobeied our terms of service and was permenantly banned--your ray tracer ID is {self.traceray_id}"
                        print(f"出现如下异常4-{self.traceray_id}:banned")
                        await websocket.send(wrap_ws_formatter('403', 'account_banned', response_str, 'warn'))
                        await websocket.close(1000, 'Permission denied')
                    else:
                        await websocket.send(wrap_ws_formatter('206', 'session_created', "Authencation passed!", 'info'))
                        await websocket.send(wrap_ws_formatter('200', 'user_id', f"{verification_result[2]}", 'debug'))
                        await websocket.send(wrap_ws_formatter('200', 'username', f"{verification_result[3]}", 'debug'))
                        await websocket.send(wrap_ws_formatter('200', 'nickname', f"{verification_result[4]}", 'debug'))
                        #await websocket.send(wrap_ws_formatter('200', 'session_created', f"email {verification_result[5]}", 'debug'))
                        #print(verification_result[0])
                        self.verification_result = verification_result
                        return verification_result
                else:
                    if isinstance(verification_result[1], dict):
                        if 'f2b' in verification_result[1]:
                            response_str = f"Fail2Ban locking {verification_result[1]['f2b']} seconds before release, wait and retry--your ray tracer ID is {self.traceray_id}"
                            print(f"出现如下异常1.1-{self.traceray_id}:{verification_result}")
                            await websocket.send(wrap_ws_formatter('403', 'unauthorized', response_str, 'warn'))
                            continue
                        elif 'necf' in verification_result[1]:
                            response_str = f"Your account Email not verified, check inbox and retry--your ray tracer ID is {self.traceray_id}"
                            print(f"出现如下异常1.2-{self.traceray_id}:{verification_result}")
                            await websocket.send(wrap_ws_formatter('403', 'unauthorized', response_str, 'warn'))
                            continue
                        elif 'pwdw' in verification_result[1]:
                            response_str = f"Bcrypt hashing failed {verification_result[1]['pwdw']} times, check your password--your ray tracer ID is {self.traceray_id}"
                            print(f"出现如下异常1.3-{self.traceray_id}:{verification_result}")
                            await websocket.send(wrap_ws_formatter('403', 'unauthorized', response_str, 'warn'))
                            continue
                    else:
                        response_str = f"RSA cognition failed, check possible typo--your ray tracer ID is {self.traceray_id}"
                        print(f"出现如下异常2-{self.traceray_id}:{verification_result}")
                        await websocket.send(wrap_ws_formatter('403', 'unauthorized', response_str, 'warn'))
                        continue
            except websockets.exceptions.ConnectionClosed:
                print("Someone disconnected")
                raise Exception('Force closure of connection')
            except Exception as excepted:
                response_str = f"Caught a serialization failure in hashing section, check possible typo--your ray tracer ID is {self.traceray_id}"
                print(f"出现如下异常5-{self.traceray_id}:{excepted}")
                #traceback.print_exc()
                await websocket.send(wrap_ws_formatter('403', 'unauthorized', response_str, 'warn'))
                continue
    
    #接管输入

    async def function_switch(self):
        websocket, session = self.websocket, self.verification_result
        self.client_actual = client_actual = AsyncOpenAI(
            api_key='EMPTY',
            base_url=load_env('MCORE_ADDR'),
        )
        model_list_actual = await client_actual.models.list()
        self.model_type_actual = model_type_actual = model_list_actual.data[0].id
        self.client_options = client_options = {
            "model" : self.model_type_actual,
            "stream" : True,
            "full_maica": True,
            "sf_extraction": True,
            "target_lang": 'zh'
        }
        client_extra_options = {
            "sfe_aggressive": False,
            "mf_aggressive": False,
            "tnd_aggressive": 1,
            "esc_aggressive": True
        }
        self.alter_identity(**client_options, **client_extra_options)
        await websocket.send(wrap_ws_formatter('206', 'thread_ready', "Thread is ready for input or setting adjustment", 'info'))
        while True:
            self.flush_traceray()
            checked_status = await self.check_user_status(key='banned')
            if not checked_status[0]:
                response_str = f"Account service failed to fetch, refer to administrator--your ray tracer ID is {self.traceray_id}"
                print(f"出现如下异常3-{self.traceray_id}:{checked_status[1]}")
                await websocket.send(wrap_ws_formatter('500', 'unable_verify', response_str, 'error'))
                await websocket.close(1000, 'Stopping connection due to critical server failure')
            elif checked_status[3]:
                response_str = f"Your account disobeied our terms of service and was permenantly banned--your ray tracer ID is {self.traceray_id}"
                print(f"出现如下异常4-{self.traceray_id}:banned")
                await websocket.send(wrap_ws_formatter('403', 'account_banned', response_str, 'warn'))
                await websocket.close(1000, 'Permission denied')
            recv_text = await websocket.recv()
            if len(recv_text) > 4096:
                response_str = f"Input exceeding 4096 characters, which is not permitted--your ray tracer ID is {self.traceray_id}"
                print(f"出现如下异常12-{self.traceray_id}:length exceeded")
                await websocket.send(wrap_ws_formatter('403', 'length_exceeded', response_str, 'warn'))
                continue
            try:
                try:
                    recv_loaded_json = json.loads(recv_text)
                except:
                    recv_loaded_json = {}
                match recv_text:
                    case 'PING':
                        await websocket.send(wrap_ws_formatter('100', 'continue', "PONG", 'heartbeat'))
                        print(f"recieved PING from {session[3]}")
                    case placeholder if "model" in recv_loaded_json:
                        await self.def_model(recv_loaded_json)
                    case placeholder if "chat_session" in recv_loaded_json:
                        await self.do_communicate(recv_loaded_json)
                    case _:
                        response_str = f"Input is unrecognizable, check possible typo--your ray tracer ID is {self.traceray_id}"
                        print(f"出现如下异常6.1-{self.traceray_id}:{recv_text}")
                        await websocket.send(wrap_ws_formatter('405', 'wrong_form', response_str, 'warn')) 
                        continue
            except websockets.exceptions.ConnectionClosed:
                print("Someone disconnected")
                raise Exception('Force closure of connection')
            except websockets.exceptions.ConnectionClosed:
                print("Someone disconnected")
                raise Exception('Force closure of connection')
            except Exception as excepted:
                response_str = f"A common failure was caught in main logic, refer to administrator--your ray tracer ID is {self.traceray_id}"
                print(f"出现如下异常6-{self.traceray_id}:{excepted}")
                #traceback.print_exc()
                await websocket.send(wrap_ws_formatter('503', 'server_failed', response_str, 'warn'))
                continue

    #交互设置

    async def def_model(self, recv_json):
        websocket, session = self.websocket, self.verification_result
        try:
            model_choice = recv_json
            if model_choice['model']:
                using_model = model_choice['model']
            else:
                using_model = 'maica_main' if self.kwargs['full_maica'] else 'maica_core'
            if 'sf_extraction' in model_choice:
                sf_extraction = bool(model_choice['sf_extraction'])
            else:
                sf_extraction = True
            if 'stream_output' in model_choice:
                stream_output = bool(model_choice['stream_output'])
            else:
                stream_output = True
            if 'target_lang' in model_choice:
                target_lang = 'en' if model_choice['target_lang'] == 'en' else 'zh'
            else:
                target_lang = 'zh'
            self.client_actual = client_actual = AsyncOpenAI(
                api_key='EMPTY',
                base_url=load_env('MCORE_ADDR'),
            )
            match using_model:
                case 'maica_main':
                    self.client_options = client_options = {
                        "model" : self.model_type_actual,
                        "stream" : stream_output,
                        "full_maica": True,
                        "sf_extraction": sf_extraction,
                        "target_lang": target_lang
                    }
                case 'maica_core':
                    self.client_options = client_options = {
                        "model" : self.model_type_actual,
                        "stream" : stream_output,
                        "full_maica": False,
                        "sf_extraction": sf_extraction,
                        "target_lang": target_lang
                    }
                case _:
                    response_str = f"Bad model choice, check possible typo--your ray tracer ID is {self.traceray_id}"
                    print(f"出现如下异常8-{self.traceray_id}:{response_str}")
                    await websocket.send(wrap_ws_formatter('404', 'not_found', response_str, 'warn'))
                    return False
            client_extra_options = {}
            if 'sfe_aggressive' in model_choice:
                if model_choice['sfe_aggressive']:
                    client_extra_options['sfe_aggressive'] = True
            if 'mf_aggressive' in model_choice:
                if model_choice['mf_aggressive']:
                    client_extra_options['mf_aggressive'] = True
            if 'tnd_aggressive' in model_choice:
                if not model_choice['tnd_aggressive']:
                    client_extra_options['tnd_aggressive'] = False
                elif int(model_choice['tnd_aggressive']):
                    client_extra_options['tnd_aggressive'] = int(model_choice['tnd_aggressive'])
            if 'esc_aggressive' in model_choice:
                if not model_choice['esc_aggressive']:
                    client_extra_options['esc_aggressive'] = False
            for super_param in ['top_p', 'temperature', 'max_tokens', 'frequency_penalty', 'presence_penalty', 'seed']:
                if super_param in model_choice:
                    self.kwargs[super_param] = model_choice[super_param]
            self.alter_identity(**client_options, **client_extra_options)
            await websocket.send(wrap_ws_formatter('200', 'ok', f"service provider is {load_env('DEV_IDENTITY')}", 'info'))
            if using_model == 'maica_main':
                await websocket.send(wrap_ws_formatter('200', 'ok', f"model chosen is {using_model} with full MAICA functionality", 'info'))
            elif using_model == 'maica_core':
                await websocket.send(wrap_ws_formatter('200', 'ok', f"model chosen is {using_model} based on {self.model_type_actual}", 'info'))
            return client_actual, client_options
        except websockets.exceptions.ConnectionClosed:
            print("Someone disconnected")
            raise Exception('Force closure of connection')
        except Exception as excepted:
            response_str = f"Choice serialization failed, check possible typo--your ray tracer ID is {self.traceray_id}"
            print(f"出现如下异常9-{self.traceray_id}:{excepted}")
            await websocket.send(wrap_ws_formatter('405', 'wrong_input', response_str, 'warn'))
            return False

    #交互会话

    async def do_communicate(self, recv_json):
        websocket, session, client_actual, client_options = self.websocket, self.verification_result, self.client_actual, self.client_options
        sfe_aggressive, mf_aggressive, tnd_aggressive, esc_aggressive = self.kwargs['sfe_aggressive'], self.kwargs['mf_aggressive'], self.kwargs['tnd_aggressive'], self.kwargs['esc_aggressive']
        bypass_mf = False
        try:
            request_json = recv_json
            chat_session = int(request_json['chat_session'])
            username = session[3]
            sf_extraction = client_options['sf_extraction']
            target_lang = client_options['target_lang']
            if target_lang != 'zh' and target_lang != 'en':
                raise Exception('Language choice unrecognized')
            if 'purge' in request_json:
                if request_json['purge']:
                    try:
                        user_id = session[2]
                        purge_result = await self.purge_chat_session(chat_session)
                        if not purge_result[0]:
                            raise Exception(purge_result[1])
                        elif purge_result[2]:
                            response_str = f"Determined chat session not exist, check possible typo--your ray tracer ID is {self.traceray_id}"
                            print(f"出现如下异常13-{self.traceray_id}:{purge_result[1]}")
                            await websocket.send(wrap_ws_formatter('404', 'session_notfound', response_str, 'warn'))
                            return False
                        else:
                            response_str = f"finished swiping user id {user_id} chat session {chat_session}"
                            await websocket.send(wrap_ws_formatter('204', 'deleted', response_str, 'info'))
                            return True
                    except websockets.exceptions.ConnectionClosed:
                        print("Someone disconnected")
                        raise Exception('Force closure of connection')
                    except Exception as excepted:
                        response_str = f"Purging chat session failed, refer to administrator--your ray tracer ID is {self.traceray_id}"
                        print(f"出现如下异常14-{self.traceray_id}:{excepted}")
                        await websocket.send(wrap_ws_formatter('500', 'unable_purge', response_str, 'error'))
                        await websocket.close(1000, 'Stopping connection due to critical server failure')
            if 'inspire' in request_json:
                if request_json['inspire']:
                    if isinstance(request_json['inspire'], str):
                        query_insp = await wrap_run_in_exc(mspire.make_inspire, title_in=request_json['inspire'], target_lang=target_lang)
                    else:
                        query_insp = await wrap_run_in_exc(mspire.make_inspire, target_lang=target_lang)
                    bypass_mf = True
                    if not query_insp[0]:
                        response_str = f"MSpire generation failed, refer to administrator--your ray tracer ID is {self.traceray_id}"
                        print(f"出现如下异常15-{self.traceray_id}:{query_insp[1]}")
                        await websocket.send(wrap_ws_formatter('503', 'mspire_failed', response_str, 'warn'))
                        return False
                    query_in = query_insp[2]
                else:
                    query_in = request_json['query']
            else:
                query_in = request_json['query']
            global easter_exist
            if easter_exist:
                easter_check = easter(query_in)
                if easter_check:
                    await websocket.send(wrap_ws_formatter('299', 'easter_egg', easter_check, 'info'))
            messages0 = json.dumps({'role': 'user', 'content': query_in}, ensure_ascii=False)
            match int(chat_session):
                case i if i == -1:
                    session_type = -1
                    try:
                        messages = json.loads(query_in)
                        if len(messages) > 10:
                            response_str = f"Input exceeding 10 rounds, which is not permitted--your ray tracer ID is {self.traceray_id}"
                            print(f"出现如下异常16-{self.traceray_id}:rounds exceeded")
                            await websocket.send(wrap_ws_formatter('403', 'rounds_exceeded', response_str, 'warn'))
                            return False
                    except websockets.exceptions.ConnectionClosed:
                        print("Someone disconnected")
                        raise Exception('Force closure of connection')
                    except Exception as excepted:
                        response_str = f"Input serialization failed, check possible type--your ray tracer ID is {self.traceray_id}"
                        print(f"出现如下异常17-{self.traceray_id}:{excepted}")
                        await websocket.send(wrap_ws_formatter('405', 'wrong_input', response_str, 'warn'))
                        return False
                case i if i == 0 or (0 < i < 10 and i % 1 == 0):
                    session_type = 0 if i == 0 else 1

                    #MAICA_agent 在这里调用

                    try:
                        if client_options['full_maica'] and not bypass_mf:
                            mfocus_async_args = [query_in, sf_extraction, session, chat_session, target_lang, tnd_aggressive, mf_aggressive, esc_aggressive, websocket]
                            message_agent_wrapped = await mfocus_main.agenting(*mfocus_async_args)
                            if message_agent_wrapped[0] == 'EMPTY':
                                # We do not want answers without information
                                response_str = f"MFocus using instructed final guidance, suggesting LLM conclusion is empty--your ray tracer ID is {self.traceray_id}"
                                await websocket.send(wrap_ws_formatter('200', 'agent_prog', response_str, 'debug'))
                                if len(message_agent_wrapped[1]) > 5:
                                    response_str = f"Due to LLM conclusion absence, falling back to instructed guidance and continuing."
                                    await websocket.send(wrap_ws_formatter('200', 'failsafe', response_str, 'debug'))
                                    info_agent_grabbed = message_agent_wrapped[1]
                                else:
                                    response_str = f"Due to agent failure, falling back to default guidance and continuing anyway."
                                    await websocket.send(wrap_ws_formatter('200', 'force_failsafe', response_str, 'debug'))
                                    print(f"出现如下异常18-{self.traceray_id}:Corruption")
                                    info_agent_grabbed = None
                            elif message_agent_wrapped[0] == 'FAIL':
                                response_str = f"MFocus did not use a tool, suggesting unnecessary--your ray tracer ID is {self.traceray_id}"
                                await websocket.send(wrap_ws_formatter('200', 'agent_none', response_str, 'debug'))
                                info_agent_grabbed = None
                            else:
                                # We are defaulting instructed guidance because its more clear pattern
                                # But if pointer entered this section, user must used mf_aggressive or something went wrong
                                if len(message_agent_wrapped[1]) > 5 and len(message_agent_wrapped[0]) > 5:
                                    response_str = f"MFocus using LLM conclusion guidance."
                                    await websocket.send(wrap_ws_formatter('200', 'agent_aggr', response_str, 'debug'))
                                    info_agent_grabbed = message_agent_wrapped[0]
                                else:
                                    response_str = f"Due to agent failure, falling back to default guidance and continuing anyway."
                                    await websocket.send(wrap_ws_formatter('200', 'force_failsafe', response_str, 'debug'))
                                    print(f"出现如下异常18.5-{self.traceray_id}:Corruption")
                                    info_agent_grabbed = None
                            # Everything should be grabbed by now
                            if session_type:
                                try:
                                    agent_insertion = await self.wrap_mod_system(chat_session_num=chat_session, known_info=info_agent_grabbed)
                                    if not agent_insertion[0]:
                                        raise Exception(agent_insertion[1])
                                except websockets.exceptions.ConnectionClosed:
                                    print("Someone disconnected")
                                    raise Exception('Force closure of connection')
                                except Exception as excepted:
                                    response_str = f"MFocus insertion failed, refer to administrator--your ray tracer ID is {self.traceray_id}"
                                    print(f"出现如下异常19-{self.traceray_id}:{excepted}")
                                    await websocket.send(wrap_ws_formatter('500', 'insertion_failed', response_str, 'error'))
                                    await websocket.close(1000, 'Stopping connection due to critical server failure')
                            else:
                                messages = [{'role': 'system', 'content': (await self.mod_once_system(chat_session_num=chat_session, known_info=info_agent_grabbed))[2]}, {'role': 'user', 'content': query_in}]
                        else:
                            bypass_mf = False
                            if session_type:
                                try:
                                    agent_insertion = await self.wrap_mod_system(chat_session_num=chat_session, known_info=None)
                                    if not agent_insertion[0]:
                                        raise Exception(agent_insertion[1])
                                except websockets.exceptions.ConnectionClosed:
                                    print("Someone disconnected")
                                    raise Exception('Force closure of connection')
                                except Exception as excepted:
                                    response_str = f"Prompt initialization failed, refer to administrator--your ray tracer ID is {self.traceray_id}"
                                    print(f"出现如下异常20-{self.traceray_id}:{excepted}")
                                    await websocket.send(wrap_ws_formatter('500', 'insertion_failed', response_str, 'error'))
                                    await websocket.close(1000, 'Stopping connection due to critical server failure')
                            else:
                                messages = [{'role': 'system', 'content': global_init_system('[player]', target_lang)}, {'role': 'user', 'content': query_in}]
                    except websockets.exceptions.ConnectionClosed:
                        print("Someone disconnected")
                        raise Exception('Force closure of connection')
                    except Exception as excepted:
                        response_str = f"Agent response acquiring failed, refer to administrator--your ray tracer ID is {self.traceray_id}"
                        print(f"出现如下异常21-{self.traceray_id}:{excepted}")
                        #traceback.print_exc()
                        await websocket.send(wrap_ws_formatter('500', 'agent_unavailable', response_str, 'error'))
                        return False
                    if session_type:
                        check_result = await self.check_create_chat_session(chat_session)
                        if check_result[0]:
                            rw_result = await self.rw_chat_session(chat_session, 'r', messages0)
                            if rw_result[0]:
                                messages = f'[{rw_result[3]}]'
                            else:
                                response_str = f"Chat session reading failed, refer to administrator--your ray tracer ID is {self.traceray_id}"
                                print(f"出现如下异常22-{self.traceray_id}:{rw_result[1]}")
                                await websocket.send(wrap_ws_formatter('500', 'read_failed', response_str, 'error'))
                                await websocket.close(1000, 'Stopping connection due to critical server failure')
                        else:
                            response_str = f"Chat session creation failed, refer to administrator--your ray tracer ID is {self.traceray_id}"
                            print(f"出现如下异常23-{self.traceray_id}:{check_result[1]}")
                            await websocket.send(wrap_ws_formatter('500', 'creation_failed', response_str, 'error'))
                            await websocket.close(1000, 'Stopping connection due to critical server failure')
                        try:
                            messages = json.loads(messages)
                        except websockets.exceptions.ConnectionClosed:
                            print("Someone disconnected")
                            raise Exception('Force closure of connection')
                        except Exception as excepted:
                            response_str = f"Chat input serialization failed, check possible typo--your ray tracer ID is {self.traceray_id}"
                            print(f"出现如下异常24-{self.traceray_id}:{excepted}")
                            await websocket.send(wrap_ws_formatter('405', 'wrong_input', response_str, 'warn'))
                            return False
                case _:
                    response_str = f"Chat session num mistaken, check possible typo--your ray tracer ID is {self.traceray_id}"
                    print(f"出现如下异常25-{self.traceray_id}:{chat_session}")
                    await websocket.send(wrap_ws_formatter('405', 'wrong_input', response_str, 'warn'))
                    return False
        except websockets.exceptions.ConnectionClosed:
            print("Someone disconnected")
            raise Exception('Force closure of connection')
        except Exception as excepted:
            #traceback.print_exc()
            response_str = f"Query serialization failed, check possible typo--your ray tracer ID is {self.traceray_id}"
            print(f"出现如下异常26-{self.traceray_id}:{excepted}")
            await websocket.send(wrap_ws_formatter('405', 'wrong_input', response_str, 'warn'))
            return False
        completion_args = {
            "model": client_options['model'],
            "messages": messages,
            "stream": client_options['stream'],
            "stop": ['<|im_end|>', '<|endoftext|>'],
        }
        default_sparams = {
            "top_p": 0.7,
            "temperature": 0.4,
            "max_tokens": 1024,
            "frequency_penalty": 0.4,
            "presence_penalty": 0.2,
            "seed": random.randint(0,999)
            #default_seed = 42
        }
        for super_param in ['top_p', 'temperature', 'max_tokens', 'frequency_penalty', 'presence_penalty', 'seed']:
            if super_param in self.kwargs:
                super_value = self.kwargs[super_param]
                match super_param:
                    case 'max_tokens':
                        if 0 < int(super_value) <= 1024:
                            completion_args['max_tokens'] = int(super_value)
                        else:
                            raise Exception('max_tokens must fall on 1~1024')
                    case 'seed':
                        if 0 <= int(super_value) <= 999:
                            completion_args['seed'] = int(super_value)
                        else:
                            raise Exception('seed must fall on 0~999')      
                    case 'top_p':
                        if 0.1 <= float(super_value) <= 1.0:
                            completion_args['top_p'] = float(super_value)
                        else:
                            raise Exception('top_p must fall on 0.1~1.0')
                    case 'frequency_penalty':
                        if 0.2 <= float(super_value) <= 1.0:
                            completion_args['frequency_penalty'] = float(super_value)
                        else:
                            raise Exception('frequency_penalty must fall on 0.2~1.0')
                    case _:
                        if 0.0 <= float(super_value) <= 1.0:
                            completion_args[super_param] = float(super_value)
                        else:
                            raise Exception(f'{super_param} must fall on 0.0~1.0')
            if not super_param in completion_args:
                completion_args[super_param] = default_sparams[super_param]
        print(f"Query ready to go, last query line is:\n{query_in}\nSending query.")
        stream_resp = await client_actual.chat.completions.create(**completion_args)
        if client_options['stream']:
        #print(f'query: {query}')
            reply_appended = ''
            async for chunk in stream_resp:
                token = chunk.choices[0].delta.content
                await asyncio.sleep(0)
                print(token, end='', flush=True)
                if token != '':
                    if True:
                        reply_appended = reply_appended + token
                        await websocket.send(wrap_ws_formatter('100', 'continue', token, 'carriage'))
                    else:
                        break
            await websocket.send(wrap_ws_formatter('1000', 'streaming_done', f"streaming has finished with seed {completion_args['seed']}", 'info'))
            reply_appended_insertion = json.dumps({'role': 'assistant', 'content': reply_appended}, ensure_ascii=False)
            print(f"Finished replying-{self.traceray_id}:{session[3]}, with seed {completion_args['seed']}")
        else:
            token_combined = stream_resp.choices[0].message.content
            print(token_combined)
            await websocket.send(wrap_ws_formatter('200', 'reply', token_combined, 'carriage'))
            reply_appended_insertion = json.dumps({'role': 'assistant', 'content': token_combined}, ensure_ascii=False)
        if int(chat_session) > 0:
            stored = await self.rw_chat_session(chat_session, 'w', messages0)
            await self.rw_chat_session(chat_session, 'r', None)
            #print(stored)
            if stored[0]:
                stored = await self.rw_chat_session(chat_session, 'w', reply_appended_insertion)
                if stored[0]:
                    success = True
                    if stored[4]:
                        match stored[4]:
                            case 1:
                                await websocket.send(wrap_ws_formatter('204', 'deleted', f"Since session {chat_session} of user {username} exceeded {load_env('SESSION_MAX_TOKEN')} characters, The former part has been deleted to save storage--your ray tracer ID is {self.traceray_id}.", 'info'))
                            case 2:
                                await websocket.send(wrap_ws_formatter('200', 'delete_hint', f"Session {chat_session} of user {username} exceeded {load_env('SESSION_WARN_TOKEN')} characters, which will be chopped after exceeding {load_env('SESSION_MAX_TOKEN')}, make backups if you want to--your ray tracer ID is {self.traceray_id}.", 'info'))
                else:
                    response_str = f"Chat reply recording failed, refer to administrator--your ray tracer ID is {self.traceray_id}. This can be a severe problem thats breaks your session savefile, stopping entire session."
                    print(f"出现如下异常27-{self.traceray_id}:{stored[1]}")
                    await websocket.send(wrap_ws_formatter('500', 'store_failed', response_str, 'error'))
                    await websocket.close(1000, 'Stopping connection due to critical server failure')
            else:
                response_str = f"Chat query recording failed, refer to administrator--your ray tracer ID is {self.traceray_id}. This can be a severe problem thats breaks your session savefile, stopping entire session."
                print(f"出现如下异常28-{self.traceray_id}:{stored[1]}")
                await websocket.send(wrap_ws_formatter('500', 'store_failed', response_str, 'error'))
                await websocket.close(1000, 'Stopping connection due to critical server failure')
            print(f"Finished entire loop-{self.traceray_id}:{session[3]}")
        else:
            success = True
            print(f"Finished non-recording loop-{self.traceray_id}:{session[3]}")

#异步标记程序, 不是必要的. 万一要用呢?

def callback_func_switch(future):
    print(f'!Stage2 passed abnormally!')

def callback_check_permit(future):
    print(f'Stage1 passed:\n{future.result()}')
    
#主要线程驱动器

async def main_logic(websocket, path):
    try:
        loop = asyncio.get_event_loop()
        thread_instance = ws_threading_instance(websocket)

        permit = await thread_instance.check_permit()
        print(permit)
        if not isinstance(permit, tuple) or not permit[0]:
            raise Exception('Security exception occured')

        await thread_instance.function_switch()

    except Exception as excepted:
        await websocket.close(1010, 'Destroying ws due to connection loss')
        print(f'Exception: {excepted}. Likely connection loss.')
        raise Exception('Force closure of connection')

async def prepare_thread():
    client = AsyncOpenAI(
        api_key='EMPTY',
        base_url=load_env('MCORE_ADDR'),
    )
    model_list = await client.models.list()
    model_type = model_list.data[0].id
    print(f"First time confirm--model type is {model_type}")

if __name__ == '__main__':

    asyncio.run(prepare_thread())
    print('Server started!')

    new_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(new_loop)

    start_server = websockets.serve(functools.partial(main_logic, path=None), '0.0.0.0', 5000)
    try:
        asyncio.get_event_loop().run_until_complete(start_server)
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        print("Server stopped!")
