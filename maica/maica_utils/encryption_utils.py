"""Import layer 5"""
import asyncio
import bcrypt
import base64
import json
import time
import colorama

from typing import *

from Crypto.Random import random as CRANDOM
from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Signature import pss
from Crypto.Hash import SHA256

from .maica_utils import *

class CryptoObject():
    encryptor: Optional[PKCS1_OAEP.PKCS1OAEP_Cipher] = None
    decryptor: Optional[PKCS1_OAEP.PKCS1OAEP_Cipher] = None
    verifier: Optional[pss.PSS_SigScheme] = None
    signer: Optional[pss.PSS_SigScheme] = None

    def filled(self):
        return (self.encryptor and self.decryptor and self.verifier and self.signer)

crypto_object = CryptoObject()

def pkg_init_encryption_utils():
    _check_keys()

def _get_keys():
    prv_path = get_inner_path('keys/prv.key')
    pub_path = get_inner_path('keys/pub.key')

    with open(prv_path, "r") as privkey_file:
        privkey = privkey_file.read()
    with open(pub_path, "r") as pubkey_file:
        pubkey = pubkey_file.read()

    pubkey_loaded = RSA.import_key(pubkey)
    privkey_loaded = RSA.import_key(privkey)
    encryptor = PKCS1_OAEP.new(pubkey_loaded)
    decryptor = PKCS1_OAEP.new(privkey_loaded)
    verifier = pss.new(pubkey_loaded)
    signer = pss.new(privkey_loaded)
    return encryptor, decryptor, verifier, signer

def _check_keys() -> bool:
    co = crypto_object
    if not co.filled():
        co.encryptor, co.decryptor, co.verifier, co.signer = _get_keys()

def encrypt_token(cridential: str) -> str:
    """Generates an encrypted token. It does not care validity."""
    encoded_token = cridential.encode('utf-8')
    encrypted_token = crypto_object.encryptor.encrypt(encoded_token)
    decoded_token = base64.b64encode(encrypted_token).decode('utf-8')
    return decoded_token

def sign_message(message: str):
    message = message.encode("utf-8")
    h = SHA256.new()
    h.update(message)
    signature = crypto_object.signer.sign(h)
    sigb64 = base64.b64encode(signature).decode("utf-8")
    return sigb64

def verify_message(message: str, sigb64):
    message = message.encode("utf-8")
    signature = base64.b64decode(sigb64.encode("utf-8"))
    h = SHA256.new()
    h.update(message)
    if crypto_object.verifier.verify(h, signature):
        return True
    else:
        return False

if __name__ == '__main__':
    from maica import init
    init()
    pkg_init_encryption_utils()
    
    async def _atest():
        ...

    print(asyncio.run(_atest()))