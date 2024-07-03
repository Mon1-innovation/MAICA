from flask import Flask, current_app, redirect, url_for, request
import json
import base64
import traceback
import ws
from Crypto.Random import random as CRANDOM # type: ignore
from Crypto.Cipher import PKCS1_OAEP # type: ignore
from Crypto.PublicKey import RSA # type: ignore

# 实例化app
app = Flask(import_name=__name__)

with open("key/prv.key", "r") as privkey_file:
    global privkey
    privkey = privkey_file.read()
with open("key/pub.key", "r") as pubkey_file:
    global pubkey
    pubkey = pubkey_file.read()
privkey_loaded = RSA.import_key(privkey)
pubkey_loaded = RSA.import_key(pubkey)


# 通过methods设置POST请求
@app.route('/savefile', methods=["POST"])
def save_upload():
    success = True
    exception = ''
    try:
        data = json.loads(request.data)
        access_token = data['access_token']
        chat_session = data['chat_session']
        content = data['content']
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
        verification_result = ws.run_hash_dcc(login_identity, login_is_email, login_password)
        if not verification_result[0]:
            raise Exception('Identity hashing failed')
        else:
            if len(content) < 100000:
                with open(f'persistents/{verification_result[2]}_{chat_session}.json', 'w+', encoding = 'utf-8') as sf:
                    sf.write(json.dumps(content, ensure_ascii=False))
            else:
                success = False
                exception = "Content length exceeded"
                return json.dumps({"success": success, "exception": exception}, ensure_ascii=False)
        return json.dumps({"success": success, "exception": exception}, ensure_ascii=False)
    except Exception as excepted:
        #traceback.print_exc()
        success = False
        exception = excepted
        return json.dumps({"success": success, "exception": exception}, ensure_ascii=False)

@app.route('/history', methods=["POST"])
def history_download():
    success = True
    exception = ''
    try:
        data = json.loads(request.data)
        access_token = data['access_token']
        chat_session = data['chat_session']
        lines = data['lines']
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
        verification_result = ws.run_hash_dcc(login_identity, login_is_email, login_password)
        if not verification_result[0]:
            raise Exception('Identity hashing failed')
        else:
            session = verification_result
            hisjson = ws.rw_chat_session(session, chat_session, 'r', None)
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

    
@app.route('/register', methods=["POST"])
def register():
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
        traceback.print_exc()
        success = False
        exception = excepted
        return json.dumps({"success": success, "exception": exception}, ensure_ascii=False)
    

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port= 6000,
        debug=True
    )