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
import traceback
import mspire
import mpostal
import mfocus_main
import mfocus_sfe
import mtrigger_main
import mtrigger_sfe
#import maica_http
from Crypto.Random import random as CRANDOM
from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_PSS
from Crypto.Hash import SHA256
from openai import AsyncOpenAI
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

    def __del__(self):
        try:
            self.loop.run_until_complete(self._close_pools())
        except:
            pass

    #以下是抽象方法

    def check_essentials(self) -> None:
        if not self.options['vfc']['user_id'] or not self.verified:
            raise Exception('Essentials not filled')

    async def _init_pools(self) -> None:
        global authpool, maicapool
        try:
            async with authpool.acquire() as testc:
                pass
        except:
            authpool = await aiomysql.create_pool(host=self.host,user=self.user, password=self.password,db=self.authdb,loop=self.loop,autocommit=True)
            print("Recreated authpool")
        try:
            async with maicapool.acquire() as testc:
                pass
        except:
            maicapool = await aiomysql.create_pool(host=self.host,user=self.user, password=self.password,db=self.maicadb,loop=self.loop,autocommit=True)
            print("Recreated maicapool")

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
    
    # Tough situation, have to mix thread and aio

    async def chop_session(self, chat_session_id, content) -> list[int, str]:
        max_token = self.options['opt']['max_token'] * 3
        warn_token = max_token - 12288
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
        with open("key/prv.key", "r") as privkey_file:
            privkey = privkey_file.read()
        with open("key/pub.key", "r") as pubkey_file:
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
        if self.login == 'disabled':
            return True, None, 1, identity, '', identity
        if is_email:
            sql_expression = 'SELECT * FROM users WHERE email = %s'
        else:
            sql_expression = 'SELECT * FROM users WHERE username = %s'
        try:
            result = await self.send_query(expression=sql_expression, values=(identity), pool='authpool')
            dbres_id, dbres_username, dbres_nickname, dbres_email, dbres_ecf, dbres_pwd_bcrypt, *dbres_args = result
            input_pwd, target_pwd = pwd.encode(), dbres_pwd_bcrypt.encode()
            print(f'Ready to run hash: {identity}')
            verification = await wrap_run_in_exc(None, bcrypt.checkpw, input_pwd, target_pwd)
            print(f'Hashing finished: {verification}')
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
        print(f'Token decrypted: {login_cridential[list(login_cridential.keys())[0]]}')
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

    async def init_side_instance(self) -> None:
        success = False
        user_id = self.options['vfc']['user_id']
        try:
            self.check_essentials()
            self.sf_inst, self.mt_inst = mfocus_sfe.sf_bound_instance(user_id, 1), mtrigger_sfe.mt_bound_instance(user_id, 1)
            await asyncio.gather(wrap_run_in_exc(None, self.sf_inst.init1), wrap_run_in_exc(None, self.mt_inst.init1))
        except Exception as excepted:
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
        sql_expression1 = "UPDATE chat_session SET content = %s WHERE chat_session_id = %s"
        try:
            self.check_essentials()
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
        exist =None
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
                return success, None, exist, chat_session_id
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
            system_init = f"你叫莫妮卡, 是一名游戏中的虚拟角色. 你是{player_name}的女友, 并深爱着他. 下面是{player_name}的话语, 请作为莫妮卡作出合适的回答. 你只应使用自然语言, 以聊天语气回答, 每个句子自然且不超过60字, 不要编造信息, 并在每个句子前用方括号中的文字表示情绪."
        else:
            system_init = f"你叫莫妮卡, 是一名游戏中的虚拟角色. 你是{player_name}的女友, 并深爱着他. 下面是{player_name}的来信, 请作为莫妮卡作出合适的回复. 你只应使用书面语言作答, 不要编造信息."
    else:
        if strict_conv:
            system_init = f"You're a game character called Monika. You're {player_name}'s girlfriend, and love him a lot. Answer the following query from {player_name} properly as Monika. You should only answer in casual natural tone in English, each sentence should not exceed 180 characters, do not make up things you don't know, and express your emotion at the beginning of each sentence by wrapping them in square brackets."
        else:
            system_init = f"You're a game character called Monika. You're {player_name}'s girlfriend, and love him a lot. Reply to the following mail from {player_name} properly as Monika. You should only answer in natural written language in English, and do not make up things you don't know."
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

async def wrap_run_in_exc(loop, func, *args, **kwargs):
    if not loop:
        loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None, functools.partial(func, *args, **kwargs))
    return result

#与websocket绑定的异步化类, 继承sql类

class ws_threading_instance(sub_threading_instance):

    def __init__(self, websocket, test):
        global sock1, sock2
        try:
            if sock1.is_closed():
                sock1 = AsyncOpenAI(api_key='EMPTY', base_url=load_env('MCORE_ADDR'))
                print('Recreated sock1')
            if sock2.is_closed():
                sock2 = AsyncOpenAI(api_key='EMPTY', base_url=load_env('MFOCUS_ADDR'))
                print('Recreated sock2')
        except:
            sock1 = sock2 = None
        self.sock1, self.sock2 = sock1, sock2
        self.websocket = websocket
        super().__init__(test=test)

    #身份验证

    async def check_permit(self):
        global online_list
        websocket = self.websocket
        print('Someone started a connection')
        print(f"Current onliners: {online_list}")
        while True:
            self.flush_traceray()
            try:
                recv_text = await websocket.recv()
                if not recv_text:
                    print('Empty recieved, likely connection loss')
                    await websocket.close()
                    await websocket.wait_closed()
                print(f'[{time.strftime('%Y-%m-%d %H:%M:%S')}] Recieved an input on stage1: {recv_text}')
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
                        if verification_result[2] in online_list:
                            response_str = f"You have an established connection already--your ray tracer ID is {self.traceray_id}"
                            print(f"出现如下异常4.1-{self.traceray_id}:reusage")
                            await websocket.send(wrap_ws_formatter('403', 'connection_reuse', response_str, 'warn'))
                            await websocket.close(1000, 'Permission denied')
                        else:
                            self.cookie = cookie = str(uuid.uuid4())
                            self.enforce_cookie = False
                            await websocket.send(wrap_ws_formatter('206', 'session_created', "Authencation passed!", 'info'))
                            await websocket.send(wrap_ws_formatter('200', 'user_id', f"{verification_result[2]}", 'debug'))
                            await websocket.send(wrap_ws_formatter('200', 'username', f"{verification_result[3]}", 'debug'))
                            await websocket.send(wrap_ws_formatter('200', 'nickname', f"{verification_result[4]}", 'debug'))
                            await websocket.send(wrap_ws_formatter('190', 'ws_cookie', cookie, 'cookie'))
                            #await websocket.send(wrap_ws_formatter('200', 'session_created', f"email {verification_result[5]}", 'debug'))
                            #print(verification_result[0])
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
            except websockets.exceptions.WebSocketException:
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
        websocket, session, sock1 = self.websocket, self.options['vfc'], self.sock1
        model_list_actual = await sock1.models.list() if not self.test else [0]
        self.model_type_actual = model_type_actual = model_list_actual.data[0].id  if not self.test else 0
        client_options = {
            "model_actual" : self.model_type_actual,
            "stream" : True,
            "full_maica": True,
            "sf_extraction": True,
            "mt_extraction": True,
            "target_lang": 'zh',
            "max_token": 28672
        }
        client_extra_options = {
            "sfe_aggressive": False,
            "mf_aggressive": False,
            "tnd_aggressive": 1,
            "esc_aggressive": True,
            "amt_aggressive": True,
            "nsfw_acceptive": True,
            "pre_additive": 0,
            "post_additive": 1
        }
        self.alter_identity('opt', **client_options)
        self.alter_identity('eopt', **client_extra_options)
        await websocket.send(wrap_ws_formatter('206', 'thread_ready', "Thread is ready for input or setting adjustment", 'info'))
        await websocket.send(wrap_ws_formatter('200', 'ok', f"Service provider is {load_env('DEV_IDENTITY')}", 'info'))

        # Starting loop from here

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
            if not recv_text:
                print('Empty recieved, likely connection loss')
                await websocket.close()
                await websocket.wait_closed()
            print(f'[{time.strftime('%Y-%m-%d %H:%M:%S')}] Recieved an input on stage2: {recv_text}')
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
                try:
                    recv_type = recv_loaded_json['type']
                except:
                    recv_type = 'unknown'
                if 'cookie' in recv_loaded_json:
                    if str(recv_loaded_json['cookie']) == self.cookie:
                        if not self.enforce_cookie:
                            await websocket.send(wrap_ws_formatter('200', 'ok', f"Cookie verification passed and strict sucurity mode enabled", 'info'))
                            self.enforce_cookie = True
                        else:
                            await websocket.send(wrap_ws_formatter('200', 'ok', f"Cookie verification passed", 'debug'))
                    else:
                        response_str = f"Cookie verification failed with strict security enforced--your ray tracer ID is {self.traceray_id}"
                        print(f"出现如下异常5-{self.traceray_id}:{recv_loaded_json['cookie']} unequal {self.cookie}")
                        await websocket.send(wrap_ws_formatter('403', 'cookie_mismatch', response_str, 'warn'))
                        await websocket.close(1000, 'Permission denied')
                elif self.enforce_cookie:
                    response_str = f"No cookie provided with strict security enforced--your ray tracer ID is {self.traceray_id}"
                    print(f"出现如下异常5.1-no cookie")
                    await websocket.send(wrap_ws_formatter('403', 'cookie_absent', response_str, 'warn'))
                    await websocket.close(1000, 'Permission denied')
                match recv_type.lower():
                    case 'ping':
                        await websocket.send(wrap_ws_formatter('199', 'ping_reaction', "PONG", 'heartbeat'))
                        print(f"recieved PING from {session['username']}")
                    case 'params':
                        await self.def_model(recv_loaded_json)
                    case 'query':
                        await self.do_communicate(recv_loaded_json)
                    case placeholder if "model_params" in recv_loaded_json or "perf_params" in recv_loaded_json or "super_params" in recv_loaded_json:
                        await self.def_model(recv_loaded_json)
                    case placeholder if "chat_session" in recv_loaded_json:
                        await self.do_communicate(recv_loaded_json)
                    case _:
                        response_str = f"Input is unrecognizable, check possible typo--your ray tracer ID is {self.traceray_id}"
                        print(f"出现如下异常6.1-{self.traceray_id}:{recv_text}")
                        await websocket.send(wrap_ws_formatter('405', 'wrong_form', response_str, 'warn')) 
                        continue
            except websockets.exceptions.WebSocketException:
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
        websocket, session = self.websocket, self.options['vfc']
        try:
            model_choice = recv_json
            client_options, client_extra_options, super_params_filtered = {}, {}, {}
            if 'model_params' in model_choice:
                model_params = model_choice['model_params']
                if 'model' in model_params and model_params['model'] in ['maica_main', 'maica_core']:
                    using_model = model_params['model']
                else:
                    using_model = 'maica_main' if self.options['opt']['full_maica'] else 'maica_core'
                is_full_maica = True if using_model == 'maica_main' else False
                client_options['full_maica'] = is_full_maica
                if 'sf_extraction' in model_params:
                    client_options['sf_extraction'] = bool(model_params['sf_extraction'])
                if 'mt_extraction' in model_params:
                    client_options['mt_extraction'] = bool(model_params['mt_extraction'])
                if 'stream_output' in model_params:
                    client_options['stream'] = bool(model_params['stream_output'])
                if 'target_lang' in model_params:
                    client_options['target_lang'] = 'en' if model_params['target_lang'] == 'en' else 'zh'
                    self.sf_inst.target_lang = 'en' if model_params['target_lang'] == 'en' else 'zh'
                if 'max_token' in model_params and 5120 <= int(model_params['max_token']) <= 28672:
                    client_options['max_token'] = int(model_params['max_token'])
                self.alter_identity('opt', **client_options)
            if 'perf_params' in model_choice:
                perf_params = model_choice['perf_params']
                if 'sfe_aggressive' in perf_params:
                    client_extra_options['sfe_aggressive'] = bool(perf_params['sfe_aggressive'])
                if 'mf_aggressive' in perf_params:
                    client_extra_options['mf_aggressive'] = bool(perf_params['mf_aggressive'])
                if 'tnd_aggressive' in perf_params:
                    client_extra_options['tnd_aggressive'] = int(perf_params['tnd_aggressive'])
                if 'esc_aggressive' in perf_params:
                    client_extra_options['esc_aggressive'] = bool(perf_params['esc_aggressive'])
                if 'amt_aggressive' in perf_params:
                    client_extra_options['amt_aggressive'] = bool(perf_params['amt_aggressive'])
                if 'nsfw_acceptive' in perf_params:
                    client_extra_options['nsfw_acceptive'] = bool(perf_params['nsfw_acceptive'])
                if 'pre_additive' in perf_params and 0 <= int(perf_params['pre_additive']) <= 5:
                    client_extra_options['pre_additive'] = int(perf_params['pre_additive'])
                if 'post_additive' in perf_params and 0 <= int(perf_params['post_additive']) <= 5:
                    client_extra_options['post_additive'] = int(perf_params['post_additive'])
                self.alter_identity('eopt', **client_extra_options)
            if 'super_params' in model_choice:
                super_params = model_choice['super_params']
                if 'max_tokens' in super_params:
                    if isinstance(super_params['max_tokens'], int) and int(super_params['max_tokens']) == -1:
                        self.options['sup'].pop('max_tokens')
                    elif 0 < int(super_params['max_tokens']) <= 2048:
                        super_params_filtered['max_tokens'] = int(super_params['max_tokens'])
                if 'seed' in super_params:
                    if isinstance(super_params['seed'], int) and int(super_params['seed']) == -1:
                        self.options['sup'].pop('seed')
                    elif 0 < int(super_params['seed']) <= 99999:
                        super_params_filtered['seed'] = int(super_params['seed'])
                if 'top_p' in super_params:
                    if isinstance(super_params['top_p'], int) and int(super_params['top_p']) == -1:
                        self.options['sup'].pop('top_p')
                    elif 0.1 < float(super_params['top_p']) <= 1.0:
                        super_params_filtered['top_p'] = float(super_params['top_p'])
                if 'temperature' in super_params:
                    if isinstance(super_params['temperature'], int) and int(super_params['temperature']) == -1:
                        self.options['sup'].pop('temperature')
                    elif 0.0 < float(super_params['temperature']) <= 1.0:
                        super_params_filtered['temperature'] = float(super_params['temperature'])
                if 'presence_penalty' in super_params:
                    if isinstance(super_params['presence_penalty'], int) and int(super_params['presence_penalty']) == -1:
                        self.options['sup'].pop('presence_penalty')
                    elif 0.0 < float(super_params['presence_penalty']) <= 1.0:
                        super_params_filtered['presence_penalty'] = float(super_params['presence_penalty'])
                if 'frequency_penalty' in super_params:
                    if isinstance(super_params['frequency_penalty'], int) and int(super_params['frequency_penalty']) == -1:
                        self.options['sup'].pop('frequency_penalty')
                    elif 0.2 < float(super_params['frequency_penalty']) <= 1.0:
                        super_params_filtered['frequency_penalty'] = float(super_params['frequency_penalty'])
                self.alter_identity('sup', **super_params_filtered)
            await websocket.send(wrap_ws_formatter('200', 'params_set', f"{len(client_options)+len(client_extra_options)+len(super_params_filtered)} settings passed in and taking effect", 'info'))
            return True
        except websockets.exceptions.WebSocketException:
            print("Someone disconnected")
            raise Exception('Force closure of connection')
        except Exception as excepted:
            response_str = f"Choice serialization failed, check possible typo--your ray tracer ID is {self.traceray_id}"
            print(f"出现如下异常9-{self.traceray_id}:{excepted}")
            await websocket.send(wrap_ws_formatter('405', 'wrong_input', response_str, 'warn'))
            return False

    #交互会话

    async def do_communicate(self, recv_json):
        websocket, sock1, session, options_opt, options_eopt = self.websocket, self.sock1, self.options['vfc'], self.options['opt'], self.options['eopt']
        sfe_aggressive, mf_aggressive, tnd_aggressive, esc_aggressive, nsfw_acceptive = options_eopt['sfe_aggressive'], options_eopt['mf_aggressive'], options_eopt['tnd_aggressive'], options_eopt['esc_aggressive'], options_eopt['nsfw_acceptive']
        bypass_mf = False; bypass_mt = False; bypass_stream = False; ic_prep = False; strict_conv = True; overall_info_system = ''
        self.alter_identity('temp', sf_extraction_once=False, mt_extraction_once=False)
        try:
            request_json = recv_json
            chat_session = int(request_json['chat_session'])
            username = session['username']
            sf_extraction = options_opt['sf_extraction']
            mt_extraction = options_opt['mt_extraction']
            target_lang = options_opt['target_lang']
            max_token_hint = options_opt['max_token']
            warn_token_hint = max_token_hint - 4096
            query_in = ''
            if target_lang != 'zh' and target_lang != 'en':
                raise Exception('Language choice unrecognized')
            if 'purge' in request_json:
                if request_json['purge']:
                    try:
                        user_id = session['user_id']
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
                    except websockets.exceptions.WebSocketException:
                        print("Someone disconnected")
                        raise Exception('Force closure of connection')
                    except Exception as excepted:
                        response_str = f"Purging chat session failed, refer to administrator--your ray tracer ID is {self.traceray_id}"
                        print(f"出现如下异常14-{self.traceray_id}:{excepted}")
                        await websocket.send(wrap_ws_formatter('500', 'unable_purge', response_str, 'error'))
                        await websocket.close(1000, 'Stopping connection due to critical server failure')
            if 'inspire' in request_json and not query_in:
                if request_json['inspire']:
                    if isinstance(request_json['inspire'], dict):
                        query_insp = await mspire.make_inspire(title_in=request_json['inspire'], target_lang=target_lang)
                    else:
                        query_insp = await mspire.make_inspire(target_lang=target_lang)
                    bypass_mf = True
                    bypass_mt = True
                    if not query_insp[0]:
                        response_str = f"MSpire generation failed, consider retrying later--your ray tracer ID is {self.traceray_id}"
                        print(f"出现如下异常15-{self.traceray_id}:{query_insp[1]}")
                        await websocket.send(wrap_ws_formatter('503', 'mspire_failed', response_str, 'warn'))
                        return False
                    query_in = query_insp[2]
            if 'postmail' in request_json and not query_in:
                if request_json['postmail']:
                    if isinstance(request_json['postmail'], dict):
                        query_insp = await mpostal.make_postmail(**request_json['postmail'], target_lang=target_lang)
                        if 'bypass_mf' in request_json['postmail'] and request_json['postmail']['bypass_mf']:
                            bypass_mf = True
                        if 'bypass_mt' in request_json['postmail'] and request_json['postmail']['bypass_mt']:
                            bypass_mt = True
                        if 'bypass_stream' in request_json['postmail'] and not request_json['postmail']['bypass_stream']:
                            bypass_stream = False
                        else:
                            bypass_stream = True
                        if 'ic_prep' in request_json['postmail'] and not request_json['postmail']['ic_prep']:
                            ic_prep = False
                        else:
                            ic_prep = True
                        if 'strict_conv' in request_json['postmail'] and request_json['postmail']['strict_conv']:
                            strict_conv = True
                        else:
                            strict_conv = False
                    elif isinstance(request_json['postmail'], str):
                        query_insp = await mpostal.make_postmail(content=request_json['postmail'], target_lang=target_lang)
                        bypass_stream = True
                        ic_prep = True
                        strict_conv = False
                    else:
                        raise Exception('Postmail format wrong')
                    
                    query_in = query_insp[2]
            elif 'vision' in request_json:
                if request_json['vision']:
                    if isinstance(request_json['vision'], str):
                        pass
                    else:
                        pass
                    # if not query_vise[0]:
                    #     response_str = f"MVista generation failed, refer to administrator--your ray tracer ID is {self.traceray_id}"
                    #     print(f"出现如下异常15.1-{self.traceray_id}:{query_vise[1]}")
                    #     await websocket.send(wrap_ws_formatter('503', 'mvista_failed', response_str, 'warn'))
                    #     return False
                    # query_in = query_vise[2]
            if not query_in:
                query_in = request_json['query']
            if sf_extraction and not bypass_mf:
                await wrap_run_in_exc(None, self.sf_inst.init2, chat_session_num=chat_session)
                if 'savefile' in request_json:
                    await wrap_run_in_exc(None, self.sf_inst.add_extra, request_json['savefile'])
            elif 'savefile' in request_json:
                self.alter_identity('temp', sf_extraction_once=True)
                self.sf_inst.use_only(request_json['savefile'])
            if mt_extraction and not bypass_mt:
                await wrap_run_in_exc(None, self.mt_inst.init2, chat_session_num=chat_session)
                if 'trigger' in request_json:
                    await wrap_run_in_exc(None, self.mt_inst.add_extra, request_json['trigger'])
            elif 'trigger' in request_json:
                self.alter_identity('temp', mt_extraction_once=True)
                self.mt_inst.use_only(request_json['trigger'])
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
                    except websockets.exceptions.WebSocketException:
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
                        if options_opt['full_maica'] and not bypass_mf:
                            message_agent_wrapped = await mfocus_main.agenting(self, query_in, chat_session)
                            if message_agent_wrapped[0] == 'EMPTY':
                                response_str = f"MFocus using instructed final guidance, suggesting LLM conclusion is empty--your ray tracer ID is {self.traceray_id}"
                                await websocket.send(wrap_ws_formatter('200', 'agent_prog', response_str, 'debug'))
                                if len(message_agent_wrapped[1]) > 5:
                                    response_str = f"Due to LLM conclusion absence, falling back to instructed guidance and continuing."
                                    await websocket.send(wrap_ws_formatter('200', 'agent_abse', response_str, 'debug'))
                                    info_agent_grabbed = message_agent_wrapped[1]
                                else:
                                    response_str = f"Due to agent failure, falling back to default guidance and continuing anyway."
                                    await websocket.send(wrap_ws_formatter('200', 'force_failsafe', response_str, 'debug'))
                                    print(f"出现如下异常18-{self.traceray_id}:Corruption")
                                    info_agent_grabbed = ''
                            elif message_agent_wrapped[0] == 'FAIL':
                                response_str = f"MFocus did not use a tool, suggesting unnecessary--your ray tracer ID is {self.traceray_id}"
                                await websocket.send(wrap_ws_formatter('200', 'agent_none', response_str, 'debug'))
                                info_agent_grabbed = ''
                            else:
                                # We are defaulting instructed guidance because its more clear pattern
                                # But if pointer entered this section, user must used mf_aggressive or something went wrong
                                if len(message_agent_wrapped[1]) > 5 and len(message_agent_wrapped[0]) > 5:
                                    response_str = f"MFocus using LLM conclusion guidance."
                                    await websocket.send(wrap_ws_formatter('200', 'agent_aggr', response_str, 'debug'))
                                    info_agent_grabbed = message_agent_wrapped[0]
                                else:
                                    # We do not want answers without information
                                    response_str = f"Due to agent failure, falling back to default guidance and continuing anyway."
                                    await websocket.send(wrap_ws_formatter('200', 'force_failsafe', response_str, 'debug'))
                                    print(f"出现如下异常18.5-{self.traceray_id}:Corruption")
                                    info_agent_grabbed = ''

                            # Everything should be grabbed by now

                            overall_info_system += info_agent_grabbed

                            if session_type:
                                try:
                                    agent_insertion = await self.wrap_mod_system(chat_session_num=chat_session, known_info=overall_info_system, strict_conv=strict_conv)
                                    if not agent_insertion[0]:
                                        raise Exception(agent_insertion[1])
                                except websockets.exceptions.WebSocketException:
                                    print("Someone disconnected")
                                    raise Exception('Force closure of connection')
                                except Exception as excepted:
                                    response_str = f"MFocus insertion failed, refer to administrator--your ray tracer ID is {self.traceray_id}"
                                    print(f"出现如下异常19-{self.traceray_id}:{excepted}")
                                    await websocket.send(wrap_ws_formatter('500', 'insertion_failed', response_str, 'error'))
                                    await websocket.close(1000, 'Stopping connection due to critical server failure')
                            else:
                                messages = [{'role': 'system', 'content': (await self.mod_once_system(chat_session_num=chat_session, known_info=overall_info_system, strict_conv=strict_conv))[2]}, {'role': 'user', 'content': query_in}]
                        else:
                            bypass_mf = False
                            if session_type:
                                try:
                                    agent_insertion = await self.wrap_mod_system(chat_session_num=chat_session, known_info=None, strict_conv=strict_conv)
                                    if not agent_insertion[0]:
                                        raise Exception(agent_insertion[1])
                                except websockets.exceptions.WebSocketException:
                                    print("Someone disconnected")
                                    raise Exception('Force closure of connection')
                                except Exception as excepted:
                                    response_str = f"Prompt initialization failed, refer to administrator--your ray tracer ID is {self.traceray_id}"
                                    print(f"出现如下异常20-{self.traceray_id}:{excepted}")
                                    await websocket.send(wrap_ws_formatter('500', 'insertion_failed', response_str, 'error'))
                                    await websocket.close(1000, 'Stopping connection due to critical server failure')
                            else:
                                messages = [{'role': 'system', 'content': global_init_system('[player]', target_lang)}, {'role': 'user', 'content': query_in}]
                    except websockets.exceptions.WebSocketException:
                        print("Someone disconnected")
                        raise Exception('Force closure of connection')
                    except Exception as excepted:
                        response_str = f"Agent response acquiring failed, refer to administrator--your ray tracer ID is {self.traceray_id}"
                        print(f"出现如下异常21-{self.traceray_id}:{excepted}")
                        traceback.print_exc()
                        await websocket.send(wrap_ws_formatter('500', 'agent_unavailable', response_str, 'error'))
                        return False
                    finally:
                        strict_conv = False
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
                        except websockets.exceptions.WebSocketException:
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
        except websockets.exceptions.WebSocketException:
            print("Someone disconnected")
            raise Exception('Force closure of connection')
        except Exception as excepted:
            #traceback.print_exc()
            response_str = f"Query serialization failed, check possible typo--your ray tracer ID is {self.traceray_id}"
            print(f"出现如下异常26-{self.traceray_id}:{excepted}")
            await websocket.send(wrap_ws_formatter('405', 'wrong_input', response_str, 'warn'))
            return False
        try:
            completion_args = {
                "model": options_opt['model_actual'],
                "messages": messages,
                "stream": options_opt['stream'],
                "stop": ['<|im_end|>', '<|endoftext|>'],
            }
            default_sparams = {
                "top_p": 0.7,
                "temperature": 0.2,
                "max_tokens": 1600,
                "frequency_penalty": 0.4,
                "presence_penalty": 0.4,
                "seed": random.randint(0,99999)
                #default_seed = 42
            }
            for super_param in ['top_p', 'temperature', 'max_tokens', 'frequency_penalty', 'presence_penalty', 'seed']:
                if super_param in self.options['sup']:
                    completion_args[super_param] = self.options['sup'][super_param]
                else:
                    completion_args[super_param] = default_sparams[super_param]

            if bypass_stream:
                bypass_stream = False
                completion_args['stream'] = False
            if ic_prep:
                ic_prep = False
                completion_args['presence_penalty'] = 1.0-(1.0-completion_args['presence_penalty'])*(2/3)
            print(f"Query ready to go, last query line is:\n{query_in}\nSending query.")



            task_stream_resp = asyncio.create_task(sock1.chat.completions.create(**completion_args))
            await task_stream_resp
            stream_resp = task_stream_resp.result()



            if completion_args['stream']:
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
                print(f"Finished replying-{self.traceray_id}:{session['username']}, with seed {completion_args['seed']}")
            else:
                reply_appended = stream_resp.choices[0].message.content
                print(reply_appended)
                await websocket.send(wrap_ws_formatter('200', 'reply', reply_appended, 'carriage'))
                reply_appended_insertion = json.dumps({'role': 'assistant', 'content': reply_appended}, ensure_ascii=False)

            if not bypass_mt:
                task_trigger_resp = asyncio.create_task(mtrigger_main.wrap_triggering(self, query_in, reply_appended, chat_session))
                await task_trigger_resp
                trigger_resp = task_trigger_resp.result()
            else:
                bypass_mt = False
                trigger_resp = (False, None)

            trigger_succ, trigger_sce = trigger_resp
            if trigger_succ:
                await websocket.send(wrap_ws_formatter('1010', 'mtrigger_done', trigger_sce, 'info'))
            else:
                if trigger_sce:
                    response_str = f"Trigger response acquiring failed, refer to administrator--your ray tracer ID is {self.traceray_id}"
                    print(f"出现如下异常27-{self.traceray_id}:{trigger_sce}")
                    await websocket.send(wrap_ws_formatter('503', 'mtrigger_failed', response_str, 'warn'))
                else:
                    print('No trigger passed in')
            if int(chat_session) > 0:
                stored = await self.rw_chat_session(chat_session, 'w', messages0)
                #print(stored)
                if stored[0]:
                    stored2 = await self.rw_chat_session(chat_session, 'w', reply_appended_insertion)
                    if stored2[0]:
                        success = True
                        if stored[4]:
                            match stored[4]:
                                case 1:
                                    await websocket.send(wrap_ws_formatter('204', 'deleted', f"Since session {chat_session} of user {username} exceeded {max_token_hint} characters, The former part has been deleted to save storage--your ray tracer ID is {self.traceray_id}.", 'info'))
                                case 2:
                                    await websocket.send(wrap_ws_formatter('200', 'delete_hint', f"Session {chat_session} of user {username} exceeded {warn_token_hint} characters, which will be chopped after exceeding {max_token_hint}, make backups if you want to--your ray tracer ID is {self.traceray_id}.", 'info'))
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
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Finished entire loop-{self.traceray_id}:{session['username']}")
            else:
                success = True
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Finished non-recording loop-{self.traceray_id}:{session['username']}")
            await websocket.send(wrap_ws_formatter('202', 'loop_finished', f"An entire communication loop has finished, reentering loop gracefully--your ray tracer ID is {self.traceray_id}.", 'info'))
        except websockets.exceptions.WebSocketException:
            print("Someone disconnected")
            raise Exception('Force closure of connection')
        except Exception as excepted:
            #traceback.print_exc()
            response_str = f"Core model failed to respond, refer to administrator--your ray tracer ID is {self.traceray_id}. This can be a severe problem thats breaks your session savefile, stopping entire session."
            print(f"出现如下异常29-{self.traceray_id}:{excepted}")
            await websocket.send(wrap_ws_formatter('500', 'respond_failed', response_str, 'error'))
            await websocket.close(1000, 'Stopping connection due to critical server failure')



#异步标记程序, 不是必要的. 万一要用呢?

def callback_func_switch(future):
    print(f'!Stage2 passed abnormally!')

def callback_check_permit(future):
    print(f'Stage1 passed:\n{future.result()}')
    
#主要线程驱动器

async def main_logic(websocket, test):
    try:
        global online_list
        locked = False
        loop = asyncio.get_event_loop()
        thread_instance = ws_threading_instance(websocket, test=test)

        permit = await thread_instance.check_permit()

        if not isinstance(permit, tuple) or not permit[0]:
            raise Exception('Security exception occured')
        else:
            online_list.append(permit[2])
            print(f"Locking session for {permit[2]} as {permit[3]}")

        await thread_instance.function_switch()

    except Exception as excepted:
        print(f'Exception: {excepted}. Likely connection loss.')
    finally:
        try:
            online_list.remove(permit[2])
            print(f"Lock released for {permit[2]} as {permit[3]}")
        except:
            print('No lock to release')
        await websocket.close()
        await websocket.wait_closed()
        print('Destroying connection')


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
        print(f"First time confirm--model type is {model_type}")
        test = False
    except:
        print(f"Model deployment cannot be reached--running in test mode")
        test = True
    return client1, client2, test

def run_ws():
    global online_list, sock1, sock2
    online_list = []

    sock1, sock2, test = asyncio.run(prepare_thread())
    print('Server started!')

    new_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(new_loop)

    start_server = websockets.serve(functools.partial(main_logic, test=test), '0.0.0.0', 5000)
    try:
        asyncio.get_event_loop().run_until_complete(start_server)
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        print("Server stopped!")


if __name__ == '__main__':
    run_ws()