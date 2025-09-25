from quart import Quart, request, jsonify, Response
from quart.views import View
import os
import asyncio
import json
import traceback
import time
import colorama
import logging

from hypercorn.config import Config
from hypercorn.asyncio import serve
from typing import *

from maica.maica_ws import NoWsCoroutine, _onliners
from maica.maica_utils import *
from maica.mtools import NvWatcher

def pkg_init_maica_http():
    global MCORE_ADDR, MFOCUS_ADDR, FULL_RESTFUL, known_servers
    MCORE_ADDR = load_env('MAICA_MCORE_ADDR')
    MFOCUS_ADDR = load_env('MAICA_MFOCUS_ADDR')
    FULL_RESTFUL = load_env('MAICA_FULL_RESTFUL')
    if FULL_RESTFUL == '1':
        app.add_url_rule("/savefile", methods=['POST'], view_func=ShortConnHandler.as_view("upload_savefile"))
        app.add_url_rule("/savefile", methods=['DELETE'], view_func=ShortConnHandler.as_view("delete_savefile"))
        app.add_url_rule("/trigger", methods=['POST'], view_func=ShortConnHandler.as_view("upload_trigger"))
        app.add_url_rule("/trigger", methods=['DELETE'], view_func=ShortConnHandler.as_view("delete_trigger"))
        app.add_url_rule("/history", methods=['GET'], view_func=ShortConnHandler.as_view("download_history"))
        app.add_url_rule("/history", methods=['PUT'], view_func=ShortConnHandler.as_view("restore_history"))
        app.add_url_rule("/preferences", methods=['GET'], view_func=ShortConnHandler.as_view("download_preferences"))
        app.add_url_rule("/preferences", methods=['PATCH'], view_func=ShortConnHandler.as_view("edit_preferences"))
        app.add_url_rule("/preferences", methods=['DELETE'], view_func=ShortConnHandler.as_view("delete_preferences"))
        app.add_url_rule("/preferences", methods=['POST'], view_func=ShortConnHandler.as_view("reset_preferences"))
        app.add_url_rule("/register", methods=['GET'], view_func=ShortConnHandler.as_view("download_token", val=False))
        app.add_url_rule("/legality", methods=['GET'], view_func=ShortConnHandler.as_view("check_legality"))
        app.add_url_rule("/servers", methods=['GET'], view_func=ShortConnHandler.as_view("get_servers", val=False))
        app.add_url_rule("/accessibility", methods=['GET'], view_func=ShortConnHandler.as_view("get_accessibility", val=False))
        app.add_url_rule("/version", methods=['GET'], view_func=ShortConnHandler.as_view("get_version", val=False))
        app.add_url_rule("/workload", methods=['GET'], view_func=ShortConnHandler.as_view("get_workload", val=False))
        app.add_url_rule("/defaults", methods=['GET'], view_func=ShortConnHandler.as_view("get_defaults", val=False))
    else:
        app.add_url_rule("/savefile", methods=['POST'], view_func=ShortConnHandler.as_view("upload_savefile"))
        app.add_url_rule("/savefile/delete", methods=['POST'], view_func=ShortConnHandler.as_view("delete_savefile"))
        app.add_url_rule("/trigger", methods=['POST'], view_func=ShortConnHandler.as_view("upload_trigger"))
        app.add_url_rule("/trigger/delete", methods=['POST'], view_func=ShortConnHandler.as_view("delete_trigger"))
        app.add_url_rule("/history", methods=['GET'], view_func=ShortConnHandler.as_view("download_history"))
        app.add_url_rule("/history", methods=['POST'], view_func=ShortConnHandler.as_view("restore_history"))
        app.add_url_rule("/preferences", methods=['GET'], view_func=ShortConnHandler.as_view("download_preferences"))
        app.add_url_rule("/preferences/edit", methods=['POST'], view_func=ShortConnHandler.as_view("edit_preferences"))
        app.add_url_rule("/preferences/delete", methods=['POST'], view_func=ShortConnHandler.as_view("delete_preferences"))
        app.add_url_rule("/preferences/reset", methods=['POST'], view_func=ShortConnHandler.as_view("reset_preferences"))
        app.add_url_rule("/register", methods=['GET'], view_func=ShortConnHandler.as_view("download_token", val=False))
        app.add_url_rule("/legality", methods=['GET'], view_func=ShortConnHandler.as_view("check_legality"))
        app.add_url_rule("/servers", methods=['GET'], view_func=ShortConnHandler.as_view("get_servers", val=False))
        app.add_url_rule("/accessibility", methods=['GET'], view_func=ShortConnHandler.as_view("get_accessibility", val=False))
        app.add_url_rule("/version", methods=['GET'], view_func=ShortConnHandler.as_view("get_version", val=False))
        app.add_url_rule("/workload", methods=['GET'], view_func=ShortConnHandler.as_view("get_workload", val=False))
        app.add_url_rule("/defaults", methods=['GET'], view_func=ShortConnHandler.as_view("get_defaults", val=False))
    app.add_url_rule("/<path>", methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'], view_func=ShortConnHandler.as_view("any_unknown", val=False))

    try:
        known_servers = json.loads(load_env('MAICA_SERVERS_LIST'))
    except Exception as e:
        sync_messenger(info=f'Loading servers list failed: {str(e)}', type=MsgType.ERROR)
        known_servers = False

app = Quart(import_name=__name__)
app.config['JSON_AS_ASCII'] = False

quart_logger = logging.getLogger('hypercorn.error')
quart_logger.disabled = True

workload_cache = {}

class ShortConnHandler(View):
    """Flask initiates it on every request."""

    auth_pool: DbPoolCoroutine = None
    """Don't forget to implement at first!"""
    maica_pool: DbPoolCoroutine = None
    """Don't forget to implement at first!"""
    mcore_watcher: NvWatcher = None
    mfocus_watcher: NvWatcher = None

    def __init__(self, val=True):
        if val:
            self.val = True
        else:
            self.val = False

    def msg_http(self, *args, **kwargs):
        if self.val:
            sync_messenger(*args, **kwargs)

    async def dispatch_request(self, **kwargs):
        try:
            if self.val:
                self.stem_inst = await NoWsCoroutine.async_create(self.auth_pool, self.maica_pool, None)
                self.settings = self.stem_inst.settings
            else:
                self.stem_inst = None
                self.settings = None
            endpoint = request.endpoint
            function_routed = getattr(self, endpoint)

            self.msg_http(info=f'Recieved request on API endpoint {endpoint}', type=MsgType.RECV)
            result = await function_routed()

            if isinstance(result, Response):
                result_json = await result.get_json()
                d = {"success": result_json.get('success'), "exception": result_json.get('exception'), "content": ellipsis_str(result_json.get('content'))}
                self.msg_http(info=f'Return value: {str(d)}', type=MsgType.SYS)

            return result

        except CommonMaicaException as ce:
            if ce.is_critical:
                traceback.print_exc()
            await messenger(error=ce, no_raise=True)
            return jsonify({"success": False, "exception": str(ce)})

        except Exception as e:
            await messenger(info=f'Handler hit an exception: {str(e)}', type=MsgType.WARN)
            return jsonify({"success": False, "exception": str(e)})

    async def _validate_http(self, raw_data: Union[str, dict], must: list=[]) -> dict:
        data_json = await validate_input(raw_data, 100000, None, must=must)
        if self.val and 'access_token' in must:
            access_token = data_json.get('access_token')
            assert access_token, "access_token not provided"
            login_result = await self.stem_inst.hash_and_login(access_token)
            assert login_result, "Login failed somehow"

        if 'chat_session' in must:
            data_json['chat_session'] = int(data_json['chat_session'])
            assert 0 <= data_json.get('chat_session') < 10, "chat_session out of bound"

        return data_json

    async def upload_savefile(self):
        """POST"""
        json_data = await request.get_json()
        valid_data = await self._validate_http(json_data, must=['access_token', 'chat_session', 'content'])

        chat_session = valid_data.get('chat_session')
        content = valid_data.get('content')
        content_str = json.dumps(valid_data.get('content'), ensure_ascii=False) if content else None

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
    
    async def delete_savefile(self):
        """DELETE"""
        json_data = await request.get_json()
        valid_data = await self._validate_http(json_data, must=['access_token', 'chat_session'])

        chat_session = valid_data.get('chat_session')

        sql_expression_1 = "DELETE FROM persistents WHERE user_id = %s AND chat_session_num = %s"
        result = await self.maica_pool.query_modify(sql_expression_1, (self.settings.verification.user_id, chat_session))

        return jsonify({"success": True, "exception": None})
        
    async def upload_trigger(self):
        """POST"""
        json_data = await request.get_json()
        valid_data = await self._validate_http(json_data, must=['access_token', 'chat_session', 'content'])

        chat_session = valid_data.get('chat_session')
        content = valid_data.get('content')
        content_str = json.dumps(valid_data.get('content'), ensure_ascii=False) if content else None

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
    
    async def delete_trigger(self):
        """DELETE"""
        json_data = await request.get_json()
        valid_data = await self._validate_http(json_data, must=['access_token', 'chat_session'])

        chat_session = valid_data.get('chat_session')

        sql_expression_1 = "DELETE FROM triggers WHERE user_id = %s AND chat_session_num = %s"
        result = await self.maica_pool.query_modify(sql_expression_1, (self.settings.verification.user_id, chat_session))

        return jsonify({"success": True, "exception": None})
   
    async def download_history(self):
        """GET"""
        json_data = request.args.to_dict(flat=True)
        valid_data = await self._validate_http(json_data, must=['access_token', 'chat_session'])

        chat_session = valid_data.get('chat_session')
        assert 1 <= chat_session < 10, "chat_session out of bound"
        rounds = int(valid_data.get('content', 0))

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

    async def restore_history(self):
        """PUT"""
        json_data = await request.get_json()
        valid_data = await self._validate_http(json_data, must=['access_token', 'chat_session', 'content'])

        chat_session = valid_data.get('chat_session')
        assert 1 <= chat_session < 10, "chat_session out of bound"
        content = valid_data.get('content')

        sigb64, history_json = content
        history_json_sorted = sort_message(history_json)
        assert (await wrap_run_in_exc(None, verify_message, json.dumps(history_json_sorted, ensure_ascii=False), sigb64)), "Signature mismatch"
        await self.stem_inst.restore_chat_session(history_json_sorted, chat_session)

        return jsonify({"success": True, "exception": None})

    async def download_preferences(self):
        """GET"""
        json_data = request.args.to_dict(flat=True)
        valid_data = await self._validate_http(json_data, must=['access_token'])

        preferences_json = await self.stem_inst.hasher.check_user_status(pref=True)

        return jsonify({"success": True, "exception": None, "content": preferences_json})

    async def edit_preferences(self):
        """PATCH"""
        json_data = await request.get_json()
        valid_data = await self._validate_http(json_data, must=['access_token', 'content'])

        preferences_json = await self.stem_inst.hasher.check_user_status(pref=True)

        content = valid_data.get('content')
        assert isinstance(content, dict), "Request content invalid" 
        preferences_json.update(content)
        await self._validate_http(preferences_json, must=[])

        await self.stem_inst.hasher.write_user_status(enforce=True, pref=True, **preferences_json)
        return jsonify({"success": True, "exception": None})

    async def delete_preferences(self):
        """DELETE"""
        json_data = await request.get_json()
        valid_data = await self._validate_http(json_data, must=['access_token', 'content'])

        preferences_json = await self.stem_inst.hasher.check_user_status(pref=True)

        content = valid_data.get('content')
        assert isinstance(content, list), "Request content invalid" 
        for key in content:
            preferences_json.pop(key)

        await self.stem_inst.hasher.write_user_status(enforce=True, pref=True, **preferences_json)
        return jsonify({"success": True, "exception": None})

    async def reset_preferences(self):
        """POST"""
        json_data = await request.get_json()
        valid_data = await self._validate_http(json_data, must=['access_token'])

        await self.stem_inst.hasher.write_user_status(enforce=True, pref=True)
        return jsonify({"success": True, "exception": None})
        
    # async def control_preferences(self):
    #     """read->GET, write->PATCH, delete->DELETE, reset->POST"""
    #     try:
    #         json_data = request.args.to_dict(flat=True) if request.method == 'GET' else await request.get_json()
    #         must = ['access_token'] if request.method in ['GET', 'POST'] else ['access_token', 'content']
    #         valid_data = await self._validate_http(json_data, must=must)

    #         if request.method == 'POST':
    #             await self.stem_inst.hasher.write_user_status(True, True)
    #             return jsonify({"success": True, "exception": None})
    #         else:
    #             preferences_json = await self.stem_inst.hasher.check_user_status(True)

    #             if request.method == 'GET':
    #                 return jsonify({"success": True, "exception": None, "content": preferences_json})
    #             else:
    #                 content = valid_data.get('content')
    #                 if request.method == 'PATCH':
    #                     assert isinstance(content, dict), "Request content invalid"
    #                     preferences_json.update(content)
    #                 elif request.method == 'DELETE':
    #                     assert isinstance(content, list), "Request content invalid"
    #                     for key in content:
    #                         preferences_json.pop(key)
    #                 await self.stem_inst.hasher.write_user_status(True, True, **preferences_json)
    #                 return jsonify({"success": True, "exception": None})
                
    #     except Exception as e:
    #         return jsonify({"success": False, "exception": str(e)})

    async def download_token(self):
        """GET, val=False"""
        json_data = request.args.to_dict(flat=True)
        valid_data = await self._validate_http(json_data, must=['content'])

        content = json.loads(valid_data.get('content'))

        cridential_type = 'username' if content.get('username') else 'email'
        cridential = content.get(cridential_type)
        password = content.get('password')
        assert isinstance(cridential, str) and isinstance(password, str), "Request content invalid"

        unencrypted_token = json.dumps({cridential_type: cridential, "password": password}, ensure_ascii=False)
        encrypted_token = await wrap_run_in_exc(None, encrypt_token, unencrypted_token)
        return jsonify({"success": True, "exception": None, "content": encrypted_token})

    async def check_legality(self):
        """GET"""
        json_data = request.args.to_dict(flat=True)
        valid_data = await self._validate_http(json_data, must=['access_token'])
        content = self.settings.verification.username
        return jsonify({"success": True, "exception": None, "content": content})

    async def get_servers(self):
        """GET, val=False"""
        return jsonify({"success": True, "exception": None, "content": known_servers})
    
    async def get_accessibility(self):
        """GET, val=False"""
        accessibility = load_env('MAICA_DEV_STATUS')
        return jsonify({"success": True, "exception": None, "content": accessibility})
    
    async def get_version(self):
        """GET, val=False"""
        curr_version, legc_version = load_env('MAICA_CURR_VERSION'), load_env('MAICA_VERSION_CONTROL')
        return jsonify({"success": True, "exception": None, "content": {"curr_version": curr_version, "legc_version": legc_version}})

    async def get_workload(self):
        """GET, val=False"""
        content = self.mcore_watcher.get_statics_inside()
        content_2 = self.mfocus_watcher.get_statics_inside()
        if isinstance(content_2, dict):
            content.update(content_2)
        content.update({"onliners": len(_onliners)})

        return jsonify({"success": True, "exception": None, "content": content})
    
    async def get_defaults(self):
        """GET, val=False"""
        settings = MaicaSettings()
        content = {}
        content.update(settings.basic.default())
        content.update(settings.extra.default())
        content.update(settings.super.default())
        return jsonify({"success": True, "exception": None, "content": content})

    async def any_unknown(self):
        """Handles any unknown endpoint"""
        await messenger(info=f"An unknown access to {request.full_path} handled", type=MsgType.WARN)
        return jsonify({"success": False, "exception": 'Unknown request endpoint or method'}), 404

async def prepare_thread(**kwargs):
    auth_created = False; maica_created = False

    if kwargs.get('auth_pool'):
        ShortConnHandler.auth_pool = kwargs.get('auth_pool')
    else:
        ShortConnHandler.auth_pool = await ConnUtils.auth_pool()
        auth_created = True
    if kwargs.get('maica_pool'):
        ShortConnHandler.maica_pool = kwargs.get('maica_pool')
    else:
        ShortConnHandler.maica_pool = await ConnUtils.maica_pool()
        maica_created = True

    if get_host(MCORE_ADDR) != get_host(MFOCUS_ADDR):

        ShortConnHandler.mcore_watcher = await NvWatcher.async_create('mcore', 'maica')
        ShortConnHandler.mfocus_watcher = await NvWatcher.async_create('mfocus', 'maica')
        mcore_task = asyncio.create_task(ShortConnHandler.mcore_watcher.wrapped_main_watcher())
        mfocus_task = asyncio.create_task(ShortConnHandler.mfocus_watcher.wrapped_main_watcher())

    else:

        ShortConnHandler.mcore_watcher = await NvWatcher.async_create('mcore', 'maica')
        mcore_task = asyncio.create_task(ShortConnHandler.mcore_watcher.wrapped_main_watcher())
        mfocus_task = None

    config = Config()
    config.bind = ['0.0.0.0:6000']

    main_task = asyncio.create_task(serve(app, config))
    task_list = [main_task, mcore_task]
    if mfocus_task:
        task_list.append(mfocus_task)

    await messenger(info='MAICA HTTP server started!', type=MsgType.PRIM_SYS)

    try:
        await asyncio.wait(task_list, return_when=asyncio.FIRST_COMPLETED)

    except BaseException as be:
        if isinstance(be, Exception):
            error = CommonMaicaError(str(be), '504')
            await messenger(error=error, no_raise=True)
    finally:
        close_list = []
        if auth_created:
            close_list.append(ShortConnHandler.auth_pool.close())
        if maica_created:
            close_list.append(ShortConnHandler.maica_pool.close())

        await asyncio.gather(*close_list, return_exceptions=True)

        # Normally maica_http should be the first one (possibly only one) to
        # respond to the original SIGINT.

        # So its stop msg will be print first, adding \n after ^C to look prettier.

        await messenger(info='\n', type=MsgType.PLAIN)
        await messenger(info='MAICA HTTP server stopped!', type=MsgType.PRIM_SYS)

def run_http(**kwargs):

    asyncio.run(prepare_thread(**kwargs))

if __name__ == '__main__':

    run_http()