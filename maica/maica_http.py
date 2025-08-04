if __name__ == '__main__':
    from gevent import monkey
    monkey.patch_all()
from quart import Quart, request
import os
import asyncio
import json
import base64
import functools
import traceback
import aiosqlite
import maica_ws
from hypercorn.config import Config
from hypercorn.asyncio import serve
# from gevent import pywsgi
# from waitress import serve
# from paste.translogger import TransLogger
# from gunicorn.app.wsgiapp import WSGIApplication
from Crypto.Random import random as CRANDOM
from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_PSS
from Crypto.Hash import SHA256
from maica_utils import *

app = Quart(import_name=__name__)

@app.route('/savefile', methods=["POST"])
async def save_upload():
    global decryptor
    success = True
    exception = ''
    try:
        data = json.loads(await request.data)
        access_token = data['access_token']
        chat_session = data['chat_session']
        content = data['content']
        print(access_token)
        if int(chat_session) < 1 or int(chat_session) > 9:
            raise Exception('Chat session out of range')
        hduplex_instance = maica_ws.sub_threading_instance()
        verification_result = await wrap_verify_token(access_token, hduplex_instance)
        if verification_result:
            if len(str(content)) < 100000:
                try:
                    content_text = json.dumps(content, ensure_ascii=False)
                    sql_expression1 = 'SELECT persistent_id FROM persistents WHERE user_id = %s AND chat_session_num = %s'
                    result = await hduplex_instance.send_query(sql_expression1, (hduplex_instance.options['vfc']['user_id'], chat_session))
                    if result:
                        pers_id = result[0]
                        sql_expression2 = 'UPDATE persistents SET content = %s WHERE persistent_id = %s'
                        await hduplex_instance.send_modify(sql_expression2, (content_text, pers_id))
                    else:
                        sql_expression2 = 'INSERT INTO persistents (user_id, chat_session_num, content) VALUES (%s, %s, %s)'
                        await hduplex_instance.send_modify(sql_expression2, (hduplex_instance.options['vfc']['user_id'], chat_session, content_text))
                except:
                    raise Exception('Database writing failed')
            else:
                raise Exception('Content length exceeded')
        return json.dumps({"success": success, "exception": str(exception)}, ensure_ascii=False)
    except Exception as excepted:
        #traceback.print_exc()
        print('This one has failed')
        success = False
        exception = excepted
        return json.dumps({"success": success, "exception": str(exception)}, ensure_ascii=False)
    finally:
        try:
            await hduplex_instance._close_pools()
        except:
            pass

@app.route('/trigger', methods=["POST"])
async def trigger_upload():
    global decryptor
    success = True
    exception = ''
    try:
        data = json.loads(await request.data)
        access_token = data['access_token']
        chat_session = data['chat_session']
        content = data['content']
        print(access_token)
        if int(chat_session) < 1 or int(chat_session) > 9:
            raise Exception('Chat session out of range')
        hduplex_instance = maica_ws.sub_threading_instance()
        verification_result = await wrap_verify_token(access_token, hduplex_instance)
        if verification_result:
            if len(str(content)) < 100000:
                try:
                    content_text = json.dumps(content, ensure_ascii=False)
                    sql_expression1 = 'SELECT trigger_id FROM triggers WHERE user_id = %s AND chat_session_num = %s'
                    result = await hduplex_instance.send_query(sql_expression1, (hduplex_instance.options['vfc']['user_id'], chat_session))
                    if result:
                        trgs_id = result[0]
                        sql_expression2 = 'UPDATE triggers SET content = %s WHERE trigger_id = %s'
                        await hduplex_instance.send_modify(sql_expression2, (content_text, trgs_id))
                    else:
                        sql_expression2 = 'INSERT INTO triggers (user_id, chat_session_num, content) VALUES (%s, %s, %s)'
                        await hduplex_instance.send_modify(sql_expression2, (hduplex_instance.options['vfc']['user_id'], chat_session, content_text))
                except:
                    raise Exception('Database writing failed')
            else:
                raise Exception('Content length exceeded')
        return json.dumps({"success": success, "exception": str(exception)}, ensure_ascii=False)
    except Exception as excepted:
        #traceback.print_exc()
        print('This one has failed')
        success = False
        exception = excepted
        return json.dumps({"success": success, "exception": str(exception)}, ensure_ascii=False)
    finally:
        try:
            await hduplex_instance._close_pools()
        except:
            pass

@app.route('/history', methods=["POST"])
async def history_download():
    global decryptor, signer
    success = True
    exception = ''
    try:
        data = json.loads(await request.data)
        access_token = data['access_token']
        chat_session = data['chat_session']
        rounds = data['rounds']
        print(access_token)
        if int(chat_session) < 1 or int(chat_session) > 9:
            raise Exception('Chat session out of range')
        hduplex_instance = maica_ws.sub_threading_instance()
        verification_result = await wrap_verify_token(access_token, hduplex_instance)
        if verification_result:
            session = verification_result
            hisjson = await hduplex_instance.rw_chat_session(chat_session, 'r', None)
            print(hisjson)
            if hisjson[0]:
                hisjson = json.loads(f"[{hisjson[3]}]")
            else:
                raise Exception('History reading failed')
            hislen = len(hisjson)
            if abs(2*int(rounds))+1 >= hislen:
                hisfine = hisjson
            else:
                match int(rounds):
                    case i if i > 0:
                        hisfine = hisjson[:2*i+1]
                    case i if i < 0:
                        hisfine = [hisjson[0]].extend(hisjson[2*i:])
                    case _:
                        hisfine = hisjson
            hisstr = json.dumps(hisfine, ensure_ascii=False)
            sigb64 = await wrap_run_in_exc(None, sign_message, hisstr)
            hisfinal = [sigb64, hisfine]
        return json.dumps({"success": success, "exception": str(exception), "history": hisfinal}, ensure_ascii=False)
    except Exception as excepted:
        #traceback.print_exc()
        print('This one has failed')
        success = False
        exception = excepted
        return json.dumps({"success": success, "exception": str(exception)}, ensure_ascii=False)
    finally:
        try:
            await hduplex_instance._close_pools()
        except:
            pass

@app.route('/restore', methods=["POST"])
async def history_restore():
    global decryptor, verifier
    success = True
    exception = ''
    try:
        data = json.loads(await request.data)
        access_token = data['access_token']
        chat_session = data['chat_session']
        print(access_token)
        if int(chat_session) < 1 or int(chat_session) > 9:
            raise Exception('Chat session out of range')
        hduplex_instance = maica_ws.sub_threading_instance()
        verification_result = await wrap_verify_token(access_token, hduplex_instance)
        if verification_result:
            sigb64, to_verify = data['history']
            to_verify = await wrap_run_in_exc(None, seri_message, to_verify)
            vfresult = await wrap_run_in_exc(None, veri_message, json.dumps(to_verify, ensure_ascii=False), sigb64)
            if vfresult:
                await hduplex_instance.restore_chat_session(chat_session, to_verify)
            else:
                raise Exception('Signature verification failed')
        return json.dumps({"success": success, "exception": str(exception)}, ensure_ascii=False)
    except Exception as excepted:
        #traceback.print_exc()
        print('This one has failed')
        success = False
        exception = excepted
        return json.dumps({"success": success, "exception": str(exception)}, ensure_ascii=False)
    finally:
        try:
            await hduplex_instance._close_pools()
        except:
            pass

@app.route('/preferences', methods=["POST"])
async def sl_prefs():
    global decryptor
    success = True
    exception = ''
    try:
        data = json.loads(await request.data)
        access_token = data['access_token']
        print(access_token)
        hduplex_instance = maica_ws.sub_threading_instance()
        verification_result = await wrap_verify_token(access_token, hduplex_instance)
        if verification_result:
            overall_prefs = await hduplex_instance.check_user_preferences(key=False)
            user_prof_exist, prefs_old = overall_prefs[2], overall_prefs[3]
            if not prefs_old:
                prefs_old = {}
            if 'read' in data and data['read']:
                prefs_str = json.dumps(prefs_old, ensure_ascii=False)
                return json.dumps({"success": success, "exception": str(exception), "preferences": prefs_old}, ensure_ascii=False)
            if 'purge' in data and data['purge']:
                prefs_old = {}
            else:
                if 'write' in data and data['write']:
                    prefs_new = data['write']
                    prefs_old.update(prefs_new)
                if 'delete' in data and data['delete']:
                    for popper in data['delete']:
                        prefs_old.pop(popper, None)
            prefs_str = json.dumps(prefs_old, ensure_ascii=False)
            if len(prefs_str) < 100000:
                await hduplex_instance.write_user_preferences(prefs_old, enforce=True)
            else:
                raise Exception('Content length exceeded')
        return json.dumps({"success": success, "exception": str(exception)}, ensure_ascii=False)
    except Exception as excepted:
        #traceback.print_exc()
        print('This one has failed')
        success = False
        exception = excepted
        return json.dumps({"success": success, "exception": str(exception)}, ensure_ascii=False)
    finally:
        try:
            await hduplex_instance._close_pools()
        except:
            pass

@app.route('/register', methods=["POST"])
async def register():
    global encryptor
    success = True
    exception = ''
    try:
        data = json.loads(await request.data)
        if 'username' in data:
            type_usr = 'username'
            cridential = data['username']
        elif 'email' in data:
            type_usr = 'email'
            cridential = data['email']
        else:
            success = False
            exception = "No user cridential provided"
            return json.dumps({"success": success, "exception": str(exception)}, ensure_ascii=False)
        password = data['password']
        token_raw = json.dumps({type_usr: cridential, "password": password}, ensure_ascii=False).encode("utf-8")
        exec_encrypted_token = await maica_ws.wrap_run_in_exc(None, encryptor.encrypt, token_raw)
        exec_base64ed_token = await maica_ws.wrap_run_in_exc(None, base64.b64encode, exec_encrypted_token)
        encrypted_token = exec_base64ed_token.decode("utf-8")
        return json.dumps({"success": success, "exception": str(exception), "token": encrypted_token}, ensure_ascii=False)
    except Exception as excepted:
        print('This one has failed')
        success = False
        exception = excepted
        return json.dumps({"success": success, "exception": str(exception)}, ensure_ascii=False)

@app.route('/legality', methods=["POST"])
async def legal():
    global decryptor
    success = True
    exception = ''
    try:
        data = json.loads(await request.data)
        access_token = data['access_token']
        print(access_token)
        exec_unbase64_token = await maica_ws.wrap_run_in_exc(None, base64.b64decode, access_token)
        exec_decrypted_token = await maica_ws.wrap_run_in_exc(None, decryptor.decrypt, exec_unbase64_token)
        decrypted_token = exec_decrypted_token.decode("utf-8")
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
        hduplex_instance = maica_ws.sub_threading_instance()
        verification_result = await hduplex_instance.run_hash_dcc(login_identity, login_is_email, login_password)
        if verification_result[0]:
            checked_status = await hduplex_instance.check_user_status('banned')
            if not checked_status[0]:
                success = False
                exception = f"Account service failed to fetch, refer to administrator"
            elif checked_status[3]:
                success = False
                exception = f"Your account disobeied our terms of service and was permenantly banned"
        else:
            success = False
            if isinstance(verification_result[1], dict):
                if 'f2b' in verification_result[1]:
                    exception = f"Fail2Ban locking {verification_result[1]['f2b']} seconds before release"
                elif 'necf' in verification_result[1]:
                    exception = f"Your account Email not confirmed, check inbox and retry"
                elif 'pwdw' in verification_result[1]:
                    exception = f"Bcrypt hashing failed {verification_result[1]['pwdw']} times, check your password"
            else:
                exception = f"Caught a serialization failure in hashing section, check possible typo"
        if success:
            return json.dumps({"success": success, "exception": str(exception), "id": verification_result[2]})
        else:
            return json.dumps({"success": success, "exception": str(exception)})
    except Exception as excepted:
        #traceback.print_exc()
        print('This one has failed')
        success = False
        exception = excepted
        return json.dumps({"success": success, "exception": str(exception)}, ensure_ascii=False)
    finally:
        try:
            await hduplex_instance._close_pools()
        except:
            pass

@app.route('/servers', methods=["POST"])
async def nameserv():
    global known_servers
    success = True
    exception = ''
    return json.dumps({"success": success, "exception": str(exception), "servers": known_servers}, ensure_ascii=False)

@app.route('/accessibility', methods=["POST"])
async def access():
    success = True
    exception = ''
    accessibility = load_env('DEV_STATUS')
    return json.dumps({"success": success, "exception": str(exception), "accessibility": accessibility}, ensure_ascii=False)

@app.route('/version', methods=["POST"])
async def vcontrol():
    success = True
    exception = ''
    cur_v, last_v = load_env('VERSION_CONTROL').split(';',1)
    return json.dumps({"success": success, "exception": str(exception), "version": {"curr_version": cur_v, "legc_version": last_v}}, ensure_ascii=False)

@app.route('/workload', methods=["POST"])
async def gpuload():
    success = True
    exception = ''
    overall_info = {}
    if not os.path.exists('./.nvsw.db'):
        success = False
        exception = 'Exporter nvsw offline'
        return json.dumps({"success": success, "exception": str(exception)})
    try:
        async with aiosqlite.connect('./.nvsw.db') as db_client:
            for table_name in [load_env('MCORE_NODE'), load_env('MFOCUS_NODE')]:
                node_info = {}
                async with db_client.execute(f'SELECT * FROM `{table_name}`;') as res1:
                    node_status = await res1.fetchall()
                    # id, name, memory, history
                for gpu_status in node_status:
                    gpuid, name, memory, history = list(gpu_status)
                    u=0;m=0;p=0
                    history = json.loads(history)
                    for line in history:
                        u+=float(line['u']);m+=float(line['m']);p+=float(line['p'])
                    u/=len(history);m/=len(history);p/=len(history)
                    node_info[gpuid] = {'name': name, 'vram': memory, 'mean_utilization': int(u), 'mean_memory': int(m), 'mean_consumption': int(p)}
                overall_info[table_name] = node_info
        return json.dumps({"success": success, "exception": str(exception), "workload": overall_info}, ensure_ascii=False)
    except Exception as excepted:
        print('Performance acquiring failed')
        success = False
        exception = excepted
        return json.dumps({"success": success, "exception": str(exception)}, ensure_ascii=False)

def sign_message(message):
    global signer
    message = message.encode("utf-8")
    h = SHA256.new()
    h.update(message)
    signature = signer.sign(h)
    sigb64 = base64.b64encode(signature).decode("utf-8")
    return sigb64

def veri_message(message, sigb64):
    global verifier
    message = message.encode("utf-8")
    signature = base64.b64decode(sigb64.encode("utf-8"))
    h = SHA256.new()
    h.update(message)
    if verifier.verify(h, signature):
        return True
    else:
        return False

def seri_message(message):
    message = list(message)
    message_new = []
    for line in message:
        line = dict(line)
        line_new = {"role": line['role'], "content": line['content']}
        message_new.append(line_new)
    return message_new

async def wrap_verify_token(access_token, hduplex_instance=None):
    exec_unbase64_token = await wrap_run_in_exc(None, base64.b64decode, access_token)
    exec_decrypted_token = await wrap_run_in_exc(None, decryptor.decrypt, exec_unbase64_token)
    decrypted_token = exec_decrypted_token.decode("utf-8")
    login_cridential = json.loads(decrypted_token)
    if 'username' in login_cridential:
        login_identity = login_cridential['username']
        login_is_email = False
    elif 'email' in login_cridential:
        login_identity = login_cridential['email']
        login_is_email = True
    else:
        # raise Exception('No Identity Provided')
        return False
    login_password = login_cridential['password']
    if not hduplex_instance:
        hduplex_instance = maica_ws.sub_threading_instance()
    verification_result = await hduplex_instance.run_hash_dcc(login_identity, login_is_email, login_password)
    if not verification_result[0]:
        # raise Exception('Identity hashing failed')
        return False
    else:
        return verification_result


# class StandaloneApplication(WSGIApplication):
#     def __init__(self, app_uri, options=None):
#         self.options = options or {}
#         self.app_uri = app_uri
#         super().__init__()

#     def load_config(self):
#         config = {
#             key: value
#             for key, value in self.options.items()
#             if key in self.cfg.settings and value is not None
#         }
#         for key, value in config.items():
#             self.cfg.set(key.lower(), value)

def run_http():
    global encryptor, decryptor, verifier, signer
    global known_servers
    with open("../key/prv.key", "r") as privkey_file:
        privkey = privkey_file.read()
    with open("../key/pub.key", "r") as pubkey_file:
        pubkey = pubkey_file.read()
    try:
        with open(".servers", "r", encoding='utf-8') as servers_file:
            known_servers = json.loads(servers_file.read())
    except:
        known_servers = False
    privkey_loaded = RSA.import_key(privkey)
    pubkey_loaded = RSA.import_key(pubkey)
    encryptor = PKCS1_OAEP.new(pubkey_loaded)
    decryptor = PKCS1_OAEP.new(privkey_loaded)
    verifier = PKCS1_PSS.new(pubkey_loaded)
    signer = PKCS1_PSS.new(privkey_loaded)
    # app.run(
    #     host='0.0.0.0',
    #     port= 6000,
    #     debug=False
    # )
    # server_thread = pywsgi.WSGIServer(('0.0.0.0', 6000), app)
    # options = {
    #     "bind": "0.0.0.0:6000",
    #     "workers": 1,
        
    # }
    # StandaloneApplication("maica_http:app", options).run()
    # serve(TransLogger(app), host='0.0.0.0', port='6000')

    config = Config()
    config.bind = ['0.0.0.0:6000']
    print('HTTP server started!')
    asyncio.run(serve(app, config))
    # server_thread.serve_forever()

if __name__ == '__main__':
    # from gevent import monkey
    # monkey.patch_all()
    run_http()