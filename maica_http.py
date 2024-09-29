from gevent import monkey
monkey.patch_all()
from flask import Flask, current_app, redirect, url_for, request
import asyncio
import json
import base64
import traceback
import maica_ws
from gevent import pywsgi
from Crypto.Random import random as CRANDOM # type: ignore
from Crypto.Cipher import PKCS1_OAEP # type: ignore
from Crypto.PublicKey import RSA # type: ignore
from loadenv import load_env

app = Flask(import_name=__name__)


@app.route('/savefile', methods=["POST"])
async def save_upload():
    global privkey_loaded
    success = True
    exception = ''
    try:
        data = json.loads(request.data)
        access_token = data['access_token']
        chat_session = data['chat_session']
        content = data['content']
        print(access_token)
        if int(chat_session) < 1 or int(chat_session) > 9:
            raise Exception('Chat session out of range')
        decryptor = PKCS1_OAEP.new(privkey_loaded)
        decrypted_token =decryptor.decrypt(base64.b64decode(access_token)).decode("utf-8")
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
        if not verification_result[0]:
            raise Exception('Identity hashing failed')
        else:
            if len(content) < 100000:
                with open(f'persistents/{verification_result[2]}_{chat_session}.json', 'w+', encoding = 'utf-8') as sf:
                    sf.write(json.dumps(content, ensure_ascii=False))
            else:
                raise Exception('Content length exceeded')
        return json.dumps({"success": success, "exception": exception}, ensure_ascii=False)
    except Exception as excepted:
        #traceback.print_exc()
        success = False
        exception = excepted
        return json.dumps({"success": success, "exception": exception}, ensure_ascii=False)
    
@app.route('/history', methods=["POST"])
async def history_download():
    global privkey_loaded
    success = True
    exception = ''
    try:
        data = json.loads(request.data)
        access_token = data['access_token']
        chat_session = data['chat_session']
        lines = data['lines']
        print(access_token)
        if int(chat_session) < 1 or int(chat_session) > 9:
            raise Exception('Chat session out of range')
        decryptor = PKCS1_OAEP.new(privkey_loaded)
        decrypted_token =decryptor.decrypt(base64.b64decode(access_token)).decode("utf-8")
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
        if not verification_result[0]:
            raise Exception('Identity hashing failed')
        else:
            session = verification_result
            hisjson = await hduplex_instance.rw_chat_session(chat_session, 'r', None)
            print(hisjson)
            if hisjson[0]:
                hisjson = json.loads(f"[{hisjson[3]}]")
            else:
                raise Exception('History reading failed')
            match int(lines):
                case i if i > 0:
                    hisfine = hisjson[:i]
                case i if i < 0:
                    hisfine = hisjson[i:]
                case _:
                    hisfine = hisjson
            hisstr = json.dumps(hisfine, ensure_ascii=False)
        return json.dumps({"success": success, "exception": exception, "history": hisstr}, ensure_ascii=False)
    except Exception as excepted:
        #traceback.print_exc()
        success = False
        exception = excepted
        return json.dumps({"success": success, "exception": exception}, ensure_ascii=False)

@app.route('/preferences', methods=["POST"])
async def sl_prefs():
    global privkey_loaded
    success = True
    exception = ''
    try:
        data = json.loads(request.data)
        access_token = data['access_token']
        print(access_token)
        decryptor = PKCS1_OAEP.new(privkey_loaded)
        decrypted_token =decryptor.decrypt(base64.b64decode(access_token)).decode("utf-8")
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
        if not verification_result[0]:
            raise Exception('Identity hashing failed')
        else:
            overall_prefs = await hduplex_instance.check_user_preferences(key=False)
            user_prof_exist, prefs_old = overall_prefs[2], overall_prefs[3]
            if not prefs_old:
                prefs_old = {}
            if 'read' in data and data['read']:
                prefs_str = json.dumps(prefs_old, ensure_ascii=False)
                return json.dumps({"success": success, "exception": exception, "preferences": prefs_str}, ensure_ascii=False)
            if 'purge' in data and data['purge']:
                prefs_old = {}
            else:
                if 'write' in data and data['write']:
                    prefs_new = json.loads(data['write'])
                    prefs_old.update(prefs_new)
                if 'delete' in data and data['delete']:
                    for popper in json.loads(data['delete']):
                        prefs_old.pop(popper, None)
            prefs_str = json.dumps(prefs_old, ensure_ascii=False)
            if len(prefs_str) < 100000:
                await hduplex_instance.write_user_preferences(prefs_old, enforce=True)
            else:
                raise Exception('Content length exceeded')
        return json.dumps({"success": success, "exception": exception}, ensure_ascii=False)
    except Exception as excepted:
        #traceback.print_exc()
        success = False
        exception = excepted
        return json.dumps({"success": success, "exception": exception}, ensure_ascii=False)

@app.route('/register', methods=["POST"])
async def register():
    global pubkey_loaded
    success = True
    exception = ''
    try:
        data = json.loads(request.data)
        if 'username' in data:
            type_usr = 'username'
            cridential = data['username']
        elif 'email' in data:
            type_usr = 'email'
            cridential = data['email']
        else:
            success = False
            exception = "No user cridential provided"
            return json.dumps({"success": success, "exception": exception}, ensure_ascii=False)
        password = data['password']
        token_raw = json.dumps({type_usr: cridential, "password": password}, ensure_ascii=False)
        encryptor = PKCS1_OAEP.new(pubkey_loaded)
        encrypted_token = base64.b64encode(encryptor.encrypt(token_raw.encode('utf-8'))).decode('utf-8')
        return json.dumps({"success": success, "exception": exception, "token": encrypted_token}, ensure_ascii=False)
    except Exception as excepted:
        success = False
        exception = excepted
        return json.dumps({"success": success, "exception": exception}, ensure_ascii=False)

@app.route('/legality', methods=["POST"])
async def legal():
    global privkey_loaded
    success = True
    exception = ''
    try:
        data = json.loads(request.data)
        access_token = data['access_token']
        print(access_token)
        decryptor = PKCS1_OAEP.new(privkey_loaded)
        decrypted_token =decryptor.decrypt(base64.b64decode(access_token)).decode("utf-8")
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
        return json.dumps({"success": success, "exception": exception})
    except Exception as excepted:
        success = False
        exception = excepted
        return json.dumps({"success": success, "exception": exception}, ensure_ascii=False)

@app.route('/servers', methods=["POST"])
async def nameserv():
    global known_servers
    success = True
    exception = ''
    return json.dumps({"success": success, "exception": exception, "servers": known_servers}, ensure_ascii=False)

@app.route('/accessibility', methods=["POST"])
async def access():
    success = True
    exception = ''
    accessibility = load_env('DEV_STATUS')
    return json.dumps({"success": success, "exception": exception, "accessibility": accessibility}, ensure_ascii=False)

if __name__ == '__main__':
    global pubkey_loaded, privkey_loaded
    with open("key/prv.key", "r") as privkey_file:
        privkey = privkey_file.read()
    with open("key/pub.key", "r") as pubkey_file:
        pubkey = pubkey_file.read()
    try:
        with open(".servers", "r", encoding='utf-8') as servers_file:
            known_servers = json.dumps(json.loads(servers_file.read()), ensure_ascii=False)
    except:
        known_servers = False
    privkey_loaded = RSA.import_key(privkey)
    pubkey_loaded = RSA.import_key(pubkey)
#    app.run(
#        host='0.0.0.0',
#        port= 6000,
#        debug=False
#    )
    server_thread = pywsgi.WSGIServer(('0.0.0.0', 6000), app)
    print('HTTP server started!')
    server_thread.serve_forever()