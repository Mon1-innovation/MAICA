from quart import Quart, request, jsonify, send_file, Response
from quart.views import View
import os
import asyncio
import json
import traceback
import time
import uuid
import colorama
import logging

from werkzeug.datastructures import FileStorage
from hypercorn.config import Config
from hypercorn.asyncio import serve
from typing import *

from maica.maica_ws import NoWsCoroutine
from maica.maica_utils import *
from maica.mtools import *

_CONNS_LIST = ['auth_pool', 'maica_pool', 'mnerve_conn']
_WATCHES_DICT = {
    "mcore": "MCORE_ADDR",
    "mfocus": "MFOCUS_ADDR",
    "mvista": "MVISTA_ADDR",
    "mnerve": "MNERVE_ADDR",
}

def pkg_init_maica_http():
    global KNOWN_SERVERS
    if G.A.FULL_RESTFUL == '1':
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
        app.add_url_rule("/emotion", methods=['GET'], view_func=ShortConnHandler.as_view("normalize_emo"))
        app.add_url_rule("/vista", methods=['POST'], view_func=ShortConnHandler.as_view("upload_vista"))
        app.add_url_rule("/vista", methods=['DELETE'], view_func=ShortConnHandler.as_view("delete_vista"))
        app.add_url_rule("/vista", methods=['GET'], view_func=ShortConnHandler.as_view("download_vista"))
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
        app.add_url_rule("/emotion", methods=['GET'], view_func=ShortConnHandler.as_view("normalize_emo"))
        app.add_url_rule("/vista", methods=['POST'], view_func=ShortConnHandler.as_view("upload_vista"))
        app.add_url_rule("/vista/delete", methods=['POST'], view_func=ShortConnHandler.as_view("delete_vista"))
        app.add_url_rule("/vista", methods=['GET'], view_func=ShortConnHandler.as_view("download_vista"))
        app.add_url_rule("/servers", methods=['GET'], view_func=ShortConnHandler.as_view("get_servers", val=False))
        app.add_url_rule("/accessibility", methods=['GET'], view_func=ShortConnHandler.as_view("get_accessibility", val=False))
        app.add_url_rule("/version", methods=['GET'], view_func=ShortConnHandler.as_view("get_version", val=False))
        app.add_url_rule("/workload", methods=['GET'], view_func=ShortConnHandler.as_view("get_workload", val=False))
        app.add_url_rule("/defaults", methods=['GET'], view_func=ShortConnHandler.as_view("get_defaults", val=False))
    app.add_url_rule("/<path>", methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'], view_func=ShortConnHandler.as_view("any_unknown", val=False))

    try:
        KNOWN_SERVERS = json.loads(G.A.SERVERS_LIST)
    except Exception as e:
        sync_messenger(info=f'Loading servers list failed: {str(e)}', type=MsgType.ERROR)
        KNOWN_SERVERS = False

app = Quart(import_name=__name__)
app.config['JSON_AS_ASCII'] = False
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024

quart_logger = logging.getLogger('hypercorn.error')
quart_logger.disabled = True

class ShortConnHandler(View):
    """Flask initiates it on every request."""
    init_every_request = True
    stem_inst: Optional[NoWsCoroutine]

    root_csc: ConnSocketsContainer = None
    """Don't forget to implement at first!"""

    nvwatchers: list[NvWatcher] = []

    def __init__(self, val=True):
        self.val = val
        if val:
            rsc = RealtimeSocketsContainer()
            csc = self.__class__.root_csc.spawn_sub(rsc) if self.__class__.root_csc else ConnSocketsContainer()
            self.fsc = FullSocketsContainer(rsc, csc)
            
            self.maica_pool = self.fsc.maica_pool
            self.remote_addr = None

    def msg_http(self, *args, **kwargs):
        if self.val:
            sync_messenger(*args, **kwargs)

    @staticmethod
    def jfy_res(content=None):
        """I mean jsonify result."""
        d = {"success": True, "exception": None}
        if content:
            d['content'] = content
        return jsonify(d)

    async def dispatch_request(self, **kwargs):
        try:
            if self.val:
                self.stem_inst = await NoWsCoroutine.async_create(self.fsc)
                self.settings = self.fsc.maica_settings
            else:
                self.stem_inst = None
                self.settings = None
            endpoint = request.endpoint
            function_routed = getattr(self, endpoint)

            xff = request.headers.get('X-Forwarded-For')
            if xff:
                self.remote_addr = xff.split(',')[0].strip()
                if self.stem_inst:
                    self.stem_inst.remote_addr = self.remote_addr

            self.msg_http(info=f'Recieved request on API endpoint {endpoint}', type=MsgType.RECV)
            self.msg_http(info=f'From IP {self.remote_addr}', type=MsgType.DEBUG)
            result = await function_routed()

            if isinstance(result, Response):
                result_json = await result.get_json()
                if result_json:
                    d = {"success": result_json.get('success'), "exception": result_json.get('exception')}
                    if "content" in result_json:
                        d["content"] = ellipsis_str(result_json.get('content'), limit=65)
                    self.msg_http(info=f'Return value: {str(d)}', type=MsgType.SYS)
                else:
                    self.msg_http(info='A non-json response has been made', type=MsgType.SYS)

            return result

        except CommonMaicaException as ce:
            if ce.is_critical:
                traceback.print_exc()
            await messenger(error=ce, no_raise=True)
            return jsonify({"success": False, "exception": str(ce)}), int(ce.error_code) or 400

        except Exception as e:
            await messenger(info=f'Handler hit an exception: {str(e)}', type=MsgType.WARN)
            return jsonify({"success": False, "exception": str(e)}), 400

    async def validate_http(self, raw_data: Union[str, dict], must: Optional[list]=None) -> dict:
        must = must or []
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
        valid_data = await self.validate_http(json_data, must=['access_token', 'chat_session', 'content'])

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

        return self.jfy_res()
    
    async def delete_savefile(self):
        """DELETE"""
        json_data = await request.get_json()
        valid_data = await self.validate_http(json_data, must=['access_token', 'chat_session'])

        chat_session = valid_data.get('chat_session')

        sql_expression_1 = "DELETE FROM persistents WHERE user_id = %s AND chat_session_num = %s"
        await self.maica_pool.query_modify(sql_expression_1, (self.settings.verification.user_id, chat_session))

        return self.jfy_res()
        
    async def upload_trigger(self):
        """POST"""
        json_data = await request.get_json()
        valid_data = await self.validate_http(json_data, must=['access_token', 'chat_session', 'content'])

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

        return self.jfy_res()
    
    async def delete_trigger(self):
        """DELETE"""
        json_data = await request.get_json()
        valid_data = await self.validate_http(json_data, must=['access_token', 'chat_session'])

        chat_session = valid_data.get('chat_session')

        sql_expression_1 = "DELETE FROM triggers WHERE user_id = %s AND chat_session_num = %s"
        await self.maica_pool.query_modify(sql_expression_1, (self.settings.verification.user_id, chat_session))

        return self.jfy_res()
   
    async def download_history(self):
        """GET"""
        json_data = request.args.to_dict(flat=True)
        valid_data = await self.validate_http(json_data, must=['access_token', 'chat_session'])

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
            history_final_str = json.dumps(history_final_json, ensure_ascii=False, sort_keys=True)
            sigb64 = await wrap_run_in_exc(None, sign_message, history_final_str)
            return self.jfy_res([sigb64, history_final_json])
        else:
            return self.jfy_res([])

    async def restore_history(self):
        """PUT"""
        json_data = await request.get_json()
        valid_data = await self.validate_http(json_data, must=['access_token', 'chat_session', 'content'])

        chat_session = valid_data.get('chat_session')
        assert 1 <= chat_session < 10, "chat_session out of bound"
        content = valid_data.get('content')

        sigb64, history_json = content
        assert (await wrap_run_in_exc(None, verify_message, json.dumps(history_json, ensure_ascii=False, sort_keys=True), sigb64)), "Signature mismatch"
        await self.stem_inst.restore_chat_session(history_json, chat_session)

        return self.jfy_res()

    async def download_preferences(self):
        """GET"""
        json_data = request.args.to_dict(flat=True)
        valid_data = await self.validate_http(json_data, must=['access_token'])

        preferences_json = await self.stem_inst.hasher.check_user_status(pref=True)

        return self.jfy_res(preferences_json)

    async def edit_preferences(self):
        """PATCH"""
        json_data = await request.get_json()
        valid_data = await self.validate_http(json_data, must=['access_token', 'content'])

        preferences_json = await self.stem_inst.hasher.check_user_status(pref=True)

        content = valid_data.get('content')
        assert isinstance(content, dict), "Request content invalid" 
        preferences_json.update(content)
        await self.validate_http(preferences_json)

        await self.stem_inst.hasher.write_user_status(enforce=True, pref=True, **preferences_json)
        return self.jfy_res()

    async def delete_preferences(self):
        """DELETE"""
        json_data = await request.get_json()
        valid_data = await self.validate_http(json_data, must=['access_token', 'content'])

        preferences_json = await self.stem_inst.hasher.check_user_status(pref=True)

        content = valid_data.get('content')
        assert isinstance(content, list), "Request content invalid" 
        for key in content:
            preferences_json.pop(key)

        await self.stem_inst.hasher.write_user_status(enforce=True, pref=True, **preferences_json)
        return self.jfy_res()

    async def reset_preferences(self):
        """POST"""
        json_data = await request.get_json()
        valid_data = await self.validate_http(json_data, must=['access_token'])

        await self.stem_inst.hasher.write_user_status(enforce=True, pref=True)
        return self.jfy_res()
        
    # async def control_preferences(self):
    #     """read->GET, write->PATCH, delete->DELETE, reset->POST"""
    #     try:
    #         json_data = request.args.to_dict(flat=True) if request.method == 'GET' else await request.get_json()
    #         must = ['access_token'] if request.method in ['GET', 'POST'] else ['access_token', 'content']
    #         valid_data = await self.validate_http(json_data, must=must)

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
        valid_data = await self.validate_http(json_data, must=['content'])

        content = json.loads(valid_data.get('content'))

        cridential_type = 'username' if content.get('username') else 'email'
        cridential = content.get(cridential_type)
        password = content.get('password')
        assert isinstance(cridential, str) and isinstance(password, str), "Request content invalid"

        unencrypted_token = json.dumps({cridential_type: cridential, "password": password}, ensure_ascii=False)
        encrypted_token = await wrap_run_in_exc(None, encrypt_token, unencrypted_token)
        return self.jfy_res(encrypted_token)

    async def check_legality(self):
        """GET"""
        json_data = request.args.to_dict(flat=True)
        valid_data = await self.validate_http(json_data, must=['access_token'])

        try:
            content = json.loads(valid_data.get('content'))
        except:
            content = None

        if not content:
            result = self.settings.verification.username
        else:
            object = content.get('object')
            value = content.get('value')
            assert object and value, 'Empty in input'
            match object:
                case 'geolocation':
                    res = await weather_api_get(value)
                    result = res

                case _:
                    raise MaicaInputWarning(f"'{object}' is not valid object")

        return self.jfy_res(result)

    async def normalize_emo(self):
        """GET"""
        json_data = request.args.to_dict(flat=True)
        valid_data = await self.validate_http(json_data, must=['access_token', 'content'])

        content = json.loads(valid_data.get('content'))

        proc_type: Literal['norm', 'add'] = content.get('type') or 'norm'
        proc_lang: Literal['zh', 'en'] = content.get('target_lang') or 'zh'
        emo = content.get('text')
        
        if proc_type == 'norm':
            result = await emo_proc_auto(emo, proc_lang, self.fsc.mnerve_conn)
        else:
            result = await emo_proc_llm(emo, proc_lang, self.fsc.mnerve_conn)

        return self.jfy_res(result)

    async def upload_vista(self):
        """POST, multipart/form-data"""
        json_data = (await request.form).to_dict()
        valid_data = await self.validate_http(json_data, must=['access_token'])

        file: FileStorage = (await request.files).get('content')

        img_uuid = await self.stem_inst.store_mv(file.stream.read())

        return self.jfy_res(img_uuid)
    
    async def delete_vista(self):
        """DELETE"""
        json_data = await request.get_json()
        valid_data = await self.validate_http(json_data, must=['access_token'])

        content = valid_data.get('content')

        await self.stem_inst.delete_mv(content)
        return self.jfy_res()
    
    async def download_vista(self):
        """GET"""
        json_data = request.args.to_dict(flat=True)
        try:
            # Predicted trying to download img
            valid_data = await self.validate_http(json_data, must=['content'])
            content = valid_data.get('content')

            uuid: str = content
            processing_img = ProcessingImg(uuid)

            return_bio = processing_img.to_bio()
            file_name = processing_img.file_name

            return await send_file(
                return_bio,
                as_attachment=True,
                attachment_filename=file_name
            )
        except Exception as e:
            # Trying to get img list
            try:
                valid_data = await self.validate_http(json_data, must=['access_token'])
                result = await self.stem_inst.list_user_mv()
                return self.jfy_res(result)
            except Exception as e2:
                if isinstance(valid_data, dict) and valid_data.get('content'):
                    raise MaicaInputWarning(f"File {valid_data.get('content')}.jpg not exist", '404') from e
                else:
                    raise e2

    async def get_servers(self):
        """GET, val=False"""
        return self.jfy_res(KNOWN_SERVERS)
    
    async def get_accessibility(self):
        """GET, val=False"""
        accessibility = G.A.DEV_STATUS
        return self.jfy_res(accessibility)
    
    async def get_version(self):
        """GET, val=False"""
        curr_version, legc_version = G.A.CURR_VERSION, G.A.LEGC_VERSION
        blessland_capv = G.A.BLESSLAND_CAPV
        return self.jfy_res({"curr_version": curr_version, "legc_version": legc_version, "fe_blessland_version": blessland_capv})

    async def get_workload(self):
        """GET, val=False"""
        content = {}
        for watcher in self.__class__.nvwatchers:
            content |= watcher.get_statics_inside()

        content.update({"onliners": len(online_dict)})
        return self.jfy_res(content)
    
    async def get_defaults(self):
        """GET, val=False"""
        settings = MaicaSettings()
        content = {}
        content.update(settings.basic.default())
        content.update(settings.extra.default())
        content.update(settings.super.default())
        return self.jfy_res(content)

    async def any_unknown(self):
        """Handles any unknown endpoint"""
        await messenger(info=f"An unknown access to {request.full_path} handled", type=MsgType.WARN)
        return jsonify({"success": False, "exception": 'Unknown request endpoint or method'}), 404

async def prepare_thread(**kwargs):

    # Construct csc first
    root_csc_kwargs = {k: kwargs.get(k) for k in _CONNS_LIST}
    root_csc = ConnSocketsContainer(**root_csc_kwargs)
    ShortConnHandler.root_csc = root_csc

    await messenger(info='MAICA HTTP server started!', type=MsgType.PRIM_SYS)

    # Construct watchers
    watch_addrs = {}
    for k, v in _WATCHES_DICT.items():
        host = get_host(getattr(G.A, v))
        if host and not k in watch_addrs:
            watch_addrs[k] = host
            
    _watch_start_list = []
    for k, _ in watch_addrs.items():
        watcher = await NvWatcher.async_create(k, 'maica')
        ShortConnHandler.nvwatchers.append(watcher)
        _watch_start_list.append(asyncio.create_task(watcher.wrapped_main_watcher()))

    try:
        config = Config()
        config.bind = ['0.0.0.0:6000']
        task = asyncio.create_task(serve(app, config))
        task_list = [task] + _watch_start_list
        await asyncio.wait(task_list, return_when=asyncio.FIRST_COMPLETED)
    except BaseException as be:
        if isinstance(be, Exception):
            error = CommonMaicaError(str(be), '504')
            await messenger(error=error, no_raise=True)
    finally:

        # Normally maica_http should be the first one (possibly only one) to
        # respond to the original SIGINT.

        # So its stop msg will be print first, adding \n after ^C to look prettier.

        await messenger(info='\n', type=MsgType.PLAIN)
        await messenger(info='MAICA HTTP server stopped!', type=MsgType.PRIM_SYS)

async def _run_http():
    from maica import init
    init()
    pkg_init_maica_http()
    _root_csc_items = [getattr(ConnUtils, k)() for k in _CONNS_LIST]
    root_csc_items = await asyncio.gather(*_root_csc_items)
    root_csc_kwargs = dict(zip(_CONNS_LIST, root_csc_items))

    task = asyncio.create_task(prepare_thread(**root_csc_kwargs))
    await task

    close_list = []
    for conn in root_csc_items:
        close_list.append(conn.close())
    await asyncio.gather(*close_list)
    await messenger(info='Individual MAICA HTTP server cleaning done', type=MsgType.DEBUG)

def run_http(**kwargs):
    asyncio.run(_run_http())

if __name__ == '__main__':
    run_http()