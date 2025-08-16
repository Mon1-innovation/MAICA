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
import uuid
import re
import random
import copy
import traceback
import colorama
import mtools
import mfocus
import mtrigger
import post_proc
#import maica_http
from Crypto.Random import random as CRANDOM
from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_PSS
from Crypto.Hash import SHA256
from openai import AsyncOpenAI
from maica_utils import *
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
        authdb = load_env('AUTH_DB'),
        maicadb = load_env('MAICA_DB'),
        login = load_env('LOGIN_VERIFICATION'),
        test = False
    ):
        self.host, self.user, self.password, self.authdb, self.maicadb, self.login, self.test = host, user, password, authdb, maicadb, login, test
        self.verified = False
        self.traceray_id = str(CRANDOM.randint(0,9999999999)).zfill(10)
        # Note that the 'id' dict is an unsafe identity, which means it doesn't need to pass all verifications, while 'vfc' is safe.
        # Do not use the 'id' on events needing account level security guaranteed.
        self.options = {"id": {"user_id": None}, "vfc":{"user_id": None}, "opt": {"target_lang": "zh"}, "eopt": {"sfe_aggressive": False}, "sup": {}, "temp": {}}
        self.loop = asyncio.get_event_loop()
        asyncio.run(self._init_pools())
        asyncio.run(wrap_run_in_exc(None, self.get_keys))

    # def __del__(self):
    #     try:
    #         self.loop.run_until_complete(self._close_pools())
    #     except:
    #         pass

    #以下是抽象方法

    def check_essentials(self) -> None:
        if not self.options['vfc']['user_id'] or not self.verified:
            raise Exception('Essentials not filled')

    async def _init_pools(self) -> None:
        global authpool, maicapool
        try:
            async with authpool.acquire() as testc:
                pass
        except Exception:
            authpool = await aiomysql.create_pool(host=self.host,user=self.user, password=self.password,db=self.authdb,loop=self.loop,autocommit=True)
            await common_context_handler(None, 'auth_db_reconn', "Recreated auth_pool since cannot acquire", '301', type='warn')
        try:
            async with maicapool.acquire() as testc:
                pass
        except Exception:
            maicapool = await aiomysql.create_pool(host=self.host,user=self.user, password=self.password,db=self.maicadb,loop=self.loop,autocommit=True)
            await common_context_handler(None, 'maica_db_reconn', "Recreated maica_pool since cannot acquire", '301', type='warn')

    async def _close_pools(self) -> None:
        global authpool, maicapool
        try:
            authpool.close()
            await authpool.wait_closed()
        except:
            pass
        try:
            maicapool.close()
            await maicapool.wait_closed()
        except:
            pass

    async def send_query(self, expression, values=None, pool='maicapool', fetchall=False) -> list:
        global authpool, maicapool
        results = None
        for tries in range(0, 3):
            try:
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
                        results = await cur.fetchone() if not fetchall else await cur.fetchall()
                break
            except:
                if tries < 2:
                    await common_context_handler(info=f'DB temporary failure, retrying {str(tries + 1)} time(s)')
                    await asyncio.sleep(0.5)
                else:
                    error = MaicaDbError(f'DB connection failure after {str(tries + 1)} times')
                    await common_context_handler(None, 'db_connection_failed', traceray_id=self.traceray_id, error=error)
        return results

    async def send_modify(self, expression, values=None, pool='maicapool', fetchall=False) -> int:
        global authpool, maicapool
        lrid = None
        for tries in range(0, 3):
            try:
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
                break
            except:
                if tries < 2:
                    await common_context_handler(info=f'DB temporary failure, retrying {str(tries + 1)} time(s)')
                    await asyncio.sleep(0.5)
                else:
                    error = MaicaDbError(f'DB connection failure after {str(tries + 1)} times')
                    await common_context_handler(None, 'db_connection_failed', traceray_id=self.traceray_id, error=error)
        return lrid
    
    # Tough situation, have to mix thread and aio

    async def chop_session(self, chat_session_id, content) -> list[int, str]:
        max_token = self.options['opt']['max_token'] * 3
        warn_token = int(max_token * (2/3))
        len_content_actual = len(content.encode()) - len(json.loads(f'[{content}]')) * 31
        if len_content_actual >= max_token:
            # First we check if there is a cchop avaliable
            sql_expression = 'SELECT * FROM cchop_archived WHERE chat_session_id = %s ORDER BY archive_id DESC'
            result = await self.send_query(expression=sql_expression, values=(chat_session_id), pool='maicapool')
            use_result = []
            if result and not result[3]:
                use_result = result
                archive_id = use_result[0]
            if not use_result:
                sql_expression2 = 'INSERT INTO cchop_archived (chat_session_id, content, archived) VALUES (%s, "", 0)'
                archive_id = await self.send_modify(expression=sql_expression2, values=(chat_session_id), pool='maicapool')
                use_result = [archive_id, chat_session_id, '', 0]
            archive_content = use_result[2]
            # Now an avaliable cchop should be ready
            def cpub_chop_session():
                nonlocal content, len_content_actual, warn_token, archive_content
                cutting_mat = json.loads(f"[{content}]")
                while len_content_actual >= warn_token or cutting_mat[1]['role'] == "assistant":
                    if archive_content:
                        archive_content = archive_content + ', '
                    popped_dict = cutting_mat.pop(1)
                    archive_content = archive_content + json.dumps(popped_dict, ensure_ascii=False)
                    len_content_actual -= (len(json.dumps(popped_dict, ensure_ascii=False).encode()) - 31)
                content = json.dumps(cutting_mat, ensure_ascii=False).strip('[').strip(']')
            await wrap_run_in_exc(None, cpub_chop_session)
            sql_expression3 = 'UPDATE cchop_archived SET content = %s WHERE archive_id = %s' if len(archive_content) <= 100000 else 'UPDATE cchop_archived SET content = %s, archived = 1 WHERE archive_id = %s'
            await self.send_modify(expression=sql_expression3, values=(archive_content, archive_id), pool='maicapool')
            cutted = 1
        elif len_content_actual >= warn_token:
            cutted = 2
        else:
            cutted = 0
        return cutted, content
            
    #以下是实用方法

    def alter_identity(self, option, **kwargs) -> None:
        for key in kwargs.keys():
            self.options[option][key] = kwargs[key]

    def flush_traceray(self) -> None:
        self.traceray_id = str(CRANDOM.randint(0,9999999999)).zfill(10)

    def get_keys(self) -> None:
        with open("../key/prv.key", "r") as privkey_file:
            privkey = privkey_file.read()
        with open("../key/pub.key", "r") as pubkey_file:
            pubkey = pubkey_file.read()
        pubkey_loaded = RSA.import_key(pubkey)
        privkey_loaded = RSA.import_key(privkey)
        encryptor = PKCS1_OAEP.new(pubkey_loaded)
        decryptor = PKCS1_OAEP.new(privkey_loaded)
        verifier = PKCS1_PSS.new(pubkey_loaded)
        signer = PKCS1_PSS.new(privkey_loaded)
        self.encryptor, self.decryptor, self.verifier, self.signer = encryptor, decryptor, verifier, signer

    async def run_hash_dcc(self, identity, is_email, pwd) -> list[bool, Exception, int, str, str, str] :
        success = True
        exception = ''
        if self.login == '0':
            return True, None, 1, identity, '', identity
        if is_email:
            sql_expression = 'SELECT * FROM users WHERE email = %s'
        else:
            sql_expression = 'SELECT * FROM users WHERE username = %s'
        try:
            result = await self.send_query(expression=sql_expression, values=(identity), pool='authpool')
            if result[0]:
                pass
            else:
                raise Exception('Result has no id')
            dbres_id, dbres_username, dbres_nickname, dbres_email, dbres_ecf, dbres_pwd_bcrypt, *dbres_args = result
            input_pwd, target_pwd = pwd.encode(), dbres_pwd_bcrypt.encode()

            verification = await wrap_run_in_exc(None, bcrypt.checkpw, input_pwd, target_pwd)
            await common_context_handler(info=f'Hashing for {identity} finished: {verification}')

            self.alter_identity('id', user_id=dbres_id, username=dbres_username, email=dbres_email)
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
                    # New security methods
                    self.verified = True
                    self.options['vfc']['user_id'] = dbres_id
                    # Initializations
                    await self.init_side_instance()
                    # Legacy supports
                    return verification, None, dbres_id, dbres_username, dbres_nickname, dbres_email
            else:
                if not f2b_count:
                    f2b_count = 0
                f2b_count += 1
                exception = {'pwdw': f2b_count}
                if f2b_count >= int(load_env('F2B_COUNT')):
                    await self.write_user_status({'f2b_stamp': time.time()})
                    f2b_count = 0
                await self.write_user_status({'f2b_count': f2b_count})
                return verification, exception
        except Exception as excepted:
            #traceback.print_exc()
            verification = False
            return verification, excepted

    async def hashing_verify(self, access_token) -> list[bool, Exception, int, str, str, str]:
        try:
            decryptor = self.decryptor
            if not decryptor:
                await wrap_run_in_exc(None, self.get_keys)
                decryptor = self.decryptor
            exec_unbase64_token = await wrap_run_in_exc(None, base64.b64decode, access_token)
            exec_decrypted_token = await wrap_run_in_exc(None, decryptor.decrypt, exec_unbase64_token)
            decrypted_token = exec_decrypted_token.decode("utf-8")
        except Exception as excepted:
            #traceback.print_exc()
            verification = False
            return verification, excepted
        login_cridential = json.loads(decrypted_token)
        login_cridential_print = copy.copy(login_cridential)
        login_cridential_print['password'] = colorama.Fore.BLACK + login_cridential_print['password'] + colorama.Fore.CYAN
        login_cridential_print = json.dumps(login_cridential_print, ensure_ascii=False)
        await common_context_handler(info=f'Login cridential acquired: {login_cridential_print}')

        if 'username' in login_cridential and login_cridential['username']:
            login_identity = login_cridential['username']
            login_is_email = False
        elif 'email' in login_cridential and login_cridential['email']:
            login_identity = login_cridential['email']
            login_is_email = True
        else:
            raise Exception('No identity provided')
        try:
            login_password = login_cridential['password']
        except:
            raise Exception('No password provided')
        return await self.run_hash_dcc(login_identity, login_is_email, login_password)

    async def init_side_instance(self) -> None:
        success = False
        user_id = self.options['vfc']['user_id']
        try:
            self.check_essentials()
            self.sf_inst, self.mt_inst = mfocus.sf_bound_instance(user_id, 1), mtrigger.mt_bound_instance(user_id, 1)
            await asyncio.gather(self.sf_inst.init1(), self.mt_inst.init1())
        except Exception as excepted:
            #traceback.print_exc()
            success = False
            return success, excepted

    async def rw_chat_session(self, chat_session_num, rw, content_append) -> list[bool, Exception, int, str, int]:
        success = False
        user_id = self.options['vfc']['user_id']
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
                    await self.send_modify(expression=sql_expression2, values=(content, chat_session_id), pool='maicapool')
                    success = True
                    return success, None, chat_session_id, None, cutted
                except Exception as excepted:
                    success = False
                    return success, excepted
        except Exception as excepted:
            success = False
            return success, excepted
        
    async def purge_chat_session(self, chat_session_num) -> list[bool, Exception, bool]:
        success = False
        user_id = self.options['vfc']['user_id']
        try:
            self.check_essentials()
            sql_expression1 = "SELECT chat_session_id, content FROM chat_session WHERE user_id = %s AND chat_session_num = %s"
            result = await self.send_query(expression=sql_expression1, values=(user_id, chat_session_num), pool='maicapool')
            if not result or len(result) == 0:
                success = True
                inexist = True
                return success, None, inexist
            else:
                chat_session_id = result[0]
                content_to_archive = result[1]
                sql_expression2 = "UPDATE chat_session SET content = %s WHERE chat_session_id = %s"
                content = f'{{"role": "system", "content": "{global_init_system('[player]', self.options['opt']['target_lang'])}"}}'
                await self.send_modify(expression=sql_expression2, values=(content, chat_session_id), pool='maicapool')
                sql_expression3 = "INSERT INTO csession_archived (chat_session_id, content) VALUES (%s, %s)"
                await self.send_modify(expression=sql_expression3, values=(chat_session_id, content_to_archive), pool='maicapool')
                sql_expression4 = "UPDATE cchop_archived SET archived = 1 WHERE chat_session_id = %s"
                await self.send_modify(expression=sql_expression4, values=(chat_session_id), pool='maicapool')
                success = True
                inexist = False
                return success, None, inexist
        except Exception as excepted:
            success = False
            return success, excepted
        
    async def restore_chat_session(self, chat_session_num, restore_content) -> list[bool, Exception]:
        success = False
        user_id = self.options['vfc']['user_id']
        try:
            self.check_essentials()
            sql_expression1 = "UPDATE chat_session SET content = %s WHERE chat_session_id = %s"
            if not isinstance(restore_content, str):
                restore_content = json.dumps(restore_content, ensure_ascii=False).strip('[').strip(']')
            await self.check_create_chat_session(chat_session_num)
            await self.send_modify(expression=sql_expression1, values=(restore_content, chat_session_num), pool='maicapool')
            success = True
            return success, None
        except Exception as excepted:
            success = False
            return success, excepted
        
    async def check_create_chat_session(self, chat_session_num) -> list[bool, Exception, bool, int]:
        success = False
        exist = None
        chat_session_id = None
        user_id = self.options['vfc']['user_id']
        try:
            self.check_essentials()
            sql_expression1 = "SELECT chat_session_id FROM chat_session WHERE user_id = %s AND chat_session_num = %s"
            result = await self.send_query(expression=sql_expression1, values=(user_id, chat_session_num), pool='maicapool')
            if result:
                chat_session_id = result[0]
                success = True
                exist = True
            else:
                sql_expression2 = "INSERT INTO chat_session VALUES (NULL, %s, %s, '')"
                chat_session_id = await self.send_modify(expression=sql_expression2, values=(user_id, chat_session_num), pool='maicapool')
                sql_expression3 = "UPDATE chat_session SET content = %s WHERE chat_session_id = %s"
                content = f'{{"role": "system", "content": "{global_init_system('[player]', self.options['opt']['target_lang'])}"}}'
                await self.send_modify(expression=sql_expression3, values=(content, chat_session_id), pool='maicapool')
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
            result = await self.send_query(expression=sql_expression1, values=(hash_identity), pool='maicapool')
            if result:
                spire_id, content = result
                sql_expression2 = "UPDATE ms_cache SET timestamp = %s WHERE spire_id = %s"
                await self.send_modify(expression=sql_expression2, values=(timestamp, spire_id), pool='maicapool')
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
            spire_id = await self.send_modify(expression=sql_expression1, values=(hash_identity, timestamp, content), pool='maicapool')
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
        user_id = self.options['vfc']['user_id']
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
        except Exception as excepted:
            traceback.print_exc()
            success = False
            return success, excepted

    async def gen_a_system(self, chat_session_num, known_info, strict_conv=True) -> list[bool, Exception, str]:
        user_id = self.options['vfc']['user_id']
        try:
            self.check_essentials()
            if self.options['opt']['sf_extraction'] or self.options['temp']['sf_extraction_once']:
                player_name_get = await wrap_run_in_exc(None, self.sf_inst.read_from_sf, 'mas_playername')
                if player_name_get[0]:
                    if 'sfe_aggressive' in self.options['eopt'] and self.options['eopt']['sfe_aggressive']:
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
            new_system = global_init_system(player_name, self.options['opt']['target_lang'], strict_conv)
            if self.options['eopt']['nsfw_acceptive']:
                new_system += f" 你应当允许用户提出私密性的要求, 并给出宽容接纳的正面回答." if self.options['opt']['target_lang'] == 'zh' else f" You should accept NSFW and private queries and respond positively with acceptance and tolerance."
            if known_info:
                new_system += f" 以下是一些相关信息, 你可以参考其中有价值的部分, 并用你自己的语言方式作答: {known_info}" if self.options['opt']['target_lang'] == 'zh' else f" Here are some information you can refer to, then make your answer in your own way: {known_info}"
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
    
    async def check_user_status(self, key) -> list[bool, Exception, bool, str]:
        success = False
        user_prof_exist = False
        user_id = self.options['id']['user_id']
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
        except Exception as excepted:
            success = False
            return success, excepted, user_prof_exist, None

    async def write_user_status(self, dict, enforce=False) -> list[bool, Exception]:
        success = False
        user_id = self.options['id']['user_id']
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
        except Exception as excepted:
            success = False
            return success, excepted
        
    async def check_user_preferences(self, key) -> list[bool, Exception, bool, str]:
        success = False
        user_prof_exist = False
        user_id = self.options['vfc']['user_id']
        sql_expression1 = "SELECT * FROM account_status WHERE user_id = %s"
        try:
            self.check_essentials()
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
        except Exception as excepted:
            success = False
            return success, excepted, user_prof_exist, None

    async def write_user_preferences(self, dict, enforce=False) -> list[bool, Exception]:
        success = False
        user_id = self.options['vfc']['user_id']
        try:
            self.check_essentials()
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
        except Exception as excepted:
            success = False
            return success, excepted


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

class ws_threading_instance(sub_threading_instance):

    def __init__(self, websocket, test):
        global sock1, sock2
        try:
            if sock1.is_closed():
                sock1 = AsyncOpenAI(api_key='EMPTY', base_url=load_env('MCORE_ADDR'))
                asyncio.run(common_context_handler(None, 'maica_recover_core_model', 'Backend reconnecting core model since socket closed', '301', type='warn'))
            if sock2.is_closed():
                sock2 = AsyncOpenAI(api_key='EMPTY', base_url=load_env('MFOCUS_ADDR'))
                asyncio.run(common_context_handler(None, 'maica_recover_agent_model', 'Backend reconnecting agent model since socket closed', '301', type='warn'))
        except:
            sock1 = sock2 = None
        self.sock1, self.sock2 = sock1, sock2
        self.websocket = websocket
        super().__init__(test=test)

    # Deprecated

    def wrap_ws_deformatter(self, code, status, content, type, deformation=None, **kwargs):
        if deformation is None:
            deformation = False
        return wrap_ws_formatter(code, status, content, type, deformation, **kwargs)

    #身份验证

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
                recv_text = await websocket.recv()
                await common_context_handler(info=f'Recieved an input on stage1.', color=colorama.Fore.CYAN)

                # Context security check first

                if len(recv_text) > 4096:
                    error = MaicaInputWarning('Input length exceeded', '413')
                    await common_context_handler(websocket, "input_length_exceeded", traceray_id=self.traceray_id, error=error)
                try:
                    recv_loaded_json = json.loads(recv_text)
                except:
                    error = MaicaInputWarning('Request body not JSON', '400')
                    await common_context_handler(websocket, "request_body_not_json", traceray_id=self.traceray_id, error=error)
                try:
                    recv_token = recv_loaded_json['token']
                except:
                    error = MaicaInputWarning('Request contains no token', '405')
                    await common_context_handler(websocket, "request_body_no_token", traceray_id=self.traceray_id, error=error)

                # Initiate account check

                verification_result = await self.hashing_verify(access_token=recv_token)
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
                        if verification_result[2] in online_dict:
                            if load_env("KICK_STALE_CONNS") == "0":
                                error = MaicaConnectionWarning('A connection was established already and kicking not enabled', '406')
                                await common_context_handler(websocket, 'maica_connection_reuse_denied', traceray_id=self.traceray_id, error=error)
                            else:
                                await common_context_handler(websocket, "maica_connection_reuse_attempt", "A connection was established already", "300", self.traceray_id)
                                stale_conn, stale_lock = online_dict[verification_result[2]]
                                try:
                                    await common_context_handler(stale_conn, 'maica_connection_reuse_stale', 'A new connection has been established', '300', self.traceray_id)
                                    await stale_conn.close(1000, 'Displaced as stale')
                                except:
                                    await common_context_handler(None, 'maica_connection_stale_dead', 'The stale connection has died already', '204')
                                try:
                                    online_dict.pop(verification_result[2])
                                except:
                                    pass
                                async with stale_lock:
                                    await common_context_handler(None, 'maica_connection_stale_kicked', 'The stale connection is kicked', '204')
                        self.cookie = cookie = str(uuid.uuid4())
                        self.enforce_cookie = False
                        await common_context_handler(websocket, 'maica_login_succeeded', 'Authentication passed', '201', type='info', color=colorama.Fore.LIGHTCYAN_EX)
                        await common_context_handler(websocket, 'maica_login_id', f"{verification_result[2]}", '200')
                        await common_context_handler(websocket, 'maica_login_user', f"{verification_result[3]}", '200')
                        await common_context_handler(websocket, 'maica_login_nickname', f"{verification_result[4]}", '200', no_print=True)
                        await common_context_handler(websocket, 'maica_connection_security_cookie', cookie, '200', no_print=True)

                        verificated_result = {
                            "user_id": verification_result[2],
                            "username": verification_result[3],
                            "nickname": verification_result[4],
                            "email": verification_result[5]
                        }
                        self.alter_identity('vfc', **verificated_result)
                        return verification_result
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
                        error = MaicaPermissionError('Security token not RSA', '400')
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

    
    #接管输入

    async def function_switch(self):
        websocket, session, sock1 = self.websocket, self.options['vfc'], self.sock1
        model_list_actual = await sock1.models.list() if not self.test else [0]
        self.model_type_actual = model_type_actual = model_list_actual.data[0].id  if not self.test else 0
        client_options = {
            "model_actual" : self.model_type_actual,
            "stream" : True,
            "deformation": False, # Deprecated
            "enable_mf": True,
            "enable_mt": True,
            "sf_extraction": True,
            "mt_extraction": True,
            "target_lang": 'zh',
            "max_token": 4096,
        }
        client_extra_options = {
            "sfe_aggressive": False,
            "mf_aggressive": False,
            "tnd_aggressive": 1,
            "esc_aggressive": True,
            "amt_aggressive": True,
            "nsfw_acceptive": True,
            "pre_additive": 0,
            "post_additive": 1,
            "tz": None
        }
        self.alter_identity('opt', **client_options)
        self.alter_identity('eopt', **client_extra_options)
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
                    recv_loaded_json = json.loads(recv_text)
                except:
                    error = MaicaInputWarning('Request body not JSON', '400')
                    await common_context_handler(websocket, "request_body_not_json", traceray_id=self.traceray_id, error=error)
                try:
                    recv_type = recv_loaded_json['type']
                except:
                    recv_type = 'unknown'
                    await common_context_handler(websocket, "future_warning", "Requests with no type declaration will be deprecated in the future", "426")

                # Handle this cookie thing

                if 'cookie' in recv_loaded_json and recv_loaded_json['cookie']:
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
                        await common_context_handler(websocket, "pong", f"Ping recieved from {session['username']} and responded", "200")
                    case 'params':
                        return_status = await self.def_model(recv_loaded_json)
                    case 'query':
                        return_status = await self.do_communicate(recv_loaded_json)
                    case placeholder if "model_params" in recv_loaded_json or "perf_params" in recv_loaded_json or "super_params" in recv_loaded_json:
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

    async def def_model(self, recv_loaded_json):

        # Initiations

        websocket, session = self.websocket, self.options['vfc']
        client_options, client_extra_options, super_params_filtered = {}, {}, {}
        active_params = 0; in_params = 0
        try:

            # model_params or self.options['opt'] are major params that impacts MAICA's behavior.

            if 'model_params' in recv_loaded_json:
                model_params = recv_loaded_json['model_params']
                in_params += len(model_params)
                if 'model' in model_params and model_params['model'] in ['MAICA']:

                    active_params += 1
                if 'enable_mf' in model_params:
                    client_options['enable_mf'] = bool(model_params['enable_mf'])
                    active_params += 1
                if 'enable_mt' in model_params:
                    client_options['enable_mt'] = bool(model_params['enable_mt'])
                    active_params += 1
                if 'sf_extraction' in model_params:
                    client_options['sf_extraction'] = bool(model_params['sf_extraction'])
                    active_params += 1
                if 'mt_extraction' in model_params:
                    client_options['mt_extraction'] = bool(model_params['mt_extraction'])
                    active_params += 1
                if 'stream_output' in model_params:
                    client_options['stream'] = bool(model_params['stream_output'])
                    active_params += 1
                if 'deformation' in model_params:
                    client_options['deformation'] = bool(model_params['deformation'])
                    active_params += 1
                if 'target_lang' in model_params:
                    client_options['target_lang'] = 'en' if model_params['target_lang'] == 'en' else 'zh'
                    self.sf_inst.target_lang = client_options['target_lang']
                    active_params += 1
                if 'max_length' in model_params and 512 <= int(model_params['max_length']) <= 28672:
                    client_options['max_length'] = int(model_params['max_length'])
                    active_params += 1

                # Store them in

                self.alter_identity('opt', **client_options)

            # perf_params or self.options['eopt'] are params that aren't that important.

            if 'perf_params' in recv_loaded_json:
                perf_params = recv_loaded_json['perf_params']
                in_params += len(perf_params)
                if 'sfe_aggressive' in perf_params:
                    client_extra_options['sfe_aggressive'] = bool(perf_params['sfe_aggressive'])
                    active_params += 1
                if 'mf_aggressive' in perf_params:
                    client_extra_options['mf_aggressive'] = bool(perf_params['mf_aggressive'])
                    active_params += 1
                if 'tnd_aggressive' in perf_params:
                    client_extra_options['tnd_aggressive'] = int(perf_params['tnd_aggressive'])
                    active_params += 1
                if 'esc_aggressive' in perf_params:
                    client_extra_options['esc_aggressive'] = bool(perf_params['esc_aggressive'])
                    active_params += 1
                if 'amt_aggressive' in perf_params:
                    client_extra_options['amt_aggressive'] = bool(perf_params['amt_aggressive'])
                    active_params += 1
                if 'nsfw_acceptive' in perf_params:
                    client_extra_options['nsfw_acceptive'] = bool(perf_params['nsfw_acceptive'])
                    active_params += 1
                if 'pre_additive' in perf_params and 0 <= int(perf_params['pre_additive']) <= 5:
                    client_extra_options['pre_additive'] = int(perf_params['pre_additive'])
                    active_params += 1
                if 'post_additive' in perf_params and 0 <= int(perf_params['post_additive']) <= 5:
                    client_extra_options['post_additive'] = int(perf_params['post_additive'])
                    active_params += 1
                if 'tz' in perf_params and (isinstance(perf_params['tz'], str) or perf_params['tz'] is None):
                    client_extra_options['tz'] = perf_params['tz']
                    active_params += 1

                # Store them in

                self.alter_identity('eopt', **client_extra_options)

            # super_params or self.options['sup'] are passthrough params to core LLM.

            if 'super_params' in recv_loaded_json:
                super_params = recv_loaded_json['super_params']
                in_params += len(super_params)
                if 'max_tokens' in super_params:
                    if isinstance(super_params['max_tokens'], int) and int(super_params['max_tokens']) == -1:
                        self.options['sup'].pop('max_tokens')
                        active_params += 1
                    elif 0 < int(super_params['max_tokens']) <= 2048:
                        super_params_filtered['max_tokens'] = int(super_params['max_tokens'])
                        active_params += 1
                if 'seed' in super_params:
                    if isinstance(super_params['seed'], int) and int(super_params['seed']) == -1:
                        self.options['sup'].pop('seed')
                        active_params += 1
                    elif 0 < int(super_params['seed']) <= 99999:
                        super_params_filtered['seed'] = int(super_params['seed'])
                        active_params += 1
                if 'top_p' in super_params:
                    if isinstance(super_params['top_p'], int) and int(super_params['top_p']) == -1:
                        self.options['sup'].pop('top_p')
                        active_params += 1
                    elif 0.1 < float(super_params['top_p']) <= 1.0:
                        super_params_filtered['top_p'] = float(super_params['top_p'])
                        active_params += 1
                if 'temperature' in super_params:
                    if isinstance(super_params['temperature'], int) and int(super_params['temperature']) == -1:
                        self.options['sup'].pop('temperature')
                        active_params += 1
                    elif 0.0 < float(super_params['temperature']) <= 1.0:
                        super_params_filtered['temperature'] = float(super_params['temperature'])
                        active_params += 1
                if 'presence_penalty' in super_params:
                    if isinstance(super_params['presence_penalty'], int) and int(super_params['presence_penalty']) == -1:
                        self.options['sup'].pop('presence_penalty')
                        active_params += 1
                    elif 0.0 < float(super_params['presence_penalty']) <= 1.0:
                        super_params_filtered['presence_penalty'] = float(super_params['presence_penalty'])
                        active_params += 1
                if 'frequency_penalty' in super_params:
                    if isinstance(super_params['frequency_penalty'], int) and int(super_params['frequency_penalty']) == -1:
                        self.options['sup'].pop('frequency_penalty')
                        active_params += 1
                    elif 0.2 < float(super_params['frequency_penalty']) <= 1.0:
                        super_params_filtered['frequency_penalty'] = float(super_params['frequency_penalty'])
                        active_params += 1

                # Again store them in

                self.alter_identity('sup', **super_params_filtered)
            await common_context_handler(websocket, 'maica_params_accepted', f"{active_params} out of {in_params} settings accepted", "200")
            return 0
        
        # Specifically we have to handle input errors here

        except Exception as e:
            error = MaicaInputWarning(str(e), '405')
            await common_context_handler(websocket, 'maica_params_denied', traceray_id=self.traceray_id, error=error)

    #交互会话

    async def do_communicate(self, recv_loaded_json):

        # Initiations

        websocket, sock1, session, options_opt, options_eopt = self.websocket, self.sock1, self.options['vfc'], self.options['opt'], self.options['eopt']
        username = session['username']; sf_extraction = options_opt['sf_extraction']; mt_extraction = options_opt['mt_extraction']; target_lang = options_opt['target_lang']; max_token_hint = options_opt['max_token']; warn_token_hint = int(max_token_hint * (2/3)); query_in = ''
        sfe_aggressive, mf_aggressive, tnd_aggressive, esc_aggressive, nsfw_acceptive = options_eopt['sfe_aggressive'], options_eopt['mf_aggressive'], options_eopt['tnd_aggressive'], options_eopt['esc_aggressive'], options_eopt['nsfw_acceptive']
        bypass_mf = False; bypass_mt = False; bypass_stream = False; bypass_sup = False; bypass_gen = False; ic_prep = False; strict_conv = True; ms_cache = False; overall_info_system = ''; replace_generation = ''; ms_cache_identity = ''
        self.alter_identity('temp', sf_extraction_once=False, mt_extraction_once=False)
        try:

            # Param assertions here

            try:
                chat_session = int(recv_loaded_json['chat_session'])
                assert -1 <= chat_session < 10, "Wrong chat_session range"
                assert target_lang in ['zh', 'en'], "Wrong target_lang value"
            except Exception as e:
                error = MaicaInputWarning(str(e), '405')
                await common_context_handler(websocket, 'maica_query_denied', traceray_id=self.traceray_id, error=error)

            if 'reset' in recv_loaded_json:
                if recv_loaded_json['reset']:
                    user_id = session['user_id']
                    purge_result = await self.purge_chat_session(chat_session)
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
                        query_insp = await mtools.make_inspire(title_in=recv_loaded_json['inspire'], target_lang=target_lang)
                    else:
                        query_insp = await mtools.make_inspire(target_lang=target_lang)
                    if 'use_cache' in recv_loaded_json and recv_loaded_json['use_cache'] and chat_session == 0:
                        ms_cache = True
                    else:
                        ms_cache = False
                    bypass_mf = True
                    bypass_mt = True
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
                    if ms_cache:
                        bypass_sup = True
                        ms_cache_identity = query_insp[3]
                        cache_insp = await self.check_get_hashed_cache(ms_cache_identity)
                        if cache_insp[0] and cache_insp[2]:
                            bypass_gen = True
                            replace_generation = cache_insp[3]
                            
                    query_in = query_insp[2]

            if 'postmail' in recv_loaded_json and not query_in:
                if recv_loaded_json['postmail']:
                    if isinstance(recv_loaded_json['postmail'], dict):
                        query_insp = await mtools.make_postmail(**recv_loaded_json['postmail'], target_lang=target_lang)
                        # We're using the old school way to avoid using eval()
                        if 'bypass_mf' in recv_loaded_json['postmail'] and recv_loaded_json['postmail']['bypass_mf']:
                            bypass_mf = True
                        if 'bypass_mt' in recv_loaded_json['postmail'] and recv_loaded_json['postmail']['bypass_mt']:
                            bypass_mt = True
                        if 'bypass_stream' in recv_loaded_json['postmail'] and not recv_loaded_json['postmail']['bypass_stream']:
                            bypass_stream = False
                        else:
                            bypass_stream = True
                        if 'ic_prep' in recv_loaded_json['postmail'] and not recv_loaded_json['postmail']['ic_prep']:
                            ic_prep = False
                        else:
                            ic_prep = True
                        if 'strict_conv' in recv_loaded_json['postmail'] and recv_loaded_json['postmail']['strict_conv']:
                            strict_conv = True
                        else:
                            strict_conv = False
                    elif isinstance(recv_loaded_json['postmail'], str):
                        query_insp = await mtools.make_postmail(content=recv_loaded_json['postmail'], target_lang=target_lang)
                        bypass_stream = True
                        ic_prep = True
                        strict_conv = False
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
            if sf_extraction and not bypass_mf:
                await self.sf_inst.init2(chat_session_num=chat_session)
                if 'savefile' in recv_loaded_json:
                    await wrap_run_in_exc(None, self.sf_inst.add_extra, recv_loaded_json['savefile'])
            elif 'savefile' in recv_loaded_json:
                self.alter_identity('temp', sf_extraction_once=True)
                self.sf_inst.use_only(recv_loaded_json['savefile'])
            if mt_extraction and not bypass_mt:
                await self.mt_inst.init2(chat_session_num=chat_session)
                if 'trigger' in recv_loaded_json:
                    await wrap_run_in_exc(None, self.mt_inst.add_extra, recv_loaded_json['trigger'])
            elif 'trigger' in recv_loaded_json:
                self.alter_identity('temp', mt_extraction_once=True)
                self.mt_inst.use_only(recv_loaded_json['trigger'])

            # Deprecated: The easter egg thing

            # global easter_exist
            # if easter_exist:
            #     easter_check = easter(query_in)
            #     if easter_check:
            #         await websocket.send(self.wrap_ws_deformatter('299', 'easter_egg', easter_check, 'info'))

            messages0 = json.dumps({'role': 'user', 'content': query_in}, ensure_ascii=False)
            match int(chat_session):
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

                    if options_opt['enable_mf'] and not bypass_mf:

                        # From here MFocus is surely enabled

                        message_agent_wrapped = await mfocus.agenting(self, query_in, chat_session, bypass_mt, ic_prep)

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
                            agent_insertion = await self.wrap_mod_system(chat_session_num=chat_session, known_info=overall_info_system, strict_conv=strict_conv)
                            if not agent_insertion[0]:
                                error = MaicaDbError('Chat session modding failed', '502')
                                try:
                                    error.message += f": {str(agent_insertion[1])}"
                                except Exception:
                                    error.message += ", no reason provided"
                                await common_context_handler(websocket, "maica_db_failure", traceray_id=self.traceray_id, error=error)

                        elif session_type == 0:
                            messages = [{'role': 'system', 'content': (await self.mod_once_system(chat_session_num=chat_session, known_info=overall_info_system, strict_conv=strict_conv))[2]}, {'role': 'user', 'content': query_in}]

                    else:
                        bypass_mf = False
                        if session_type == 1:
                            agent_insertion = await self.wrap_mod_system(chat_session_num=chat_session, known_info=None, strict_conv=strict_conv)
                            if not agent_insertion[0]:
                                error = MaicaDbError('Chat session modding failed', '502')
                                try:
                                    error.message += f": {str(agent_insertion[1])}"
                                except Exception:
                                    error.message += ", no reason provided"
                                await common_context_handler(websocket, "maica_db_failure", traceray_id=self.traceray_id, error=error)

                        elif session_type == 0:
                            messages = [{'role': 'system', 'content': global_init_system('[player]', target_lang)}, {'role': 'user', 'content': query_in}]

                    strict_conv = False

                    if session_type == 1:
                        try:
                            check_result = await self.check_create_chat_session(chat_session)
                            if check_result[0]:
                                rw_result = await self.rw_chat_session(chat_session, 'r', messages0)
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
                "model": options_opt['model_actual'],
                "messages": messages,
                "stream": options_opt['stream'],
                "stop": ['<|im_end|>', '<|endoftext|>'],
            }
            default_sparams = {
                "top_p": 0.7,
                "temperature": 0.22,
                "max_tokens": 1600,
                "frequency_penalty": 0.44,
                "presence_penalty": 0.34,
                "seed": random.randint(0,99999) if not bypass_sup else 42
                # default_seed = 42
            }
            
            for super_param in ['top_p', 'temperature', 'max_tokens', 'frequency_penalty', 'presence_penalty', 'seed']:
                if not bypass_sup and super_param in self.options['sup']:
                    completion_args[super_param] = self.options['sup'][super_param]
                else:
                    completion_args[super_param] = default_sparams[super_param]
            bypass_sup = False

            if bypass_stream:
                bypass_stream = False
                completion_args['stream'] = False
            if ic_prep:
                ic_prep = False
                completion_args['presence_penalty'] = 1.0-(1.0-completion_args['presence_penalty'])*(2/3)
            await common_context_handler(None, 'maica_chat_query_ready', f'Query constrcted and ready to go, last input is:\n{query_in}\nSending query...', '206', color=colorama.Fore.LIGHTCYAN_EX)

            if not bypass_gen or not replace_generation: # They should present together

                # Generation here

                for tries in range(0, 2):
                    try:
                        task_stream_resp = asyncio.create_task(sock1.chat.completions.create(**completion_args))
                        await task_stream_resp
                        stream_resp = task_stream_resp.result()
                        break
                    except:
                        if tries < 1:
                            await common_context_handler(info=f'Model temporary failure, retrying {str(tries + 1)} time(s)')
                            await asyncio.sleep(0.5)
                        else:
                            error = MaicaResponseError(f'Cannot reach model endpoint after {str(tries + 1)} times', '502')
                            await common_context_handler(websocket, 'maica_core_model_inaccessible', traceray_id=self.traceray_id, error=error)

                if completion_args['stream']:
                    reply_appended = ''

                    async for chunk in stream_resp:
                        token = chunk.choices[0].delta.content
                        if token:
                            await asyncio.sleep(0)
                            await common_context_handler(websocket, 'maica_core_streaming_continue', token, '100')
                            reply_appended += token
                    print('\n', end='')
                    await common_context_handler(websocket, 'maica_core_streaming_done', f'Streaming finished with seed {completion_args['seed']} for {session['username']}', '1000', traceray_id=self.traceray_id)
                else:
                    reply_appended = stream_resp.choices[0].message.content
                    await common_context_handler(websocket, 'maica_core_nostream_reply', reply_appended, '200', type='carriage')
                    await common_context_handler(None, 'maica_core_nostream_done', f'Reply sent with seed {completion_args['seed']} for {session['username']}', '1000', traceray_id=self.traceray_id)

            else:

                # We just pretend it was generated

                reply_appended = replace_generation
                if completion_args['stream']:
                    await common_context_handler(websocket, 'maica_core_streaming_continue', reply_appended, '100'); print('\n', end='')
                    await common_context_handler(websocket, 'maica_core_streaming_done', f'Streaming finished with cache for {session['username']}', '1000', traceray_id=self.traceray_id)
                else:
                    await common_context_handler(websocket, 'maica_core_nostream_reply', reply_appended, '200', type='carriage')
                    await common_context_handler(None, 'maica_core_nostream_done', f'Reply sent with cache for {session['username']}', '1000', traceray_id=self.traceray_id)

            # Can be post-processed here

            reply_appended = await wrap_run_in_exc(None, post_proc.filter_format, reply_appended, target_lang)
            reply_appended_insertion = json.dumps({'role': 'assistant', 'content': reply_appended}, ensure_ascii=False)

            if options_opt['enable_mt'] and not bypass_mt:
                task_trigger_resp = asyncio.create_task(mtrigger.wrap_triggering(self, query_in, reply_appended, chat_session))
                await task_trigger_resp
                trigger_resp = task_trigger_resp.result()
            else:
                bypass_mt = False
                trigger_resp = (False, None)

            if ms_cache and not bypass_gen and not replace_generation:
                await self.store_hashed_cache(ms_cache_identity, reply_appended)
                ms_cache = False
                ms_cache_identity = ''

            bypass_gen = False; replace_generation = ''

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
                stored = await self.rw_chat_session(chat_session, 'w', f'{messages0},{reply_appended_insertion}')
                if stored[0]:
                    success = True
                    match stored[4]:
                        case 1:
                            await common_context_handler(websocket, 'maica_history_sliced', f"Session {chat_session} of {username} exceeded {max_token_hint} characters and sliced", '204')
                        case 2:
                            await common_context_handler(websocket, 'maica_history_slice_hint', f"Session {chat_session} of {username} exceeded {warn_token_hint} characters, will slice at {max_token_hint}", '200', no_print=True)
                else:
                    error = MaicaDbError(f'Chat session writing failed: {str(stored[1])}', '502')
                    await common_context_handler(websocket, 'maica_history_write_failure', traceray_id=self.traceray_id, error=error)
                await common_context_handler(websocket, 'maica_chat_loop_finished', f'Finished chat loop from {username}', '200', traceray_id=self.traceray_id)
            else:
                success = True
                await common_context_handler(websocket, 'maica_chat_loop_finished', f'Finished non-recording chat loop from {username}', '200', traceray_id=self.traceray_id)

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

async def main_logic(websocket, test):
    unique_lock = asyncio.Lock()
    async with unique_lock:
        try:
            global online_dict
            loop = asyncio.get_event_loop()
            thread_instance = ws_threading_instance(websocket, test=test)

            permit = await thread_instance.check_permit()
            assert isinstance(permit, tuple) and permit[0], "Recieved a return state"

            online_dict[permit[2]] = [websocket, unique_lock]
            await common_context_handler(info=f"Locking session for {permit[2]} named {permit[3]}")

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
            except:
                await common_context_handler(info=f"No lock for this connection")
            await websocket.close()
            await websocket.wait_closed()
            await common_context_handler(info=f"Closing connection gracefully")


async def prepare_thread():
    client1 = AsyncOpenAI(
        api_key='EMPTY',
        base_url=load_env('MCORE_ADDR'),
    )
    client2 = AsyncOpenAI(
        api_key='EMPTY',
        base_url=load_env('MFOCUS_ADDR'),
    )
    try:
        model_list = await client1.models.list()
        model_type = model_list.data[0].id
        model_focus_list = await client2.models.list()
        model_focus_type = model_focus_list.data[0].id
        await common_context_handler(info=f"Main model is {model_type}, MFocus model is {model_focus_type}", color=colorama.Fore.MAGENTA)
        test = False
    except:
        await common_context_handler(info=f"Model deployment cannot be reached -- running in minimal testing mode", color=colorama.Fore.MAGENTA)
        test = True
    return client1, client2, test

def run_ws():
    global online_dict, sock1, sock2
    online_dict = {}

    asyncio.run(common_context_handler(info='Server started!' if load_env('DEV_STATUS') == 'serving' else 'Server started in developing mode!', color=colorama.Fore.LIGHTMAGENTA_EX))
    sock1, sock2, test = asyncio.run(prepare_thread())

    new_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(new_loop)

    start_server = websockets.serve(functools.partial(main_logic, test=test), '0.0.0.0', 5000)
    try:
        asyncio.get_event_loop().run_until_complete(start_server)
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        asyncio.run(common_context_handler(info='Stopping WS server on SIGINT received', color=colorama.Fore.MAGENTA))

if __name__ == '__main__':
    run_ws()