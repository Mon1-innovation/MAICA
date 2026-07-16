from quart import Quart, request, jsonify, send_file, Response
from quart.views import View
import os
import asyncio
import json
import orjson
import traceback
import time
import uuid
import colorama
import logging

from werkzeug.datastructures import FileStorage
from hypercorn.config import Config
from hypercorn.asyncio import serve
from typing import *
from pydantic import BaseModel, Field, model_validator, field_validator, create_model

from maica.maica_ws import NoWsCoroutine
from maica.maica_utils import *
from maica.mtools import *

_CONNS_LIST = [
    'vector_pool',
    'embedding_conn',
    # Reranking is not required here
]
_WATCHES_LIST = [
    "mcore",
    "mfocus",
    "mvista",
    "mnerve",
    "embedding",
    "reranking",
]


# ====================================================== Initiation and registration ======================================================


def pkg_init_maica_http():
    global known_servers
    if int(G.A.FULL_RESTFUL):
        app.add_url_rule("/savefile", methods=['POST'], view_func=ShortConnHandler.as_view("upload_savefile"))
        app.add_url_rule("/savefile", methods=['DELETE'], view_func=ShortConnHandler.as_view("delete_savefile"))
        app.add_url_rule("/trigger", methods=['POST'], view_func=ShortConnHandler.as_view("upload_trigger"))
        app.add_url_rule("/trigger", methods=['DELETE'], view_func=ShortConnHandler.as_view("delete_trigger"))
        app.add_url_rule("/history", methods=['GET'], view_func=ShortConnHandler.as_view("download_history"))
        app.add_url_rule("/history", methods=['PUT'], view_func=ShortConnHandler.as_view("restore_history"))
        app.add_url_rule("/preferences", methods=['GET'], view_func=ShortConnHandler.as_view("download_preferences"))
        app.add_url_rule("/preferences", methods=['PATCH'], view_func=ShortConnHandler.as_view("edit_preferences"))
        app.add_url_rule("/preferences", methods=['POST'], view_func=ShortConnHandler.as_view("override_preferences"))
        app.add_url_rule("/register", methods=['GET', 'POST'], view_func=ShortConnHandler.as_view("download_token", val=False))
        app.add_url_rule("/legality", methods=['GET'], view_func=ShortConnHandler.as_view("check_legality"))
        app.add_url_rule("/vista", methods=['POST'], view_func=ShortConnHandler.as_view("upload_vista"))
        app.add_url_rule("/vista/list", methods=['GET'], view_func=ShortConnHandler.as_view("list_vista"))
        app.add_url_rule("/vista", methods=['DELETE'], view_func=ShortConnHandler.as_view("delete_vista"))
        app.add_url_rule("/vista", methods=['GET'], view_func=ShortConnHandler.as_view("download_vista", val=False))
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
        app.add_url_rule("/preferences/override", methods=['POST'], view_func=ShortConnHandler.as_view("override_preferences"))
        app.add_url_rule("/register", methods=['GET', 'POST'], view_func=ShortConnHandler.as_view("download_token", val=False))
        app.add_url_rule("/legality", methods=['GET'], view_func=ShortConnHandler.as_view("check_legality"))
        app.add_url_rule("/vista", methods=['POST'], view_func=ShortConnHandler.as_view("upload_vista"))
        app.add_url_rule("/vista/list", methods=['GET'], view_func=ShortConnHandler.as_view("list_vista"))
        app.add_url_rule("/vista/delete", methods=['POST'], view_func=ShortConnHandler.as_view("delete_vista"))
        app.add_url_rule("/vista", methods=['GET'], view_func=ShortConnHandler.as_view("download_vista", val=False))
        app.add_url_rule("/servers", methods=['GET'], view_func=ShortConnHandler.as_view("get_servers", val=False))
        app.add_url_rule("/accessibility", methods=['GET'], view_func=ShortConnHandler.as_view("get_accessibility", val=False))
        app.add_url_rule("/version", methods=['GET'], view_func=ShortConnHandler.as_view("get_version", val=False))
        app.add_url_rule("/workload", methods=['GET'], view_func=ShortConnHandler.as_view("get_workload", val=False))
        app.add_url_rule("/defaults", methods=['GET'], view_func=ShortConnHandler.as_view("get_defaults", val=False))
    app.add_url_rule("/<path>", methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'], view_func=ShortConnHandler.as_view("any_unknown", val=False))

    known_servers = json.loads(G.A.SERVERS_LIST)

app = Quart(import_name=__name__)
app.config['JSON_AS_ASCII'] = False
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024

quart_logger = logging.getLogger('hypercorn.error')
quart_logger.disabled = True

@app.before_request
def set_max_content_length():
    if request.endpoint == 'upload_vista':
        request.max_content_length = 32 * 1024 * 1024


# ====================================================== Initiation and registration ends ======================================================


# ====================================================== Utilities ======================================================


_MISSING = object()

def jfy_res(content=_MISSING):
    """I mean jsonify result."""
    d = {"success": True, "exception": None}
    if content is not _MISSING:
        d['content'] = content
    return jsonify(d)

# class BasicHttpRequest(BaseModel):
#     access_token: Optional[str] = None
#     chat_session: Optional[int] = Field(
#         default=None,
#         # Savefile and things could go 0
#         ge=0,
#         le=9,
#     )
#     content: Any = None

Fld = Type[Field]

def pyd_http_factory(
    model_postfix: str = "",
    access_token: Optional[Fld | Any] = (Optional[str], None),
    chat_session: Optional[Fld | Any] = (Optional[int], None),
    content: Optional[Fld | Any] = (Any, None),
    **kwargs,
) -> BaseModel:
    """Constructs pyd models, just to save some typing."""
    pyd_m = create_model(
        "_DynModel_" + model_postfix,
        access_token=access_token,
        chat_session=chat_session,
        content=content,
        **kwargs,
    )
    return pyd_m

# Again just to save some typing
_session_0_9 = (
    Optional[int],
    Field(
        default=0,
        ge=0,
        le=9,
    ),
)
_session_1_9 = (
    Optional[int],
    Field(
        ge=1,
        le=9,
    ),
)
def _conv_str_json(cls, v: str):
    if isinstance(v, str):
        v = orjson.loads(v)
    return v
_get_json = field_validator("content", mode="before")(_conv_str_json)


# ====================================================== Utilities ends ======================================================


# ====================================================== Handler initiation ======================================================



class ShortConnHandler(View):
    """Flask initiates it on every request."""
    init_every_request = True
    stem_inst: Optional[NoWsCoroutine]

    root_csc: ConnSocketsContainer = None
    """This should be filled in advance."""

    nvwatchers: ClassVar[list[NvWatcher]] = []
    """This is class managed."""

    def __init__(self, val=True):
        if not self.__class__.root_csc:
            raise RuntimeError("maica_http needs class-wide root_csc to work")

        self.val = val
        if val:
            rsc = RealtimeSocketsContainer()
            csc = self.__class__.root_csc.spawn_sub(rsc)
            self.fsc = FullSocketsContainer(rsc=rsc, csc=csc)

    def msg_http(self, *args, **kwargs):

        # By using this we ignore info coming from non-validate endpoints on terminal
        if self.val:
            sync_messenger(*args, **kwargs)

    async def dispatch_request(self, **kwargs):
        try:

            # If validation required, we spawn stem instance
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
            else:
                self.remote_addr = str(request.remote_addr)

            if self.stem_inst:
                self.stem_inst.remote_addr = self.remote_addr

            self.msg_http(info=f'Recieved request on API endpoint {endpoint}', type=MsgType.RECV)
            self.msg_http(info=f'From IP {self.remote_addr}', type=MsgType.DEBUG)
            result = await function_routed()

            # Printing
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

            _, _, message, _ = sync_messenger(error=ce)
            status_code = int(ce.error_code or 400)
            if not 400 <= status_code <= 599:
                status_code = 400
            return jsonify({"success": False, "exception": message}), status_code

        except Exception as e:
            traceback.print_exc()
            sync_messenger(info=f'Handler hit an exception: {str(e)}', type=MsgType.ERROR)
            message = (
                "A critical exception happened serverside, contact administrator"
                if int(G.A.NO_SEND_ERROR)
                else str(e)
            )
            return jsonify({"success": False, "exception": message}), 500

    async def wrapped_validate[T: BaseModel](
        self,
        model: Type[T],
        data: dict | list,
    ):
        """Specifically used for maica_http. It does login too."""
        if isinstance(data, dict) and not data.get("access_token"):
            authorization = request.headers.get("Authorization", "")
            scheme, _, token = authorization.partition(" ")
            if scheme.lower() == "bearer" and token:
                data = data | {"access_token": token}

        if isinstance(data, dict) and len(data.get("access_token", "")) > 4096:
            raise MaicaInputWarning("access_token is too long")

        try:
            query = model.model_validate(data)
        except Exception as e:
            raise MaicaInputWarning(f"Query parsing failed: {str(e)}")
        
        if self.val:
            await self.fsc.login(query.access_token)

        if getattr(query, 'chat_session', None) is not None:
            self.settings.temp.chat_session = query.chat_session

        return query


    # ====================================================== Handler initiation ends ======================================================


    # ====================================================== Utilizations ======================================================


    _sf_m = pyd_http_factory(
        model_postfix="sf_m",
        access_token=(str, ...),
        chat_session=_session_0_9,
        content=(dict, ...),
    )
    async def upload_savefile(self):
        """POST"""
        query = await self.wrapped_validate(self._sf_m, await request.get_json())

        async with acquire_dbo("persistent", self.fsc) as persistent:
            persistent.load(query.content)
            await persistent.to_db(skip_sync=True)
            await persistent.to_milvus()
 
        return jfy_res()
    

    _dsf_m = pyd_http_factory(
        model_postfix="dsf_m",
        access_token=(str, ...),
        chat_session=_session_0_9,
    )
    async def delete_savefile(self):
        """DELETE"""
        await self.wrapped_validate(self._dsf_m, await request.get_json())

        async with acquire_dbo("persistent", self.fsc) as persistent:
            persistent.clear()
            await persistent.to_db(skip_sync=True)
            await persistent.to_milvus(_data=[])
 
        return jfy_res()
        

    _tr_m = pyd_http_factory(
        model_postfix="tr_m",
        access_token=(str, ...),
        chat_session=_session_0_9,
        content=(list, ...),
    )
    async def upload_trigger(self):
        """POST"""
        query = await self.wrapped_validate(self._tr_m, await request.get_json())

        async with acquire_dbo("trigger", self.fsc) as trigger:
            trigger.load(query.content)
            await trigger.to_db(skip_sync=True)

        return jfy_res()
    

    _dtr_m = pyd_http_factory(
        model_postfix="tr_m",
        access_token=(str, ...),
        chat_session=_session_0_9,
    )
    async def delete_trigger(self):
        """DELETE"""
        await self.wrapped_validate(self._dtr_m, await request.get_json())

        async with acquire_dbo("trigger", self.fsc) as trigger:
            trigger.clear()
            await trigger.to_db(skip_sync=True)

        return jfy_res()


    _dlh_m = pyd_http_factory(
        model_postfix="dlh_m",
        access_token=(str, ...),
        chat_session=_session_1_9,
        content=(Optional[int], 0),
    )
    async def download_history(self):
        """GET"""
        query = await self.wrapped_validate(self._dlh_m, request.args.to_dict(flat=True))

        async with acquire_session(self.fsc) as session:
            # It reports 404 on empty
            data_j = session.json()

        n = query.content * 2

        if query.content == 0:
            pass

        else:
            prompt_obj = data_j.pop(0)
            if query.content > 0:
                data_j = data_j[:n]
            else:
                data_j = data_j[n:]
            data_j.insert(0, prompt_obj)

        data_str = orjson.dumps(data_j, option=orjson.OPT_SORT_KEYS).decode()
        pss_b64 = await asyncio.to_thread(sign_message, data_str)

        return jfy_res([pss_b64, data_j])


    _rsh_m = pyd_http_factory(
        model_postfix="rsh_m",
        access_token=(str, ...),
        chat_session=_session_1_9,
        content=(list, ...),
    )
    async def restore_history(self):
        """PUT"""
        query = await self.wrapped_validate(self._rsh_m, await request.get_json())

        pss_b64, data_j = query.content

        data_str = orjson.dumps(data_j, option=orjson.OPT_SORT_KEYS).decode()
        try:
            await asyncio.to_thread(verify_message, data_str, pss_b64)
        except ValueError:
            raise MaicaInputWarning("Sign does not match")

        async with acquire_session(self.fsc) as session:
            session.load(data_str)
            await session.to_db(skip_sync=True)

        return jfy_res()


    _dlp_m = pyd_http_factory(
        model_postfix="dlp_m",
        access_token=(str, ...),
        content=(Optional[Hashable], None),
    )
    async def download_preferences(self):
        """GET"""
        query = await self.wrapped_validate(self._dlp_m, request.args.to_dict(flat=True))

        async with DatabaseUtils.SessionData() as dbs:
            async with dbs.begin():

                obj = await sqla_get_or_create(
                    dbs,
                    SqlAccountStatus,
                    {"id": self.settings.verification.user_id},
                    requires=("preferences", ),
                )

        data_j = obj.preferences or {}

        if query.content is not None:
            v = data_j.get(query.content)
        else:
            v = data_j
        
        return jfy_res(v)


    _edp_m = pyd_http_factory(
        model_postfix="edp_m",
        access_token=(str, ...),
        content=(dict, ...),
    )
    async def edit_preferences(self):
        """PATCH"""
        query = await self.wrapped_validate(self._edp_m, await request.get_json())

        async with DatabaseUtils.SessionData() as dbs:
            async with dbs.begin():

                obj = await sqla_get_or_create(
                    dbs,
                    SqlAccountStatus,
                    {"id": self.settings.verification.user_id},
                    requires=("preferences", ),
                )

                if obj.preferences is None:
                    obj.preferences = {}
                obj.preferences.update(query.content)

                # Enforce write in case updated nested attributes
                obj.preferences.changed()

        return jfy_res()


    _ovp_m = pyd_http_factory(
        model_postfix="ovp_m",
        access_token=(str, ...),
        content=(dict, ...),
    )
    async def override_preferences(self):
        """POST"""
        query = await self.wrapped_validate(self._ovp_m, await request.get_json())

        async with DatabaseUtils.SessionData() as dbs:
            async with dbs.begin():

                await sqla_create_or_update(
                    dbs,
                    SqlAccountStatus,
                    {"id": self.settings.verification.user_id},
                    {"preferences": query.content},
                )

        return jfy_res()


    _dlt_m = pyd_http_factory(
        model_postfix="dlt_m",
        content=(dict, ...),
        __validators__={
            "get_json": _get_json
        },
    )
    async def download_token(self):
        """POST (legacy GET is also accepted), val=False."""
        data = (
            await request.get_json()
            if request.method == "POST"
            else request.args.to_dict(flat=True)
        )
        query = await self.wrapped_validate(self._dlt_m, data)

        crid_m = FscUsersFuncMixin.TokenCridential.model_validate(query.content)
        token = await crid_m.generate_token()

        return jfy_res(token)


    _ckl_m = pyd_http_factory(
        model_postfix="ckl_m",
        access_token=(str, ...),
        content=(Optional[dict], None),
        __validators__={
            "get_json": _get_json
        },
    )
    async def check_legality(self):
        """GET"""
        query = await self.wrapped_validate(self._ckl_m, request.args.to_dict(flat=True))

        if query.content:
            object = query.content.get("object")
            value = query.content.get("value")
            if not isinstance(object, str) or not isinstance(value, str):
                raise MaicaInputWarning("Legality content requires string object and value fields")
            if not 1 <= len(value) <= 256:
                raise MaicaInputWarning("Legality value length must be between 1 and 256")

            match object:
                case "geolocation":
                    locs = await name_to_loc(value)
                    loc = locs.results[0]
                    result = loc.model_dump()

                case _:
                    raise MaicaInputWarning(f"{object} is not valid choice")
                
        else:
            result = self.settings.verification.username

        return jfy_res(result)


    _ulv_m = pyd_http_factory(
        model_postfix="ulv_m",
        access_token=(str, ...),
        # Content is from request.file
    )
    async def upload_vista(self):
        """POST, multipart/form-data"""
        await self.wrapped_validate(self._ulv_m, (await request.form).to_dict(flat=True))
        file: FileStorage = (await request.files).get('content')
        if file is None:
            raise MaicaInputWarning("Missing image file in multipart field 'content'")
        keep = int(G.A.KEEP_MVISTA)
        if keep <= 0:
            raise MaicaPermissionWarning("MVista image storage is disabled on this server", 403)

        binary = await asyncio.to_thread(file.stream.read)
        img = await asyncio.to_thread(ImgByUuid, binary)
        await asyncio.to_thread(img.save)
        try:
            await img.register(self.settings.verification.user_id)
        except Exception:
            await asyncio.to_thread(img.delete)
            raise

        imgs = await ImgByUuid.load(self.settings.verification.user_id)
        for stale_img in imgs[keep:]:
            try:
                await asyncio.to_thread(stale_img.delete)
            except MaicaInputWarning:
                pass
            finally:
                await stale_img.unregister()

        return jfy_res(img.uuid)
    

    _lv_m = pyd_http_factory(
        model_postfix="lv_m",
        access_token=(str, ...),
    )
    async def list_vista(self):
        """GET"""
        await self.wrapped_validate(self._lv_m, request.args.to_dict(flat=True))

        imgs = await ImgByUuid.load(self.settings.verification.user_id)
        uuids = [
            img.uuid
            for img in imgs
        ]

        return jfy_res(uuids)


    _dv_m = pyd_http_factory(
        model_postfix="dv_m",
        access_token=(str, ...),
        content=(Optional[str | int], None),
    )
    async def delete_vista(self):
        """DELETE"""
        query = await self.wrapped_validate(self._dv_m, await request.get_json())

        ind = query.content
        owned_imgs = await ImgByUuid.load(self.settings.verification.user_id)
        if isinstance(ind, str):
            try:
                normalized_uuid = str(uuid.UUID(ind))
            except ValueError as exc:
                raise MaicaInputWarning("Image UUID is invalid") from exc
            imgs = [img for img in owned_imgs if img.uuid == normalized_uuid]
            if not imgs:
                raise MaicaPermissionWarning("Image does not belong to the authenticated user", 403)
        elif isinstance(ind, int):
            if ind < 0 or ind >= len(owned_imgs):
                raise MaicaInputWarning("Image index is out of range", 404)
            imgs = [owned_imgs[ind]]
        else:
            imgs = owned_imgs

        for img in imgs:
            try:
                await asyncio.to_thread(img.delete)
            except MaicaInputWarning:
                # Heal a stale metadata row even if its temporary file vanished.
                pass
            finally:
                await img.unregister()

        return jfy_res()


    _dlv_m = pyd_http_factory(
        model_postfix="dlv_m",
        content=(str, ...),
    )
    async def download_vista(self):
        """GET, val=False"""
        query = await self.wrapped_validate(self._dlv_m, request.args.to_dict(flat=True))

        img = await asyncio.to_thread(ImgByUuid, query.content)

        return await send_file(
            img.get_bio(),
            as_attachment=True,
            attachment_filename=img.file_name
        )


    async def get_servers(self):
        """GET, val=False"""
        return jfy_res(known_servers)
    

    async def get_accessibility(self):
        """GET, val=False"""
        accessibility = G.A.DEV_STATUS
        return jfy_res(accessibility)
    

    async def get_version(self):
        """GET, val=False"""
        curr_version, legc_version = G.A.CURR_VERSION, G.A.LEGC_VERSION
        blessland_capv = G.A.BLESSLAND_CAPV
        return jfy_res({"curr_version": curr_version, "legc_version": legc_version, "fe_blessland_version": blessland_capv})


    async def get_workload(self):
        """GET, val=False"""
        content = {}
        for watcher in self.__class__.nvwatchers:
            content |= watcher.get_statics_inside()

        content.update({"onliners": len(online_dict)})
        return jfy_res(content)
    

    async def get_defaults(self):
        """GET, val=False"""
        settings = MaicaSettings()
        content = (
            settings.basic.model_dump()
            | settings.extra.model_dump()
            | settings.super.model_dump()
        )
        return jfy_res(content)


    async def any_unknown(self):
        """Handles any unknown endpoint"""
        sync_messenger(info=f"An unknown access to {request.full_path} handled", type=MsgType.LOG)
        return jsonify({"success": False, "exception": 'Unknown request endpoint or method'}), 404


    # ====================================================== Utilizations ends ======================================================


async def prepare_thread(shutdown_trigger=None, **kwargs):

    # Construct csc first
    root_csc_kwargs = {k: kwargs.get(k) for k in _CONNS_LIST}
    root_csc = ConnSocketsContainer(**root_csc_kwargs)
    ShortConnHandler.root_csc = root_csc
            
    # Start watchers
    _watch_start_list = []
    ShortConnHandler.nvwatchers.clear()
    for i in _WATCHES_LIST:
        watcher = await NvWatcher.async_create(i, 'maica')
        ShortConnHandler.nvwatchers.append(watcher)

        _watch_start_list.append(asyncio.create_task(watcher.wrapped_main_watcher()))

    try:
        config = Config()
        config.bind = [f'{G.A.HTTP_HOST}:{int(G.A.HTTP_PORT)}']
        # Supplying the application-level trigger keeps Hypercorn from
        # replacing the process-wide SIGTERM handler installed by the starter.
        task = asyncio.create_task(
            serve(app, config, shutdown_trigger=shutdown_trigger)
        )

        task_list = [task] + _watch_start_list

        sync_messenger(info='MAICA HTTP server started!', type=MsgType.PRIM_SYS)

        done, pending = await asyncio.wait(task_list, return_when=asyncio.FIRST_COMPLETED)
        for completed in done:
            completed.result()

    except asyncio.CancelledError:
        raise
    except Exception as e:
        error = CommonMaicaError(str(e), '504')
        sync_messenger(error=error)
        raise

    finally:
        for running_task in [*locals().get('task_list', []), *_watch_start_list]:
            if not running_task.done():
                running_task.cancel()
        await asyncio.gather(
            *locals().get('task_list', []),
            *_watch_start_list,
            return_exceptions=True,
        )
        await asyncio.gather(
            *(watcher.close() for watcher in ShortConnHandler.nvwatchers),
            return_exceptions=True,
        )

        sync_messenger(info='MAICA HTTP server stopped!', type=MsgType.PRIM_SYS)


# ====================================================== Debuggings ======================================================


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
    sync_messenger(info='Individual MAICA HTTP server cleaning done', type=MsgType.DEBUG)

def run_http(**kwargs):
    asyncio.run(_run_http())

if __name__ == '__main__':
    run_http()
