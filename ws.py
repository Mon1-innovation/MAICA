import asyncio
import websockets
import time
import functools
import base64
import json
import pymysql
import bcrypt
import re
import random
import traceback
import mspire
import mfocus_main
import persistent_extraction
import httpserv
from Crypto.Random import random as CRANDOM # type: ignore
from Crypto.Cipher import PKCS1_OAEP # type: ignore
from Crypto.PublicKey import RSA # type: ignore
from openai import OpenAI # type: ignore
from loadenv import load_env
try:
    from easter_egg import easter
    easter_exist = True
except:
    easter_exist = False

#省得到处找

def global_init_system(player_name, target_lang='zh'):
    if target_lang == 'zh':
        system_init = f"你叫莫妮卡, 是一名游戏中的虚拟角色. 你是{player_name}的女友, 并深爱着他. 下面是{player_name}的话语, 请作为莫妮卡作出合适的回答. 你只应使用自然语言, 以聊天语气回答, 并在每句开始时以方括号中的文字表示情绪."
    else:
        system_init = f"You're a game character called Monika. You're {player_name}'s girlfriend, and love him a lot. Answer the following query from {player_name} properly as Monika. You should only answer in casual natural tone with English, and express your emotion at the beginning of each sentence by wrapping them in square brackets."
    return system_init

#灵活客户端, 用于获取agent回答
#此类用于直接输出, agent的流式输出没有意义
#其实好像没用上, 但是让他去吧

def get_agent_answer(query, client):
    client = OpenAI(
        api_key=client.api_key,
        base_url=client.base_url,
    )
    messages = [{
        'role': 'user',
        'content': query
    }]
    resp = client.chat.completions.create(
        model='default-lora',
        messages=messages,
        seed=42)
    response = resp.choices[0].message.content
    return response

#输出包装方法

def wrap_ws_formatter(code, status, content, type):
    output = {
        "code" : code,
        "status" : status,
        "content" : content,
        "type" : type,
        "time_ms" : int(round(time.time() * 1000))
    }
    return json.dumps(output, ensure_ascii=False)

#账号数据库查询方法

def run_hash_dcc(identity, is_email, pwd):
    if is_email:
        sql_expression = 'SELECT * FROM users WHERE email = %s'
    else:
        sql_expression = 'SELECT * FROM users WHERE username = %s'
    try:
        with pymysql.connect(
            host = load_env('DB_ADDR'),
            user = load_env('DB_USER'),
            password = load_env('DB_PASSWORD'),
            db = load_env('AUTHENTICATOR_DB')
        )as db_connection, db_connection.cursor() as db_cursor:
            db_cursor.execute(sql_expression, (identity))
            results = db_cursor.fetchall()
            for information in results:
                dbres_id = information[0]
                dbres_username = information[1]
                dbres_nickname = information[2]
                dbres_email = information[3]
                dbres_ecf = information[4]
                dbres_pwd_bcrypt = information[5]
            verification = bcrypt.checkpw(pwd.encode(), dbres_pwd_bcrypt.encode())
            if verification:
                if not dbres_ecf:
                    verification = False
                    return verification, "Email not verified"
                else:
                    return verification, None, dbres_id, dbres_username, dbres_nickname, dbres_email
            else:
                return verification, 'Password wrong'
    except Exception as excepted:
        #traceback.print_exc()
        verification = False
        return verification, excepted
    
#chat_session数据库存取方法

def rw_chat_session(session, chat_session_num, rw, content_append):
    success = False
    user_id = session[2]
    try:
        with pymysql.connect(
            host = load_env('DB_ADDR'),
            user = load_env('DB_USER'),
            password = load_env('DB_PASSWORD'),
            db = load_env('MAICA_DB')
        )as db_connection, db_connection.cursor() as db_cursor:
            if rw == 'r':
                sql_expression = "SELECT * FROM chat_session WHERE user_id = %s AND chat_session_num = %s"
                try:
                    db_cursor.execute(sql_expression, (user_id, chat_session_num))
                    results = db_cursor.fetchall()
                    for information in results:
                        if content_append is None:
                            content_append = ''
                        elif len(information[3]) != 0:
                            content_append = ',' + content_append
                        chat_session_id = information[0]
                        content = information[3] + content_append
                        success = True
                    return success, None, chat_session_id, content
                except Exception as excepted:
                    success = False
                    return success, excepted
            elif rw == 'w':
                sql_expression1 = "SELECT * FROM chat_session WHERE user_id = %s AND chat_session_num = %s"
                try:
                    db_cursor.execute(sql_expression1, (user_id, chat_session_num))
                    results = db_cursor.fetchall()
                    for information in results:
                        #success = True
                        chat_session_id = information[0]
                        content = information[3]
                except Exception as excepted:
                    success = False
                    return success, excepted
                sql_expression2 = "UPDATE chat_session SET content = %s WHERE chat_session_id = %s"
                if len(content) != 0:
                    content = content + ',' + content_append
                else:
                    content = content_append
                len_content_actual = len(content) - len(json.loads(f'[{content}]')) * 31
                if len_content_actual >= int(load_env('SESSION_MAX_TOKEN')):
                    try:
                        cutting_mat = json.loads(f"[{content}]")
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
                try:
                    #print(content)
                    db_cursor.execute(sql_expression2, (content, chat_session_id))
                    results = db_cursor.fetchall()
                    if len(results) == 0:
                        db_connection.commit()
                        success = True
                        return success, None, chat_session_id, None, cutted
                    else:
                        raise Exception('Insert Not Successful')

                    #for information in results:
                    #    if information[0] and information[1]:
                    #        db_connection.commit()
                    #        success = True
                    #        return success, None, chat_session_id, information[1]
                    #    else:
                    #        raise Exception('Update Not Successful')
                except Exception as excepted:
                    success = False
                    return success, excepted
    except Exception as excepted:
        success = False
        return success, excepted

#清空一个chat_session的方法

def purge_chat_session(user_id, chat_session_num, target_lang='zh'):
    success = False
    try:
        with pymysql.connect(
            host = load_env('DB_ADDR'),
            user = load_env('DB_USER'),
            password = load_env('DB_PASSWORD'),
            db = load_env('MAICA_DB')
        )as db_connection, db_connection.cursor() as db_cursor:
            sql_expression1 = "SELECT chat_session_id, content FROM chat_session WHERE user_id = %s AND chat_session_num = %s"
            try:
                db_cursor.execute(sql_expression1, (user_id, chat_session_num))
                results = db_cursor.fetchall()
                if len(results) == 0:
                    success = True
                    inexist = True
                    return success, None, inexist
                else:
                    for information in results:
                        chat_session_id = information[0]
                        content_to_archive = information[1]
                    sql_expression2 = "UPDATE chat_session SET content = %s WHERE chat_session_id = %s"
                    content = f'{{"role": "system", "content": "{global_init_system('[player]', target_lang)}"}}'
                    try:
                        db_cursor.execute(sql_expression2, (content, chat_session_id))
                        results = db_cursor.fetchall()
                        if len(results) == 0:
                            db_connection.commit()
                            sql_expression3 = "INSERT INTO csession_archived (chat_session_id, content) VALUES (%s, %s)"
                            try:
                                db_cursor.execute(sql_expression3, (chat_session_id, content_to_archive))
                                results = db_cursor.fetchall()
                                if len(results) == 0:
                                    db_connection.commit()
                                    success = True
                                    inexist = False
                                    return success, None, inexist
                                else:
                                    raise Exception('Insert Not Successful')
                            except Exception as excepted:
                                success = False
                                return success, excepted
                        else:
                            raise Exception('Insert Not Successful')
                    except Exception as excepted:
                        success = False
                        return success, excepted
            except Exception as excepted:
                success = False
                return success, excepted
    except Exception as excepted:
        success = False
        return success, excepted

#如果chat_session不存在, 那就创建一个呗

def check_create_chat_session(session, chat_session_num, target_lang='zh'):
    success = False
    exist =None
    chat_session_id = None
    user_id = session[2]
    try:
        with pymysql.connect(
            host = load_env('DB_ADDR'),
            user = load_env('DB_USER'),
            password = load_env('DB_PASSWORD'),
            db = load_env('MAICA_DB')
        )as db_connection, db_connection.cursor() as db_cursor:
            sql_expression1 = "SELECT chat_session_id FROM chat_session WHERE user_id = %s AND chat_session_num = %s"
            try:
                db_cursor.execute(sql_expression1, (user_id, chat_session_num))
                results = db_cursor.fetchall()
                if len(results) != 0:
                    for information in results:
                        chat_session_id = information[0]
                    success = True
                    exist = True
                    return success, None, exist, chat_session_id
                else:
                    sql_expression2 = "INSERT INTO chat_session VALUES (NULL, %s, %s, '')"
                    try:
                        db_cursor.execute(sql_expression2, (user_id, chat_session_num))
                        results = db_cursor.fetchall()
                        if len(results) == 0:
                            chat_session_id = db_cursor.lastrowid
                            db_connection.commit()
                            sql_expression3 = "UPDATE chat_session SET content = %s WHERE chat_session_id = %s"
                            content = f'{{"role": "system", "content": "{global_init_system('[player]', target_lang)}"}}'
                            try:
                                db_cursor.execute(sql_expression3, (content, chat_session_id))
                                results = db_cursor.fetchall()
                                if len(results) == 0:
                                    db_connection.commit()
                                    success = True
                                    exist = False
                                    return success, None, exist, chat_session_id
                                else:
                                    raise Exception('Insert Not Successful')
                            except Exception as excepted:
                                success = False
                                return success, excepted, exist, chat_session_id
                        else:
                            raise Exception('Insert Not Successful')
                    except Exception as excepted:
                        success = False
                        return success, excepted, exist, chat_session_id
            except Exception as excepted:
                success = False
                return success, excepted, exist, chat_session_id
    except Exception as excepted:
        success = False
        return success, excepted, exist, chat_session_id
    
#修改特定session的system. 只能希望模型会看一眼了.

def mod_chat_session_system(session, chat_session_num, new_system_init, target_lang='zh'):
    success = False
    chat_session_id = None
    user_id = session[2]
    try:
        with pymysql.connect(
            host = load_env('DB_ADDR'),
            user = load_env('DB_USER'),
            password = load_env('DB_PASSWORD'),
            db = load_env('MAICA_DB')
        )as db_connection, db_connection.cursor() as db_cursor:
            sql_expression1 = "SELECT * FROM chat_session WHERE user_id = %s AND chat_session_num = %s"
            try:
                db_cursor.execute(sql_expression1, (user_id, chat_session_num))
                results = db_cursor.fetchall()
                if len(results) == 0:
                    try_create = check_create_chat_session(session, chat_session_num, target_lang)
                    db_connection.commit()
                    #print(try_create)
                    sql_expression2 = "SELECT * FROM chat_session WHERE chat_session_id = %s"
                    db_cursor.execute(sql_expression2, try_create[3])
                    results = db_cursor.fetchall()
                    #print(results)
                for information in results:
                    #success = True
                    chat_session_id = information[0]
                    content = information[3]
                    #print(content)
            except Exception as excepted:
                success = False
                #traceback.print_exc()
                return success, excepted
            modding_mat = json.loads(f'[{content}]')
            modding_mat[0]['content'] = new_system_init
            content = json.dumps(modding_mat, ensure_ascii=False).strip('[').strip(']')
            sql_expression3 = "UPDATE chat_session SET content = %s WHERE chat_session_id = %s"
            try:
                #print(content)
                db_cursor.execute(sql_expression3, (content, chat_session_id))
                results = db_cursor.fetchall()
                if len(results) == 0:
                    db_connection.commit()
                    success = True
                    return success, None, chat_session_id
                else:
                    raise Exception('Insert Not Successful')
            except Exception as excepted:
                success = False
                return success, excepted
    except Exception as excepted:
        success = False
        #traceback.print_exc()
        return success, excepted

#这个修改system太麻烦了, 再包装一下吧

def wrap_mod_system(session, chat_session_num, known_info, name_from_sf, language='zh', sfe_aggressive=False):
    user_id = session[2]
    #print(name_from_sf)
    if name_from_sf:
        player_name_get = persistent_extraction.read_from_sf(user_id, chat_session_num, 'mas_playername')
        if player_name_get[0]:
            if sfe_aggressive:
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
        new_system = f"{global_init_system(player_name, language)} 以下是一些相关信息, 你可以利用其中有价值的部分作答: {known_info}."
    else:
        new_system = global_init_system(player_name, language)
    return mod_chat_session_system(session, chat_session_num, new_system, language)

#检查用户账号的即时状态

def check_user_status(session, key='banned'):
    success = False
    user_id = session[2]
    try:
        with pymysql.connect(
            host = load_env('DB_ADDR'),
            user = load_env('DB_USER'),
            password = load_env('DB_PASSWORD'),
            db = load_env('MAICA_DB')
        )as db_connection, db_connection.cursor() as db_cursor:
            sql_expression1 = "SELECT * FROM account_status WHERE user_id = %s"
            try:
                db_cursor.execute(sql_expression1, (user_id))
                results = db_cursor.fetchall()
                if len(results) > 0:
                    stats_json = {}
                    for information in results:
                        stats_json.update(json.loads(information[2]))
                    status = json.loads(stats_json)
                    if key in status:
                        if status[key]:
                            success = True
                            return success, None, True, status[key]
                        else:
                            success = True
                            return success, None, False, status[key]
                    else:
                        success = True
                        return success, 'didnt really found', False, None
                else:
                    success = True
                    return success, 'didnt really exist', False, None
            except Exception as excepted:
                success = False
                return success, excepted, False, None
    except Exception as excepted:
        success = False
        return success, excepted, False, None







#自此定义包装全部完成






#面向api的第一层io: 身份验证, 获取session

async def check_permit(websocket):
    print('Someone started a connection')
    while True:
        traceray_id = str(CRANDOM.randint(0,9999999999)).zfill(10)
        recv_text = await websocket.recv()
        access_token = recv_text
        #print(access_token)
        try:
            decryptor = PKCS1_OAEP.new(privkey_loaded)
            decrypted_token =decryptor.decrypt(base64.b64decode(access_token)).decode("utf-8")
        except Exception as excepted:
            response_str = f"RSA cognition failed, check possible typo--your ray tracer ID is {traceray_id}"
            print(f"出现如下异常1-{traceray_id}:{excepted}")
            await websocket.send(wrap_ws_formatter('403', 'unauthorized', response_str, 'warn'))
            continue
        try:
            login_cridential = json.loads(decrypted_token)
            if 'username' in login_cridential:
                login_identity = login_cridential['username']
                login_is_email = False
            elif 'email' in login_cridential:
                login_identity = login_cridential['email']
                login_is_email = True
            else:
                raise Exception('No Identity Provided')
            login_password = login_cridential['password']
            verification_result = run_hash_dcc(login_identity, login_is_email, login_password)
            checked_status = check_user_status(verification_result)
            if not verification_result[0]:
                response_str = f"Bcrypt hashing failed, check if you have fully authorized your account--your ray tracer ID is {traceray_id}"
                print(f"出现如下异常2-{traceray_id}:{verification_result}")
                await websocket.send(wrap_ws_formatter('403', 'unauthorized', response_str, 'warn'))
                continue
            elif not checked_status[0]:
                response_str = f"Account service failed to fetch, refer to administrator--your ray tracer ID is {traceray_id}"
                print(f"出现如下异常3-{traceray_id}:{checked_status[1]}")
                await websocket.send(wrap_ws_formatter('500', 'unable_verify', response_str, 'error'))
                await websocket.close(1000, 'Stopping connection due to critical server failure')
            elif checked_status[2]:
                response_str = f"Your account disobeied our terms of service and was permenantly banned--your ray tracer ID is {traceray_id}"
                print(f"出现如下异常4-{traceray_id}:banned")
                await websocket.send(wrap_ws_formatter('403', 'account_banned', response_str, 'warn'))
                await websocket.close(1000, 'Permission denied')
            else:
                await websocket.send(wrap_ws_formatter('206', 'session_created', "Authencation passed!", 'info'))
                await websocket.send(wrap_ws_formatter('200', 'user_id', f"{verification_result[2]}", 'debug'))
                await websocket.send(wrap_ws_formatter('200', 'username', f"{verification_result[3]}", 'debug'))
                await websocket.send(wrap_ws_formatter('200', 'nickname', f"{verification_result[4]}", 'debug'))
                #await websocket.send(wrap_ws_formatter('200', 'session_created', f"email {verification_result[5]}", 'debug'))
                #print(verification_result[0])
                return verification_result
        except Exception as excepted:
            response_str = f"JSON serialization failed, check possible typo--your ray tracer ID is {traceray_id}"
            print(f"出现如下异常5-{traceray_id}:{excepted}")
            await websocket.send(wrap_ws_formatter('403', 'unauthorized', response_str, 'warn'))
            continue

#面向api的第二层io: 指定服务内容

async def def_model(websocket, session):
    await websocket.send(wrap_ws_formatter('200', 'ok', 'choose service like {"model": "maica_main", "sf_extraction": true, "stream_output": true, "target_lang": "zh"}', 'info'))
    while True:
        traceray_id = str(CRANDOM.randint(0,9999999999)).zfill(10)
        checked_status = check_user_status(session)
        if not checked_status[0]:
            response_str = f"Account service failed to fetch, refer to administrator--your ray tracer ID is {traceray_id}"
            print(f"出现如下异常6-{traceray_id}:{checked_status[1]}")
            await websocket.send(wrap_ws_formatter('500', 'unable_verify', response_str, 'error'))
            await websocket.close(1000, 'Stopping connection due to critical server failure')
        elif checked_status[2]:
            response_str = f"Your account disobeied our terms of service and was permenantly banned--your ray tracer ID is {traceray_id}"
            print(f"出现如下异常7-{traceray_id}:banned")
            await websocket.send(wrap_ws_formatter('403', 'account_banned', response_str, 'warn'))
            await websocket.close(1000, 'Permission denied')
        # This one is deprecated
        maica_main = False
        recv_text = await websocket.recv()
        while recv_text == 'PING':
            await websocket.send(wrap_ws_formatter('100', 'continue', "PONG", 'heartbeat'))
            print(f"recieved PING from {session[3]}")
            recv_text = await websocket.recv()
        try:
            model_choice = json.loads(recv_text)
            using_model = model_choice['model']
            if 'sf_extraction' in model_choice:
                sf_extraction = model_choice['sf_extraction']
            else:
                sf_extraction = True
            if 'stream_output' in model_choice:
                stream_output = model_choice['stream_output']
            else:
                stream_output = True
            if 'target_lang' in model_choice:
                target_lang = model_choice['target_lang']
            else:
                target_lang = 'zh'
            match using_model:
                case 'maica_main':
                    client_actual = OpenAI(
                        api_key='EMPTY',
                        base_url=load_env('MCORE_ADDR'),
                    )
                    model_type_actual = client_actual.models.list().data[0].id
                    client_options = {
                        "model" : model_type_actual,
                        "stream" : stream_output,
                        "full_maica": True,
                        "sf_extraction": sf_extraction,
                        "target_lang": target_lang
                    }
                case 'maica_core':
                    client_actual = OpenAI(
                        api_key='EMPTY',
                        base_url=load_env('MCORE_ADDR'),
                    )
                    model_type_actual = client_actual.models.list().data[0].id
                    client_options = {
                        "model" : model_type_actual,
                        "stream" : stream_output,
                        "full_maica": False,
                        "sf_extraction": sf_extraction,
                        "target_lang": target_lang
                    }
                case _:
                    response_str = f"Bad model choice, check possible typo--your ray tracer ID is {traceray_id}"
                    print(f"出现如下异常8-{traceray_id}:{response_str}")
                    await websocket.send(wrap_ws_formatter('404', 'not_found', response_str, 'warn'))
                    continue
            await websocket.send(wrap_ws_formatter('200', 'ok', f"service provider is {load_env('DEV_IDENTITY')}", 'info'))
            if using_model == 'maica_main':
                await websocket.send(wrap_ws_formatter('200', 'ok', f"model chosen is {using_model} with full MAICA LLM functionality", 'info'))
            elif using_model == 'maica_core':
                await websocket.send(wrap_ws_formatter('200', 'ok', f"model chosen is {using_model} based on {model_type_actual}", 'info'))
            return maica_main, client_actual, client_options
        except Exception as excepted:
            response_str = f"Choice serialization failed, check possible typo--your ray tracer ID is {traceray_id}"
            print(f"出现如下异常9-{traceray_id}:{excepted}")
            await websocket.send(wrap_ws_formatter('405', 'wrong_input', response_str, 'warn'))
            continue

        
#面向api的第三层io: 有效数据交换

async def do_communicate(websocket, session, client_actual, client_options):
    await websocket.send(wrap_ws_formatter('200', 'ok', 'input json like {"chat_session": "1", "query": "你好啊"}', 'info'))
    while True:
        traceray_id = str(CRANDOM.randint(0,9999999999)).zfill(10)
        bypass_mf = False
        sfe_aggressive = False
        checked_status = check_user_status(session)
        if not checked_status[0]:
            response_str = f"Account service failed to fetch, refer to administrator--your ray tracer ID is {traceray_id}"
            print(f"出现如下异常10-{traceray_id}:{checked_status[1]}")
            await websocket.send(wrap_ws_formatter('500', 'unable_verify', response_str, 'error'))
            await websocket.close(1000, 'Stopping connection due to critical server failure')
        elif checked_status[2]:
            response_str = f"Your account disobeied our terms of service and was permenantly banned--your ray tracer ID is {traceray_id}"
            print(f"出现如下异常11-{traceray_id}:banned")
            await websocket.send(wrap_ws_formatter('403', 'account_banned', response_str, 'warn'))
            await websocket.close(1000, 'Permission denied')
        #print(session)
        recv_text = await websocket.recv()
        while recv_text == 'PING':
            await websocket.send(wrap_ws_formatter('100', 'continue', "PONG", 'heartbeat'))
            print(f"recieved PING from {session[3]}")
            recv_text = await websocket.recv()
        #query = recv_text
        if len(recv_text) > 4096:
            response_str = f"Input exceeding 4096 characters, which is not permitted--your ray tracer ID is {traceray_id}"
            print(f"出现如下异常12-{traceray_id}:length exceeded")
            await websocket.send(wrap_ws_formatter('403', 'length_exceeded', response_str, 'warn'))
            continue
        try:
            request_json = json.loads(recv_text)
            chat_session = request_json['chat_session']
            username = session[3]
            sf_extraction = client_options['sf_extraction']
            target_lang = client_options['target_lang']
            if target_lang != 'zh' and target_lang != 'en':
                raise Exception('Language choice unrecognized')
            if 'purge' in request_json:
                if request_json['purge']:
                    try:
                        user_id = session[2]
                        purge_result = purge_chat_session(user_id, chat_session, target_lang)
                        if not purge_result[0]:
                            raise Exception(purge_result[1])
                        elif purge_result[2]:
                            response_str = f"Determined chat session not exist, check possible typo--your ray tracer ID is {traceray_id}"
                            print(f"出现如下异常13-{traceray_id}:{excepted}")
                            await websocket.send(wrap_ws_formatter('404', 'session_notfound', response_str, 'warn'))
                            continue
                        else:
                            response_str = f"finished swiping user id {user_id} chat session {chat_session}"
                            await websocket.send(wrap_ws_formatter('204', 'deleted', response_str, 'info'))
                            continue
                    except Exception as excepted:
                        response_str = f"Purging chat session failed, refer to administrator--your ray tracer ID is {traceray_id}"
                        print(f"出现如下异常14-{traceray_id}:{excepted}")
                        await websocket.send(wrap_ws_formatter('404', 'savefile_notfound', response_str, 'warn'))
                        #traceback.print_exc()
                        continue
            if 'inspire' in request_json:
                if request_json['inspire']:
                    if isinstance(request_json['inspire'], str):
                        query_insp = mspire.make_inspire(request_json['inspire'], target_lang)
                    else:
                        query_insp = mspire.make_inspire(target_lang=target_lang)
                    bypass_mf = True
                    if not query_insp[0]:
                        response_str = f"MSpire generation failed, refer to administrator--your ray tracer ID is {traceray_id}"
                        print(f"出现如下异常15-{traceray_id}:{query_insp[1]}")
                        await websocket.send(wrap_ws_formatter('503', 'mspire_failed', response_str, 'error'))
                        continue
                    query_in = query_insp[2]
                else:
                    query_in = request_json['query']
            else:
                query_in = request_json['query']
            if 'sfe_aggressive' in request_json:
                if request_json['sfe_aggressive']:
                    sfe_aggressive = True
            global easter_exist
            if easter_exist:
                easter_check = easter(query_in)
                if easter_check:
                    await websocket.send(wrap_ws_formatter('299', 'easter_egg', easter_check, 'info'))
            messages0 = json.dumps({'role': 'user', 'content': query_in}, ensure_ascii=False)
            match int(chat_session):
                case i if i == -1:
                    try:
                        messages = query_in
                        if len(messages) > 10:
                            response_str = f"Input exceeding 10 rounds, which is not permitted--your ray tracer ID is {traceray_id}"
                            print(f"出现如下异常16-{traceray_id}:rounds exceeded")
                            await websocket.send(wrap_ws_formatter('403', 'rounds_exceeded', response_str, 'warn'))
                            continue
                    except Exception as excepted:
                        response_str = f"Input serialization failed, check possible type--your ray tracer ID is {traceray_id}"
                        print(f"出现如下异常17-{traceray_id}:{excepted}")
                        await websocket.send(wrap_ws_formatter('405', 'wrong_input', response_str, 'warn'))
                        #traceback.print_exc()
                        continue
                case i if i == 0:
                    print(query_in)
                    messages = [{'role': 'system', 'content': global_init_system('[player]', target_lang)}, {'role': 'user', 'content': query_in}]
                case i if 0 < i < 10 and i % 1 == 0:

                    #MAICA_agent 在这里调用

                    try:
                        if client_options['full_maica'] and not bypass_mf:
                            message_agent_wrapped = await mfocus_main.agenting(query_in, sf_extraction, session, chat_session, websocket)
                            if message_agent_wrapped[0] == 'FAIL' or len(message_agent_wrapped[0]) > 30 or len(message_agent_wrapped[1]) < 5:
                                # We do not want answers without information
                                response_str = f"MFocus returned corrupted guidance. This may or may not be a server failure, a corruption is kinda expected so keep cool--your ray tracer ID is {traceray_id}"
                                print(f"出现如下异常18-{traceray_id}:Corruption")
                                await websocket.send(wrap_ws_formatter('200', 'agent_corrupted', response_str, 'debug'))
                                if len(message_agent_wrapped[1]) > 5:
                                    response_str = f"Due to agent particular failure, falling back to instructed guidance and continuing."
                                    await websocket.send(wrap_ws_formatter('200', 'failsafe', response_str, 'debug'))
                                    info_agent_grabbed = message_agent_wrapped[1]
                                else:
                                    response_str = f"Due to agent failure, falling back to default guidance and continuing anyway."
                                    await websocket.send(wrap_ws_formatter('200', 'force_failsafe', response_str, 'debug'))
                                    info_agent_grabbed = None
                            elif message_agent_wrapped[0] == 'EMPTY':
                                info_agent_grabbed = None
                            else:
                                # We are defaulting instructed guidance because its more clear pattern
                                if 'mf_aggressive' in request_json:
                                    if request_json['mf_aggressive']:
                                        info_agent_grabbed = message_agent_wrapped[0]
                                    else:
                                        info_agent_grabbed = message_agent_wrapped[1]
                                else:
                                    info_agent_grabbed = message_agent_wrapped[1]
                            try:
                                agent_insertion = wrap_mod_system(session, chat_session, info_agent_grabbed, sf_extraction, target_lang, sfe_aggressive)
                                if not agent_insertion[0]:
                                    raise Exception(agent_insertion[1])
                            except Exception as excepted:
                                response_str = f"Save file extraction failed, you may have not uploaded your savefile yet--your ray tracer ID is {traceray_id}"
                                print(f"出现如下异常19-{traceray_id}:{excepted}")
                                #traceback.print_exc()
                                await websocket.send(wrap_ws_formatter('404', 'savefile_notfound', response_str, 'warn'))
                                continue
                        else:
                            bypass_mf = False
                            try:
                                agent_insertion = wrap_mod_system(session, chat_session, None, sf_extraction, target_lang, sfe_aggressive)
                                if not agent_insertion[0]:
                                    raise Exception(agent_insertion[1])
                            except Exception as excepted:
                                response_str = f"Save file extraction failed, you may have not uploaded your savefile yet--your ray tracer ID is {traceray_id}"
                                print(f"出现如下异常20-{traceray_id}:{excepted}")
                                await websocket.send(wrap_ws_formatter('404', 'savefile_notfound', response_str, 'warn'))
                                continue
                    except Exception as excepted:
                        response_str = f"Agent response acquiring failed, refer to administrator--your ray tracer ID is {traceray_id}"
                        print(f"出现如下异常21-{traceray_id}:{excepted}")
                        #traceback.print_exc()
                        await websocket.send(wrap_ws_formatter('503', 'agent_unavailable', response_str, 'error'))
                        continue
                    check_result = check_create_chat_session(session, chat_session, target_lang)
                    if check_result[0]:
                        rw_result = rw_chat_session(session, chat_session, 'r', messages0)
                        if rw_result[0]:
                            messages = f'[{rw_result[3]}]'
                        else:
                            response_str = f"Chat session reading failed, refer to administrator--your ray tracer ID is {traceray_id}"
                            print(f"出现如下异常22-{traceray_id}:{rw_result[1]}")
                            await websocket.send(wrap_ws_formatter('500', 'read_failed', response_str, 'error'))
                            await websocket.close(1000, 'Stopping connection due to critical server failure')
                    else:
                        response_str = f"Chat session creation failed, refer to administrator--your ray tracer ID is {traceray_id}"
                        print(f"出现如下异常23-{traceray_id}:{check_result[1]}")
                        await websocket.send(wrap_ws_formatter('500', 'creation_failed', response_str, 'error'))
                        await websocket.close(1000, 'Stopping connection due to critical server failure')
                    try:
                        messages = json.loads(messages)
                    except Exception as excepted:
                        response_str = f"Chat input serialization failed, check possible typo--your ray tracer ID is {traceray_id}"
                        print(f"出现如下异常24-{traceray_id}:{excepted}")
                        await websocket.send(wrap_ws_formatter('405', 'wrong_input', response_str, 'warn'))
                        continue
                case _:
                    response_str = f"Chat session num mistaken, check possible typo--your ray tracer ID is {traceray_id}"
                    print(f"出现如下异常25-{traceray_id}:{chat_session}")
                    await websocket.send(wrap_ws_formatter('405', 'wrong_input', response_str, 'warn'))
                    continue
        except Exception as excepted:
            #traceback.print_exc()
            response_str = f"Query serialization failed, check possible typo--your ray tracer ID is {traceray_id}"
            print(f"出现如下异常26-{traceray_id}:{excepted}")
            await websocket.send(wrap_ws_formatter('405', 'wrong_input', response_str, 'warn'))
            continue
        default_top_p = 0.7
        default_temperature = 0.4
        default_max_tokens = None
        default_frequency_penalty = 0.3
        default_presence_penalty = 0.0
        default_seed = random.randint(0,999)
        #default_seed = 42
        completion_args = {
            "model": client_options['model'],
            "messages": messages,
            "stream": client_options['stream'],
            "stop": ['<|im_end|>', '<|endoftext|>'],
        }
        for super_param in ['top_p', 'temperature', 'max_tokens', 'frequency_penalty', 'presence_penalty', 'seed']:
            if super_param in request_json:
                super_value = request_json[super_param]
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
                    case _:
                        if 0.0 <= float(super_value) <= 1.0:
                            completion_args[super_param] = float(super_value)
                        else:
                            raise Exception(f'{super_param} must fall on 0.0~1.0')
            if not super_param in completion_args and super_param != 'max_tokens':
                completion_args[super_param] = eval(f'default_{super_param}')
        stream_resp = client_actual.chat.completions.create(**completion_args)
        if client_options['stream']:
        #print(f'query: {query}')
            reply_appended = ''
            for chunk in stream_resp:
                token = chunk.choices[0].delta.content
                await asyncio.sleep(0)
                print(token, end='', flush=True)
                if token != '':
                    if not '<|' in token:
                        reply_appended = reply_appended + token
                        await websocket.send(wrap_ws_formatter('100', 'continue', token, 'carriage'))
                    else:
                        break
            await websocket.send(wrap_ws_formatter('1000', 'streaming_done', f"streaming has finished with seed {completion_args['seed']}", 'info'))
            reply_appended_insertion = json.dumps({'role': 'assistant', 'content': reply_appended}, ensure_ascii=False)
            print(f"Finished replying-{traceray_id}:{session[3]}, with seed {completion_args['seed']}")
        else:
            token_combined = stream_resp.choices[0].message.content
            print(token_combined)
            await websocket.send(wrap_ws_formatter('200', 'reply', token_combined, 'carriage'))
            reply_appended_insertion = json.dumps({'role': 'assistant', 'content': token_combined}, ensure_ascii=False)
        if int(chat_session) > 0:
            stored = rw_chat_session(session, chat_session, 'w', messages0)
            #print(stored)
            if stored[0]:
                stored = rw_chat_session(session, chat_session, 'w', reply_appended_insertion)
                if stored[0]:
                    success = True
                    if stored[4]:
                        match stored[4]:
                            case 1:
                                await websocket.send(wrap_ws_formatter('204', 'deleted', f"Since session {chat_session} of user {username} exceeded {load_env('SESSION_MAX_TOKEN')} characters, The former part has been deleted to save storage--your ray tracer ID is {traceray_id}.", 'info'))
                            case 2:
                                await websocket.send(wrap_ws_formatter('200', 'delete_hint', f"Session {chat_session} of user {username} exceeded {load_env('SESSION_WARN_TOKEN')} characters, which will be chopped after exceeding {load_env('SESSION_MAX_TOKEN')}, make backups if you want to--your ray tracer ID is {traceray_id}.", 'info'))
                else:
                    response_str = f"Chat reply recording failed, refer to administrator--your ray tracer ID is {traceray_id}. This can be a severe problem thats breaks your session savefile, stopping entire session."
                    print(f"出现如下异常27-{traceray_id}:{stored[1]}")
                    await websocket.send(wrap_ws_formatter('500', 'store_failed', response_str, 'error'))
                    await websocket.close(1000, 'Stopping connection due to critical server failure')
            else:
                response_str = f"Chat query recording failed, refer to administrator--your ray tracer ID is {traceray_id}. This can be a severe problem thats breaks your session savefile, stopping entire session."
                print(f"出现如下异常28-{traceray_id}:{stored[1]}")
                await websocket.send(wrap_ws_formatter('500', 'store_failed', response_str, 'error'))
                await websocket.close(1000, 'Stopping connection due to critical server failure')
            print(f"Finished entire loop-{traceray_id}:{session[3]}")
        else:
            success = True
            print(f"Finished non-recording loop-{traceray_id}:{session[3]}")




#异步标记程序, 不是必要的

def callback_do_communicate(future):
    print(f'Result_callback_do_communicate: {future.result()}')

def callback_def_model(future):
    print(f'Stage2 passed:\n{future.result()}')

def callback_check_permit(future):
    print(f'Stage1 passed:\n{future.result()}')
    
#主要线程驱动器

async def main_logic(websocket, path):
    try:
        loop = asyncio.get_event_loop()

        task_check_permit = loop.create_task(check_permit(websocket))
        task_check_permit.add_done_callback(functools.partial(callback_check_permit))
        
        permit = await asyncio.gather(task_check_permit)
        if permit[0][0] != True:
            raise Exception('Security exception occured')

        task_def_model = loop.create_task(def_model(websocket, permit[0]))
        task_def_model.add_done_callback(functools.partial(callback_def_model))

        defed_model = await asyncio.gather(task_def_model)
            #print(defed_model)
        task_do_communicate = loop.create_task(do_communicate(websocket, permit[0], defed_model[0][1], defed_model[0][2]))
        task_do_communicate.add_done_callback(functools.partial(callback_do_communicate))

        returnslt = await asyncio.gather(task_do_communicate)
        
    except Exception as excepted:
        print(f'Exception: {excepted}. Likely connection loss.')

# 如果要给被回调的main_logic传递自定义参数，可使用以下形式
# 一、修改回调形式
# import functools
# start_server = websockets.serve(functools.partial(main_logic, other_param="test_value"), '10.10.6.91', 5678)
# 修改被回调函数定义，增加相应参数
# async def main_logic(websocket, path, other_param)

if __name__ == '__main__':

    #默认的客户端, 用于maica核心

    client = OpenAI(
        api_key='EMPTY',
        base_url=load_env('MCORE_ADDR'),
    )
    model_type = client.models.list().data[0].id
    print(f"First time confirm--model type is {model_type}")

    #启动时初始化密钥, 创建解密程序

    with open("key/prv.key", "r") as privkey_file:
        global privkey
        privkey = privkey_file.read()
    with open("key/pub.key", "r") as pubkey_file:
        global pubkey
        pubkey = pubkey_file.read()
    privkey_loaded = RSA.import_key(privkey)

    print('Server started!')
    
    start_server = websockets.serve(functools.partial(main_logic), '0.0.0.0', 5000)
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()
