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

# 通过methods设置POST请求
@app.route('/', methods=["POST"])
def json_request():
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
                    sf.write(content)
            else:
                success = False
                exception = "Content length exceeded"
                return f'{success}, {exception}'
        return f'{success}, {None}'
    except Exception as excepted:
        traceback.print_exc()
        success = False
        exception = excepted
        return f'{success}, {exception}'
if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port= 6000,
        debug=True
    )