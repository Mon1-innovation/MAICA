"""Import layer 5"""
import asyncio
import bcrypt
import base64
import json
import time
import colorama
from Crypto.Random import random as CRANDOM
from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_PSS
from Crypto.Signature.pss import PSS_SigScheme
from Crypto.Hash import SHA256

from .connection_utils import *
from maica.maica_utils import *
from .setting_utils import *
from .fsc_late import *

def pkg_init_account_utils():
    global encryptor, decryptor, verifier, signer
    encryptor = decryptor = verifier = signer = None
    _check_keys()

def _get_keys() -> tuple[PKCS1_OAEP.PKCS1OAEP_Cipher, PKCS1_OAEP.PKCS1OAEP_Cipher, PSS_SigScheme, PSS_SigScheme]:
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
    verifier = PKCS1_PSS.new(pubkey_loaded)
    signer = PKCS1_PSS.new(privkey_loaded)
    return encryptor, decryptor, verifier, signer

def _check_keys() -> bool:
    global encryptor, decryptor, verifier, signer
    if not (encryptor and decryptor and verifier and signer):
        encryptor, decryptor, verifier, signer = _get_keys()

class AccountCursor(AsyncCreator):
    """Handles any account related things."""
    def __init__(self, settings: MaicaSettings, auth_pool=None, maica_pool=None):
        self.settings = settings
        self.auth_pool, self.maica_pool = auth_pool, maica_pool
        
    async def _ainit(self):
        if not self.auth_pool:
            self.auth_pool = await ConnUtils.auth_pool()
        if not self.maica_pool:
            self.maica_pool = await ConnUtils.maica_pool()

    async def check_user_status(self, pref=False, *args) -> Union[dict, tuple]:
        status = "status" if not pref else "preferences"
        l = []
        user_id = self.settings.identity.user_id
        sql_expression = f"SELECT {status} FROM account_status WHERE user_id = %s"
        try:
            result = await self.maica_pool.query_get(expression=sql_expression, values=(user_id, ))
            stats_json = json.loads(result[0]) if result else {}

            if not args:
                return stats_json
            else:
                for k in args:
                    l.append(stats_json.get(k))
                return tuple(l)

        except Exception as e:
            raise MaicaDbError(f'Cannot acquire user {user_id}\'s {status}', '502', f'user_{status}_read_failed') from e

    async def write_user_status(self, enforce=False, pref=False, **kwargs) -> None:
        status = "status" if not pref else "preferences"
        user_id = self.settings.identity.user_id
        try:
            if not enforce:
                result = await self.check_user_status(pref=pref)
                stats_json = result
                stats_json.update(kwargs)
            else:
                stats_json = kwargs

            stats_str = json.dumps(stats_json, ensure_ascii=False)
            if self.maica_pool.db_type == 'mysql':
                sql_expression = f"INSERT INTO account_status (user_id, {status}) VALUES (%s, %s) ON DUPLICATE KEY UPDATE {status} = %s"
            else:
                sql_expression = f"INSERT INTO account_status (user_id, {status}) VALUES (%s, %s) ON CONFLICT(user_id) DO UPDATE SET {status} = %s"
            sql_args = (user_id, stats_str, stats_str)

            await self.maica_pool.query_modify(expression=sql_expression, values=sql_args)

        except Exception as e:
            raise MaicaDbError(e, '502', f'user_{status}_write_failed') from e

    async def _account_pwd_verify(self, identity, is_email, password) -> tuple[bool, Union[str, dict, None]]:
        sql_expression = 'SELECT id, username, nickname, email, is_email_confirmed, password FROM users WHERE email = %s' if is_email else 'SELECT id, username, nickname, email, is_email_confirmed, password FROM users WHERE username = %s'
        try:
            result = await self.auth_pool.query_get(expression=sql_expression, values=(identity, ))
            assert result, "User does not exist"

            dbres_id, dbres_username, dbres_nickname, dbres_email, dbres_ecf, dbres_pwd_bcrypt = result
            self.settings.identity.update(user_id=dbres_id, username=dbres_username, nickname=dbres_nickname, email=dbres_email)

            input_pwd, target_pwd = password.encode(), dbres_pwd_bcrypt.encode()
            vf_result = await wrap_run_in_exc(None, bcrypt.checkpw, input_pwd, target_pwd)
            await messenger(info=f'Hashing for {identity} finished: {vf_result}')

            f2b_count, f2b_stamp = await self.check_user_status(False, 'f2b_count', 'f2b_stamp')

            if f2b_stamp:
                # If there's possibility that the account is under F2B
                if time.time() - f2b_stamp < int(G.A.F2B_TIME):
                    # Waiting for F2B timeout
                    e = {'f2b': int(int(G.A.F2B_TIME) + f2b_stamp - time.time())}
                    return False, e
                else:
                    # Reset f2b_stamp since it has expired
                    await self.write_user_status(f2b_stamp=0)
            if vf_result:
                # Password is correct
                if not dbres_ecf:
                    # Email not verified
                    e = {'necf': True}
                    return False, e
                else:
                    # We're all good
                    await self.write_user_status(f2b_count=0)
                    self.settings.verification.update(user_id=dbres_id, username=dbres_username, nickname=dbres_nickname, email=dbres_email)
                    return True, None
            else:
                # Password is wrong
                if not f2b_count:
                    f2b_count = 0
                f2b_count += 1
                # Adding to f2b_count
                e = {'pwdw': f2b_count}
                if f2b_count >= int(G.A.F2B_COUNT):
                    # Trigger F2B
                    await self.write_user_status(f2b_stamp=time.time())
                    f2b_count = 0
                # And write f2b_count always
                await self.write_user_status(f2b_count=f2b_count)
                return False, e
        except Exception as e:
            # This function will always return information not exception, since situations can be complex
            return False, e

    async def hashing_verify(self, access_token) -> tuple[bool, Union[str, dict, None]]:
        try:
            global encryptor, decryptor, verifier, signer
            exec_unbase64_token = await wrap_run_in_exc(None, base64.b64decode, access_token)
            exec_decrypted_token = await wrap_run_in_exc(None, decryptor.decrypt, exec_unbase64_token)
            decrypted_token = exec_decrypted_token.decode("utf-8")
        except Exception as e:
            raise MaicaInputWarning(f'Security token "{ellipsis_str(access_token)}" not RSA: {str(e)}') from e
        login_cridential = json.loads(decrypted_token)
        login_cridential_print = ReUtils.re_sub_password_spoiler.sub(rf'"password": "{colorama.Back.CYAN}\1{colorama.Back.RESET}"', decrypted_token)

        sync_messenger(info=f'Login cridential acquired: {login_cridential_print}', type=MsgType.RECV)

        if login_cridential.get('username'):
            login_identity = login_cridential['username']
            login_is_email = False
        elif login_cridential.get('email'):
            login_identity = login_cridential['email']
            login_is_email = True
        else:
            raise Exception('No identity provided')
        try:
            login_password = login_cridential['password']
        except Exception:
            raise Exception('No password provided')
        return await self._account_pwd_verify(login_identity, login_is_email, login_password)
    
def encrypt_token(cridential: str) -> str:
    """Generates an encrypted token. It does not care validity."""
    encoded_token = cridential.encode('utf-8')
    encrypted_token = encryptor.encrypt(encoded_token)
    decoded_token = base64.b64encode(encrypted_token).decode('utf-8')
    return decoded_token

def sign_message(message):
    message = message.encode("utf-8")
    h = SHA256.new()
    h.update(message)
    signature = signer.sign(h)
    sigb64 = base64.b64encode(signature).decode("utf-8")
    return sigb64

def verify_message(message, sigb64):
    message = message.encode("utf-8")
    signature = base64.b64decode(sigb64.encode("utf-8"))
    h = SHA256.new()
    h.update(message)
    if verifier.verify(h, signature):
        return True
    else:
        return False

if __name__ == '__main__':
    from maica import init
    init()
    pkg_init_account_utils()
    
    async def _atest():
        a = await AccountCursor.async_create(MaicaSettings())
        ...

    print(asyncio.run(_atest()))