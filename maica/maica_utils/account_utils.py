import asyncio
import bcrypt
import base64
from Crypto.Random import random as CRANDOM
from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_PSS
from Crypto.Hash import SHA256
from .connection_utils import *
from .maica_utils import *
from .setting_utils import *

db_host = load_env('DB_ADDR')
db_user = load_env('DB_USER')
db_password = load_env('DB_PASSWORD')
authdb = load_env('AUTH_DB')
maicadb = load_env('MAICA_DB')

def _get_keys() -> list[PKCS1_OAEP.PKCS1OAEP_Cipher, PKCS1_OAEP.PKCS1OAEP_Cipher, PKCS1_PSS.PSS_SigScheme, PKCS1_PSS.PSS_SigScheme]:
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
    return encryptor, decryptor, verifier, signer

encryptor, decryptor, verifier, signer = _get_keys()

class AccountCursor():
    def __init__(self, fsc:FullSocketsContainer, auth_pool=None, maica_pool=None):
        self.settings: MaicaSettings = fsc.maica_settings
        self.websocket = fsc.rsc.websocket
        self.traceray_id = fsc.rsc.traceray_id
        asyncio.run(self._ainit(auth_pool, maica_pool))
        
    async def _ainit(self, auth_pool, maica_pool):
        if not auth_pool:
            auth_pool = DbPoolCoroutine(
                host=db_host,
                user=db_user,
                password=db_password,
                db=authdb,
                ro=True,
            )
        if not maica_pool:
            maica_pool = DbPoolCoroutine(
                host=db_host,
                user=db_user,
                password=db_password,
                db=maicadb,
            )
        self.auth_pool = auth_pool; self.maica_pool = maica_pool

    async def check_user_status(self, *args) -> Union[list, dict]:
        l = []
        user_id = self.settings.identity.user_id
        sql_expression = "SELECT status FROM account_status WHERE user_id = %s"
        try:
            result = await self.maica_pool.query_modify(expression=sql_expression, values=(user_id))
            stats_json = json.loads(result[0]) if result else {}

            if not args:
                return stats_json
            else:
                for k in args:
                    l.append(stats_json.get(k))
                return l

        except Exception as e:
            error = MaicaDbError(e, '502')
            await common_context_handler(self.websocket, 'user_status_read_failure', traceray_id=self.traceray_id, error=error)

    async def write_user_status(self, enforce=False, **kwargs) -> None:
        user_id = self.settings.identity.user_id
        try:
            if enforce:
                result = await self.check_user_status()
                stats_json = result
                stats_json.update(kwargs)
            else:
                stats_json = kwargs
                stats_str = json.dumps(stats_json, ensure_ascii=False)
                sql_expression = "REPLACE INTO account_status (user_id, status) VALUES (%s, %s)"
                sql_args = (user_id, stats_str)

            await self.maica_pool.query_modify(expression=sql_expression, values=sql_args)

        except Exception as e:
            error = MaicaDbError(e, '502')
            await common_context_handler(self.websocket, 'user_status_write_failure', traceray_id=self.traceray_id, error=error)

    async def run_hash_dcc(self, identity, is_email, password) -> list[bool, Union[str, dict, None]]:
        sql_expression = 'SELECT * FROM users WHERE email = %s' if is_email else 'SELECT * FROM users WHERE username = %s'
        try:
            result = await self.auth_pool.query_get(expression=sql_expression, values=(identity))
            assert isinstance(result[0], int), "User does not exist"
            dbres_id, dbres_username, dbres_nickname, dbres_email, dbres_ecf, dbres_pwd_bcrypt, *_ = result
            input_pwd, target_pwd = password.encode(), dbres_pwd_bcrypt.encode()

            vf_result = await wrap_run_in_exc(None, bcrypt.checkpw, input_pwd, target_pwd)
            await common_context_handler(info=f'Hashing for {identity} finished: {vf_result}')
            self.settings.identity.update(self.fsc.rsc, user_id=dbres_id, username=dbres_username, email=dbres_email)

            f2b_count, f2b_stamp = await asyncio.run(self.check_user_status('f2b_count', 'f2b_stamp'))

            if f2b_stamp:
                # If there's possibility that the account is under F2B
                if time.time() - f2b_stamp < float(load_env('F2B_TIME')):
                    # Waiting for F2B timeout
                    verification = False
                    e = {'f2b': int(float(load_env('F2B_TIME'))+f2b_stamp-time.time())}
                    return verification, e
                else:
                    # Reset f2b_stamp since it has expired
                    await self.write_user_status(f2b_stamp=0)
            if verification:
                # Password is correct
                if not dbres_ecf:
                    # Email not verified
                    verification = False
                    e = {'necf': True}
                    return verification, e
                else:
                    # We're all good
                    await self.write_user_status(f2b_count=0)
                    self.settings.verification.update(self.fsc.rsc, user_id=dbres_id, username=dbres_username, nickname=dbres_nickname, email=dbres_email)
                    return verification, None
            else:
                # Password is wrong
                if not f2b_count:
                    f2b_count = 0
                f2b_count += 1
                # Adding to f2b_count
                e = {'pwdw': f2b_count}
                if f2b_count >= int(load_env('F2B_COUNT')):
                    # Trigger F2B
                    await self.write_user_status({'f2b_stamp': time.time()})
                    f2b_count = 0
                # And write f2b_count always
                await self.write_user_status({'f2b_count': f2b_count})
                return verification, e
        except Exception as e:
            # This function will always return information not exception, since situations can be complex
            verification = False
            return verification, e

    async def hashing_verify(self, access_token) -> list[bool, Union[str, dict, None]]:
        try:
            global encryptor, decryptor, verifier, signer
            exec_unbase64_token = await wrap_run_in_exc(None, base64.b64decode, access_token)
            exec_decrypted_token = await wrap_run_in_exc(None, decryptor.decrypt, exec_unbase64_token)
            decrypted_token = exec_decrypted_token.decode("utf-8")
        except Exception as e:
            verification = False
            return verification, 'Security token not RSA'
        login_cridential = json.loads(decrypted_token)
        login_cridential_print = ReUtils.re_sub_password_spoiler.sub(rf'"password": "{colorama.Fore.BLACK}\1{colorama.Fore.CYAN}"', decrypted_token)

        await common_context_handler(info=f'Login cridential acquired: {login_cridential_print}', color=colorama.Fore.CYAN)

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
        return await self.run_hash_dcc(login_identity, login_is_email, login_password)


