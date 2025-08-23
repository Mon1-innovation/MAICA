if __name__ == '__main__':
    from gevent import monkey
    monkey.patch_all()
from quart import Quart, request, jsonify
from quart.views import View
import os
import asyncio
import json
import base64
import functools
import traceback
import aiosqlite
import time

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
from typing import *
from maica_ws import NoWsCoroutine
from maica_utils import *

app = Quart(import_name=__name__)
app.config['JSON_AS_ASCII'] = False

try:
    server_path = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(server_path, ".servers"), "r", encoding='utf-8') as servers_file:
        known_servers = json.loads(servers_file.read())
except Exception:
    known_servers = False

workload_cache = {}

class ShortConnHandler(View):
    """Flask initiates it on every request."""

    auth_pool: DbPoolCoroutine = None
    """Don't forget to implement at first!"""
    maica_pool: DbPoolCoroutine = None
    """Don't forget to implement at first!"""

    def __init__(self, val=True):
        if val:
            self.val = True
            self.stem_inst = NoWsCoroutine(self.auth_pool, self.maica_pool, None)
            self.settings = self.stem_inst.settings
        else:
            self.val = False
            self.stem_inst = None
            self.settings = None

    def dispatch_request(self):
        endpoint = request.endpoint
        function_routed = getattr(self, endpoint)
        if function_routed:
            return asyncio.run(function_routed())

    async def _validate_http(self, raw_data: Union[str, dict], must: list=[]) -> dict:
        data_json = await validate_input(raw_data, 100000, None, must=must)
        if self.val:
            access_token = data_json.get('access_token')
            assert access_token, "access_token not provided"
            login_result = await self.stem_inst.hash_and_login(access_token)
            assert login_result, "Login failed somehow"

        if 'chat_session' in must:
            data_json['chat_session'] = int(data_json['chat_session'])
            assert 0 < data_json.get('chat_session') < 10, "chat_session out of bound"

        return data_json

    async def upload_savefile(self):
        """POST"""
        try:
            json_data = await request.get_json()
            valid_data = await self._validate_http(json_data, must=['access_token', 'chat_session', 'content'])

            chat_session = valid_data.get('chat_session')
            content = valid_data.get('content')
            content_str = json.dumps(valid_data.get('content')) if content else None

            sql_expression_1 = "SELECT persistent_id FROM persistents WHERE user_id = %s AND chat_session_num = %s"
            result = await self.maica_pool.query_get(sql_expression_1, (self.settings.verification.user_id, chat_session))
            if result:
                persistent_id = result[0]
                sql_expression_2 = "UPDATE persistents SET content = %s WHERE persistent_id = %s"
                await self.maica_pool.query_modify(sql_expression_2, (content_str, persistent_id))
            else:
                sql_expression_2 = "INSERT INTO persistents (user_id, chat_session_num, content) VALUES (%s, %s, %s)"
                await self.maica_pool.query_modify(sql_expression_2, (self.settings.verification.user_id, chat_session, content_str))

            return jsonify({"success": True, "exception": None})
        except Exception as e:
            return jsonify({"success": False, "exception": str(e)})
        
    async def upload_trigger(self):
        """POST"""
        try:
            json_data = await request.get_json()
            valid_data = await self._validate_http(json_data, must=['access_token', 'chat_session', 'content'])

            chat_session = valid_data.get('chat_session')
            content = valid_data.get('content')
            content_str = json.dumps(valid_data.get('content')) if content else None

            sql_expression_1 = "SELECT trigger_id FROM triggers WHERE user_id = %s AND chat_session_num = %s"
            result = await self.maica_pool.query_get(sql_expression_1, (self.settings.verification.user_id, chat_session))
            if result:
                trigger_id = result[0]
                sql_expression_2 = "UPDATE triggers SET content = %s WHERE trigger_id = %s"
                await self.maica_pool.query_modify(sql_expression_2, (content_str, trigger_id))
            else:
                sql_expression_2 = "INSERT INTO triggers (user_id, chat_session_num, content) VALUES (%s, %s, %s)"
                await self.maica_pool.query_modify(sql_expression_2, (self.settings.verification.user_id, chat_session, content_str))

            return jsonify({"success": True, "exception": None})
        except Exception as e:
            return jsonify({"success": False, "exception": str(e)})

    async def download_history(self):
        """GET"""
        try:
            json_data = request.args.to_dict(flat=True)
            valid_data = await self._validate_http(json_data, must=['access_token', 'chat_session'])

            chat_session = valid_data.get('chat_session')
            rounds = int(valid_data.get('rounds', 0))

            history_json = (await self.stem_inst.rw_chat_session('r', chat_session_num=chat_session))[1]

            if history_json:
                history_len = len(history_json)
                # If required length larger than overall length
                if abs(2 * int(rounds)) + 1 >= history_len:
                    history_final_json = history_json
                else:
                    match int(rounds):
                        case i if i > 0:
                            history_final_json = history_json[:(2 * i + 1)]
                        case i if i < 0:
                            history_final_json = [history_json[0]] + history_json[(2 * i):]
                        case _:
                            history_final_json = history_json
                history_final_str = json.dumps(history_final_json, ensure_ascii=False)
                sigb64 = await wrap_run_in_exc(None, sign_message, history_final_str)
                return jsonify({"success": True, "exception": None, "content": [sigb64, history_final_json]})
            else:
                return jsonify({"success": True, "exception": None, "content": []})

        except Exception as e:
            return jsonify({"success": False, "exception": str(e)})

    async def restore_history(self):
        """PUT"""
        try:
            json_data = await request.get_json()
            valid_data = await self._validate_http(json_data, must=['access_token', 'chat_session', 'content'])

            chat_session = valid_data.get('chat_session')
            content = valid_data.get('content')

            sigb64, history_json = content
            history_json_sorted = sort_message(history_json)
            assert (await wrap_run_in_exc(None, verify_message, json.dumps(history_json_sorted, ensure_ascii=False), sigb64)), "Signature mismatch"
            await self.stem_inst.restore_chat_session(history_json_sorted, chat_session)

            return jsonify({"success": True, "exception": None})
        except Exception as e:
            return jsonify({"success": False, "exception": str(e)})
        
    async def control_preferences(self):
        """read->GET, write->PATCH, delete->DELETE, reset->POST"""
        try:
            json_data = request.args.to_dict(flat=True) if request.method == 'GET' else await request.get_json()
            must = ['access_token'] if request.method in ['GET', 'POST'] else ['access_token', 'content']
            valid_data = await self._validate_http(json_data, must=must)

            if request.method == 'POST':
                await self.stem_inst.hasher.write_user_status(True, True)
                return jsonify({"success": True, "exception": None})
            else:
                preferences_str = await self.stem_inst.hasher.check_user_status(True)
                preferences_json = json.loads(preferences_str)

                if request.method == 'GET':
                    return jsonify({"success": True, "exception": None, "content": preferences_json})
                else:
                    content = valid_data.get('content')
                    if request.method == 'PATCH':
                        assert isinstance(content, dict), "Request content invalid"
                        preferences_json.update(content)
                    elif request.method == 'DELETE':
                        assert isinstance(content, list), "Request content invalid"
                        for key in content:
                            preferences_json.pop(key)
                    await self.stem_inst.hasher.write_user_status(True, True, **preferences_json)
                    return jsonify({"success": True, "exception": None})
                
        except Exception as e:
            return jsonify({"success": False, "exception": str(e)})

    async def download_token(self):
        """GET, val=False"""
        try:
            json_data = request.args.to_dict(flat=True)
            valid_data = await self._validate_http(json_data, must=['content'])

            content = valid_data.get('content')
            assert isinstance(content, dict), "Request content invalid"

            cridential_type = 'username' if content.get('username') else 'email'
            cridential = content.get(cridential_type)
            password = content.get('password')
            assert isinstance(cridential, str) and isinstance(password, str), "Request content invalid"

            unencrypted_token = json.dumps({cridential_type: cridential, "password": password}, ensure_ascii=False)
            encrypted_token = await wrap_run_in_exc(None, encrypt_token, unencrypted_token)
            return jsonify({"success": True, "exception": None, "content": encrypted_token})

        except Exception as e:
            return jsonify({"success": False, "exception": str(e)})

    async def check_legality(self):
        """GET"""
        try:
            json_data = request.args.to_dict(flat=True)
            valid_data = await self._validate_http(json_data, must=['access_token'])
            return jsonify({"success": True, "exception": None})
        
        except Exception as e:
            return jsonify({"success": False, "exception": str(e)})

    async def get_servers(self):
        """GET, val=False"""
        global known_servers
        return jsonify({"success": True, "exception": None, "content": known_servers})
    
    async def get_accessibility(self):
        """GET, val=False"""
        accessibility = load_env('DEV_STATUS')
        return jsonify({"success": True, "exception": None, "content": accessibility})
    
    async def get_version(self):
        """GET, val=False"""
        curr_version, legc_version = load_env('VERSION_CONTROL').split(';', 1)
        return jsonify({"success": True, "exception": None, "content": {"curr_version": curr_version, "legc_version": legc_version}})

    async def get_workload(self):
        """GET, val=False"""
        global server_path, workload_cache
        try:
            if time.time() - workload_cache.get('timestamp', 0) > 10:
                content =  workload_cache.get('content')

            async with aiosqlite.connect(os.path.join(server_path, '.nvsw.db')) as sqlite_client:
                for table_name in [load_env('MCORE_NODE'), load_env('MFOCUS_NODE')]:
                    node_info = {}
                    async with sqlite_client.execute(f'SELECT * FROM `{table_name}`;') as result:
                        # id, name, memory, history
                        node_status = await result.fetchall()
                        
                    for gpu_status in node_status:
                        gpuid, name, memory, history = list(gpu_status)
                        u = 0; m = 0; p = 0
                        history = json.loads(history)
                        for line in history:
                            u += float(line['u']); m += float(line['m']); p += float(line['p'])
                        u /= len(history); m /= len(history); p /= len(history)
                        node_info[gpuid] = {'name': name, 'vram': memory, 'mean_utilization': int(u), 'mean_memory': int(m), 'mean_consumption': int(p)}

                    content[table_name] = node_info
                    workload_cache['timestamp'] = time.time()
                    workload_cache['content'] = content

            return jsonify({"success": True, "exception": None, "content": content})
        except Exception as e:
            return jsonify({"success": False, "exception": str(e)})

app.add_url_rule("/savefile", methods=['POST'], view_func=ShortConnHandler.as_view("download_savefile"))
app.add_url_rule("/trigger", methods=['POST'],  view_func=ShortConnHandler.as_view("download_trigger"))
app.add_url_rule("/history", methods=['GET'],  view_func=ShortConnHandler.as_view("download_history"))
app.add_url_rule("/history", methods=['PUT'],  view_func=ShortConnHandler.as_view("restore_history"))
app.add_url_rule("/preferences", methods=['GET', 'PATCH', 'DELETE', 'POST'],  view_func=ShortConnHandler.as_view("control_preferences"))
app.add_url_rule("/register", methods=['GET'],  view_func=ShortConnHandler.as_view("download_token"))
app.add_url_rule("/legality", methods=['GET'],  view_func=ShortConnHandler.as_view("check_legality"))
app.add_url_rule("/servers", methods=['GET'],  view_func=ShortConnHandler.as_view("get_servers"))
app.add_url_rule("/accessibility", methods=['GET'],  view_func=ShortConnHandler.as_view("get_accessibility"))
app.add_url_rule("/version", methods=['GET'],  view_func=ShortConnHandler.as_view("get_version"))
app.add_url_rule("/workload", methods=['GET'],  view_func=ShortConnHandler.as_view("get_workload"))

def run_http(auth_pool, maica_pool):

    ShortConnHandler.auth_pool, ShortConnHandler.maica_pool = auth_pool, maica_pool

    config = Config()
    config.bind = ['0.0.0.0:6000']
    print('HTTP server started!')
    try:
        asyncio.run(serve(app, config))
    except KeyboardInterrupt:
        print("HTTP Server stopped!")

if __name__ == '__main__':

    # Pool wrappings init here
    auth_pool, maica_pool = ConnUtils.auth_pool(), ConnUtils.maica_pool()
    
    run_http(auth_pool, maica_pool)