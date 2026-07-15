import asyncio
import websockets
import time
import functools
import traceback
import colorama

from typing import *
from pydantic import TypeAdapter

from maica import mtools
from maica.maica_nows import NoWsCoroutine
from maica.mfocus import pre_core_pipelines
from maica.mtrigger import post_core_pipelines
from maica.maica_utils import *

_CONNS_LIST = [
    'vector_pool',
    'mcore_conn',
    'mfocus_conn',
    'mvista_conn',
    'mnerve_conn',
    'embedding_conn',
    'reranking_conn',
]

_Bt = BilingualText

class WsCoroutine(NoWsCoroutine):
    """
    Force ws existence.
    Also has AI sockets.
    """

    def __init__(
            self,
            fsc: FullSocketsContainer,
        ):
        super().__init__(fsc=fsc)


    # ====================================================== Stage 1 permission check ======================================================


    async def check_permit(self):

        # The ip part
        websocket = self.fsc.websocket
        xff = websocket.request.headers.get("X-Forwarded-For")
        if xff:
            self.remote_addr = xff.split(',')[0].strip()
        else:
            self.remote_addr = str(websocket.remote_address[0])

        sync_messenger(info=f'An anonymous connection initiated', type=MsgType.PRIM_LOG)
        sync_messenger(info=f'From IP {self.remote_addr}', type=MsgType.DEBUG)
        sync_messenger(info=f'Current online users: {list(online_dict.keys())}', type=MsgType.DEBUG)

        # Starting loop from here
        while True:
            try:

                # Initiation
                self.fsc.tracker_id.rotate()

                # Recieve text
                recv_text = await websocket.recv()
                # Validate text
                try:
                    ws_config: UnionStage1Settings = TypeAdapter(Stage1Settings).validate_json(recv_text)
                except Exception as e:
                    # We can test if it's caused by wrong stage
                    try:
                        sync_messenger(info=f'Recieved request on stage1', type=MsgType.DEBUG)
                        _ws_config: UnionStage2Settings = TypeAdapter(Stage2Settings).validate_json(recv_text)
                    except Exception as e2:
                        raise MaicaInputWarning(f"Query parsing failed: {str(e)}") from e
                    raise MaicaPermissionWarning(f"Query type {_ws_config.type} now allowed pre-auth")

                match ws_config.type:
                    case "sping":
                        pass
                    case "ping":
                        await self.fsc.messenger("pong", f"Ping recieved from anonymous and responded", 200)
                    case "auth":
                        sync_messenger(info=f'Recieved auth request on stage1: {colorama.Back.CYAN}{recv_text}{colorama.Back.RESET}', type=MsgType.RECV)
                        sync_messenger(info=f'From IP {self.remote_addr}', type=MsgType.DEBUG)

                        # The login procedure
                        await self.fsc.login(ws_config.access_token)

                        # Cookies are deprecated
                        sync_messenger(info=f'Authentication passed: {self.settings.verification.username}({self.settings.verification.user_id})', type=MsgType.LOG)
                        await self.fsc.messenger('maica_login_id', f"{self.settings.verification.user_id}", 200, no_print=True, no_track=True)
                        await self.fsc.messenger('maica_login_user', f"{self.settings.verification.username}", 200, no_print=True, no_track=True)
                        await self.fsc.messenger('maica_login_nickname', f"{self.settings.verification.nickname}", 200, no_print=True, no_track=True)

                        return {'id': self.settings.verification.user_id, 'username': self.settings.verification.username}

            # Handle expected exceptions
            except CommonMaicaException as ce:
                if ce.is_critical or ce.is_breaking:
                    raise
                else:
                    await self.fsc.messenger(error=ce)
                    # await messenger(websocket, 'maica_loop_warn_finished', 'Loop hit a user level exception, stopped and reset', 304)
                    continue


    # ====================================================== Stage 1 ends ======================================================


    # ====================================================== Stage 2 function router ======================================================


    # Yes nowadays we can actually merge the two stages into one
    # But since it's not necessary and this old way offers lower level control
    # We'll just leave it be
    async def function_switch(self):
        websocket = self.fsc.websocket
        
        # Announcements
        await self.fsc.messenger("maica_connection_established", "MAICA connection established", 201, type=MsgType.INFO, no_print=True)
        await self.fsc.messenger("maica_provider_anno", f"Current service provider is {G.A.DEV_IDENTITY or 'UNKNOWN'}", 200, type=MsgType.INFO, no_print=True)
        await self.fsc.messenger("maica_model_anno", f"Main model is {self.fsc.mcore_conn.model_actual}, MFocus model is {self.fsc.mfocus_conn.model_actual}", 200, type=MsgType.INFO, no_print=True)

        if self.fsc.mvista_conn:
            await self.fsc.messenger("maica_feature_mvista", f"MVista enabled on server, model is {self.fsc.mvista_conn.model_actual}", 200, type=MsgType.INFO, no_print=True)
        elif is_mcore_vl():
            await self.fsc.messenger("maica_feature_mvista", f"MVista enabled on server, using core model implementation", 200, type=MsgType.INFO, no_print=True)

        if self.fsc.mnerve_conn:
            await self.fsc.messenger("maica_feature_mnerve", f"MNerve enabled on server, model is {self.fsc.mnerve_conn.model_actual}", 200, type=MsgType.INFO, no_print=True)
        if self.fsc.is_vector_ready:
            await self.fsc.messenger("maica_feature_rag", f"MFocus RAG enabled on server, model is {self.fsc.embedding_conn.model_actual}", 200, type=MsgType.INFO, no_print=True)
        if self.fsc.is_reranking_ready:
            await self.fsc.messenger("maica_feature_reranker", f"MFocus reranking enabled on server, model is {self.fsc.reranking_conn.model_actual}", 200, type=MsgType.INFO, no_print=True)

        # Starting loop from here
        while True:
            try:

                # Per-loop cleanups
                self.fsc.tracker_id.rotate()
                self.settings.temp.reset()

                # Run common check, like banned or what
                await self.fsc.login()

                # Then we examine the input
                recv_text = await websocket.recv()
                try:
                    sync_messenger(info=f'Recieved request on stage2', type=MsgType.DEBUG)
                    ws_config: UnionStage2Settings = TypeAdapter(Stage2Settings).validate_json(recv_text)
                except Exception as e:
                    # We can test if it's caused by wrong stage
                    try:
                        _ws_config: UnionStage1Settings = TypeAdapter(Stage1Settings).validate_json(recv_text)
                    except Exception as e2:
                        raise MaicaInputWarning(f"Query parsing failed: {str(e)}") from e
                    raise MaicaPermissionWarning(f"Query type {_ws_config.type} not allowed post-auth")
                    
                match ws_config.type:
                    case "sping":
                        pass
                    case "ping":
                        await self.fsc.messenger("pong", f"Ping recieved from {self.settings.verification.username} and responded", 200)
                    case "reconn":
                        await self.fsc.messenger.exhaust_buffer()
                    case "params":
                        sync_messenger(info=f'Recieved params request on stage2: {recv_text}', type=MsgType.RECV)
                        sync_messenger(info=f'From IP {self.remote_addr}, user {self.settings.verification.username}', type=MsgType.DEBUG)
                        await self.change_settings(ws_config)
                    case "query":
                        sync_messenger(info=f'Recieved query request on stage2: {recv_text}', type=MsgType.RECV)
                        sync_messenger(info=f'From IP {self.remote_addr}, user {self.settings.verification.username}', type=MsgType.DEBUG)
                        await self.generate_response(ws_config)

                if ws_config.type in ("reconn", "params", "query"):
                    await self.fsc.messenger(
                        'maica_worker_loop_finished',
                        f'Finished worker loop, type {ws_config.type}',
                        200,
                        no_print=True,
                    )

            # Handle expected exceptions
            except CommonMaicaException as ce:
                if ce.is_critical or ce.is_breaking:
                    raise
                else:
                    await self.fsc.messenger(error=ce)
                    await self.fsc.messenger('maica_loop_warn_reset', 'Loop hit a user level exception, reset in stage 2', 400)
                    continue


    # ====================================================== Stage 2 ends ======================================================


    # ====================================================== Utilities ======================================================


    # Param setting section
    async def change_settings(self, ws_config: WsSettingsConfig):

        if ws_config.reset:
            self.settings.soft_reset()
            await self.fsc.messenger('maica_params_reset', f"Settings reset accepted", 200)
        
        try:
            accepted_params = self.settings.update_settings(**ws_config.chat_params)
        except CommonMaicaException as ce:
            raise
        except Exception as e:
            raise MaicaInputWarning(f"Settings unacceptable: {str(e)}") from e
        
        await self.fsc.messenger('maica_params_accepted', f"{accepted_params} out of {len(ws_config.chat_params)} settings accepted", 200)

    # Completion section
    async def generate_response(self, ws_config: WsQueryConfig):

        # Initiations
        websocket = self.fsc.websocket
        chat_session = self.settings.temp.chat_session = ws_config.chat_session

        async with (
            acquire_dbo("persistent", self.fsc) as sp,
            acquire_dbo("trigger", self.fsc) as st,
            acquire_session(self.fsc) as session,
        ):
            fdb1 = set()
            if chat_session >= 1:
                fdb1.add(session.from_db())
            
            # They're not required at all if just resetting session
            if not ws_config.reset:
                # We skip sp.from_db if sf_access is not enabled at all
                if self.settings.basic.savefile_access:
                    fdb1.add(sp.from_db())
                fdb1.add(st.from_db())

            await asyncio.gather(*fdb1)

            if ws_config.reset:
                # To archive first
                await session.to_entire_archive()

                # Clear and prepare to use
                session.clear()
                await session.to_db()

                await self.fsc.messenger(
                    "maica_session_reset",
                    "Determined chat_session reset",
                    204,
                )
                return

            user_query = MaicaSessionItem("user")
            user_query.context_from_fsc(self.fsc)
            session.append(user_query)

            match ws_config.activated:
                case "query":
                    if chat_session <= -1:
                        # Overrides it
                        session.load(ws_config.query)
                        user_query = session[-1]
                        str_query = user_query.content
                    else:
                        str_query = user_query.content = ws_config.query

                case "mspire":
                    self.settings.temp.activated = "mspire"
                    self.settings.temp.mspire.update(ws_config.inspire)
                    self.settings.temp.common.update(ws_config.inspire)
                    str_query = ", ".join(ws_config.inspire.title)

                case "mpostal":
                    self.settings.temp.activated = "mpostal"
                    self.settings.temp.mpostal.update(ws_config.postmail)
                    self.settings.temp.common.update(ws_config.postmail)
                    str_query = (ws_config.postmail.header or "") + ws_config.postmail.content

            # Acquire procedure already clears temp, so write here directly
            if ws_config.savefile:
                sp.content_temp = ws_config.savefile
            if ws_config.triggers:
                st.content_temp = ws_config.triggers

            # MVista
            if ws_config.vision:
                self.settings.temp.mvista.mv_imgs = ws_config.vision.root

            # Query censor
            if G.A.CENSOR_QUERY != '0':
                tolerance = int(G.A.CENSOR_QUERY)
                query_censor = await mtools.has_censored(str_query)

                if len(query_censor) >= tolerance:
                    sync_messenger(info=f"Query has censored words: {query_censor}", type=MsgType.WARN)
                    raise MaicaInputWarning("Input query has censored words or phrases", 403, "maica_input_query_censored")
                
                elif len(query_censor):
                    sync_messenger(info=f"Input query has censored words or phrases but ignored: {query_censor}", type=MsgType.DEBUG)

            # session knows session_num already when acquiring
            # Here we should start pre_core_pipeline
            await pre_core_pipelines(
                session=session,
                fsc=self.fsc,
                sp=sp,
                st=st,
            )

            # We update str_query here for ms and mp
            str_query = user_query.content

            # Construction part done, communication part started
            completion_args = {
                "input": session.utilize(),
                "stream": self.settings.use_stream_now,
                "extra_body": {},
            }

            # Super params apply
            if self.settings.super_writable:
                super_args = self.settings.super.model_copy()

                if self.settings.temp.common.twk_super:
                    super_args.presence_penalty = 1.0 - (1.0 - super_args.presence_penalty) * (2/3)

            else:
                super_args = MaicaSettings.Super()

            completion_args.update(super_args.model_dump())

            # Enforce lang (guided regex)
            if self.settings.extra.gen_enforce_lang:
                if self.settings.basic.target_lang == 'en':
                    completion_args['extra_body']["structured_outputs"] = {"regex": r"^[^\u4e00-\u9fa5]*$"}

            # Add context log
            previous_rnds = session.utilize(text_only=True)[1:]
            previous_rnds_len = int(len(previous_rnds) / 2)
            previous_rnds_ellipsed = previous_rnds[-6:]

            previous_rnds_str = '\n'.join(
                [
                    (('Q: ' if d['role'] == 'user' else 'A: ') + d['content'])
                    for d in previous_rnds_ellipsed
                ]
            )

            if previous_rnds_len > 3:
                previous_rnds_str = '... ...\n' + previous_rnds_str

            if previous_rnds_len:
                sync_messenger(info=f'\nQuery has {previous_rnds_len} rounds of history:\n{previous_rnds_str}\nEnd of query history', type=MsgType.RECV)

            sync_messenger(info=f'\nQuery constructed and ready to go, last input is:\n{str_query}\nSending query...', type=MsgType.PRIM_RECV)

            # By default, pprt is disabled on non-streaming output
            if (
                not "pprt" in ws_config.model_fields_set
                and not self.settings.use_stream_now
            ):
                ws_config.pprt = False

            pprt_processor = mtools.PPRTProcessor(self.fsc, ws_config.pprt)

            # From now on, we add try finally block to ensure release_buffer called
            try:

                # We're about to start generation, so any ws interrupts should be handled by buffered_messenger from now.
                await self.fsc.messenger(
                    "maica_mcore_gen_start",
                    "Core model generation starting, reconn protection intervening",
                    201,
                )
                await self.fsc.messenger.acquire_buffer()

                reply_joined = ''
                seq = 0

                async def send_delta(delta):
                    nonlocal reply_joined, seq
                    await self.fsc.messenger('maica_core_streaming_continue', delta, 100)
                    reply_joined += delta
                    seq += 1

                # If not skipping generation, we generate it ofc
                if not self.settings.skip_generation:

                    # Starting generation
                    conn = self.fsc.mcore_conn
                    async with llm_request(conn, **completion_args) as (task, a_reasoning, a_content, a_tool_calls):

                        async for content_delta in a_content:
                            await asyncio.sleep(0)
                            content_delta: Optional[str] = await pprt_processor.store_and_split(content_delta)
                            if content_delta:
                                await send_delta(content_delta)

                        content_left = await pprt_processor.exaust_and_split()
                        for content_delta in content_left:
                            await send_delta(content_delta)

                        # Apply correct linewarp on terminal
                        sync_messenger(info='\n', type=MsgType.PLAIN)
                        await self.fsc.messenger(
                            'maica_core_complete',
                            f'Streaming finished for {self.settings.verification.username}, {seq} packets sent',
                            1000,
                        )

                # If skipping generation, we get result from skip_generation and just send it
                else:

                    await send_delta(self.settings.skip_generation)

                    sync_messenger(info='\n', type=MsgType.PLAIN)
                    await self.fsc.messenger(
                        'maica_core_complete',
                        f'Streaming finished (from cache) for {self.settings.verification.username}, {seq} packets sent',
                        1000,
                    )

                # Can be post-processed here
                session.append(MaicaSessionItem("assistant", reply_joined))

                # Here we should start post_core_pipelines
                await post_core_pipelines(
                    session=session,
                    fsc=self.fsc,
                    sp=sp,
                    st=st,
                )

                await self.fsc.messenger(
                    'maica_chat_loop_finished',
                    f'Finished chat loop from {self.settings.verification.username}',
                    200,
                    type=MsgType.INFO,
                )

            finally:
                # Recycle messenger buffer
                await self.fsc.messenger.release_buffer()


    # ====================================================== Utilities ends ======================================================


# ====================================================== Per-connection driver ======================================================


# Main app driver, runs per-connection
async def main_logic(
        websocket: websockets.ServerConnection,
        root_csc: ConnSocketsContainer,
    ):

    # Initializing
    rsc = RealtimeSocketsContainer(websocket=websocket)
    csc = root_csc.spawn_sub(rsc)
    fsc = FullSocketsContainer(rsc=rsc, csc=csc)
    
    unique_lock = asyncio.Lock()
    async with unique_lock:
        try:

            # This tiny welcome
            sentence_of_the_day = SentenceOfTheDay().get_sentence()
            await fsc.messenger(
                'maica_connection_initiated',
                sentence_of_the_day,
                200,
                type=MsgType.INFO,
                no_print=True,
            )

            thread_instance = await WsCoroutine.async_create(
                fsc,
            )

            # This is stage 1
            permit = await thread_instance.check_permit()
            assert permit['id'], permit

            # Lock login status
            online_dict[permit['id']] = [thread_instance.fsc, unique_lock]
            sync_messenger(info=f"Locking session for {permit['id']} named {permit['username']}", type=MsgType.LOG)

            # Runs until break
            await thread_instance.function_switch()
        
        except CommonMaicaException as ce:

            # We print original info if is critical
            if ce.is_critical:
                traceback.print_exc()

            await fsc.messenger(error=ce)

        except websockets.WebSocketException as we:

            try:
                we_code, we_reason = we.code, we.reason
                sync_messenger(info=f'Connection closed with {we_code}: {we_reason or 'No reason provided'}', type=MsgType.PRIM_LOG)

            except Exception:
                sync_messenger(info=f'Connection establishment failed: {str(we)}', type=MsgType.PRIM_LOG)

        except Exception as e:

            # We should catch and convert all expected issues in procedure
            # So unconverted exceptions are treated as errors
            traceback.print_exc()
            await fsc.messenger(
                'maica_uncaught_exception',
                f'Coroutine broke by an unknown exception: {str(e)}',
                500,
            )

        # Cleanups
        finally:
            try:
                online_dict.pop(permit['id'])
                sync_messenger(info=f"Lock released for {permit['username']}({permit['id']})", type=MsgType.LOG)

            except Exception as e:
                # Should just be caused by not locked yet
                sync_messenger(info=f"No lock for this connection", type=MsgType.DEBUG)
                
            await websocket.close()
            await websocket.wait_closed()
            sync_messenger(info=f"Closing connection gracefully", type=MsgType.DEBUG)


# ====================================================== Per-connection driver ends ======================================================


# ====================================================== Task starter ======================================================


async def prepare_thread(**kwargs):

    # Construct csc first
    root_csc_kwargs = {
        k: kwargs.get(k)
        for k in _CONNS_LIST
    }
    root_csc = ConnSocketsContainer(**root_csc_kwargs)

    sync_messenger(info='MAICA WS server started!' if G.A.DEV_STATUS == 'serving' else 'MAICA WS server started in development mode!', type=MsgType.PRIM_SYS)

    try:
        models_info = "\n"
        models_info += f"Main model: {root_csc.mcore_conn.model_actual}\n"
        models_info += f"MFocus model: {root_csc.mfocus_conn.model_actual}\n"

        if root_csc.mvista_conn:
            models_info += f"MVista model: {root_csc.mvista_conn.model_actual}\n"
        else:
            if is_mcore_vl():
                models_info += f"MVista model: Native implementation\n"
            else:
                models_info += f"MVista model: Disabled\n"

        if root_csc.mnerve_conn:
            models_info += f"MNerve model: {root_csc.mnerve_conn.model_actual}\n"
        else:
            models_info += f"MNerve model: Disabled\n"

        models_info += "\n"

        if root_csc.vector_pool:
            models_info += f"Vector database: Enabled\n"
        else:
            models_info += f"Vector database: Disabled\n"

        if root_csc.embedding_conn:
            models_info += f"Embedding model: {root_csc.embedding_conn.model_actual}\n"
        else:
            models_info += f"Embedding model: Disabled\n"

        if root_csc.reranking_conn:
            models_info += f"Reranking model: {root_csc.reranking_conn.model_actual}\n"
        else:
            models_info += f"Reranking model: Disabled\n"

        models_info = models_info.rstrip("\n")

        sync_messenger(info=models_info, type=MsgType.PRIM_LOG)

    except Exception as e:

        sync_messenger(info=f"Major model deployment cannot be reached: {str(e)}, running in minimal testing mode", type=MsgType.SYS)
    
    try:
        server = await websockets.serve(
            functools.partial
            (
                main_logic,
                root_csc=root_csc,
            ),
            '0.0.0.0',
            5000,
            max_size=64*1024
        )
        await server.wait_closed()

    except Exception as e:
        error = CommonMaicaError(str(e), '504')
        sync_messenger(error=error)

    finally:
        sync_messenger(info='MAICA WS server stopped!', type=MsgType.PRIM_SYS)


# ====================================================== Task starter ends ======================================================


# ====================================================== Debuggings ======================================================


async def _run_ws():
    """
    Notice: these only happen running individually!
    Use prepare_thread() for lower level control.
    """
    from maica import init
    init()
    _root_csc_items = [getattr(ConnUtils, k)() for k in _CONNS_LIST]
    root_csc_items = await asyncio.gather(*_root_csc_items)
    root_csc_kwargs = dict(zip(_CONNS_LIST, root_csc_items))

    task = asyncio.create_task(prepare_thread(**root_csc_kwargs))
    await task

    close_list = []
    for conn in root_csc_items:
        close_list.append(conn.close())
    await asyncio.gather(*close_list)
    sync_messenger(info='Individual MAICA WS server cleaning done', type=MsgType.DEBUG)

def run_ws():
    asyncio.run(_run_ws())

if __name__ == '__main__':
    run_ws()