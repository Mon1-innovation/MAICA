from flask import Flask, current_app, redirect, url_for, request
import json
import base64
import traceback
import maica_ws
from gevent import pywsgi
from Crypto.Random import random as CRANDOM # type: ignore
from Crypto.Cipher import PKCS1_OAEP # type: ignore
from Crypto.PublicKey import RSA # type: ignore
from loadenv import load_env

if __name__ == '__main__':
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
#    app.run(
#        host='0.0.0.0',
#        port= 6000,
#        debug=False
#    )
    server_thread = pywsgi.WSGIServer(('0.0.0.0', 6001), app)
    print('HTTP server started!')
    server_thread.serve_forever()