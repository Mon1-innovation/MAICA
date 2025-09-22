import asyncio
import websockets
import time
import functools
import json
import uuid
import traceback
import colorama

from typing import *

from maica import mtools
from maica.maica_nows import NoWsCoroutine
from maica.maica_utils import *

# For imports
_onliners = {}

class WsCoroutine(NoWsCoroutine):
    """
    Force ws existence.
    Also has AI sockets.
    """

    def __init__(self, websocket, auth_pool: DbPoolCoroutine, maica_pool: DbPoolCoroutine, mcore_conn: AiConnCoroutine, mfocus_conn: AiConnCoroutine, online_dict: dict):
        super().__init__(auth_pool=auth_pool, maica_pool=maica_pool, websocket=websocket)
        self.online_dict = online_dict

        self.fsc.rsc.websocket = websocket
        if mcore_conn and mfocus_conn:
            mcore_conn.init_rsc(self.fsc.rsc); mfocus_conn.init_rsc(self.fsc.rsc)
        self.mcore_conn, self.mfocus_conn = mcore_conn, mfocus_conn
        self.fsc.mcore_conn, self.fsc.mfocus_conn = mcore_conn, mfocus_conn

    # Stage 1 permission check
    async def check_permit(self):
        websocket = self.websocket
        await messenger(info='An anonymous connection initiated', type=MsgType.PRIM_LOG)
        await messenger(info=f'Current online users: {list(self.online_dict.keys())}', type=MsgType.DEBUG)

        # Starting loop from here
        while True:
            try:

                # Initiation
                self.flush_traceray()
                self.settings.identity.reset()
                self.settings.verification.reset()

                recv_text = await websocket.recv()
                await messenger(info=f'Recieved an input on stage1', type=MsgType.RECV)
                recv_loaded_json = await validate_input(recv_text, 4096, self.fsc.rsc, must=['access_token'])

                login_success = await self.hash_and_login(recv_loaded_json['access_token'], check_online=True)
                if login_success:

                    # From here we can assume the user has logged in successfully
                    self.cookie = cookie = str(uuid.uuid4())
                    self.enforce_cookie = False

                    await self.populate_auxiliary_inst()

                    await messenger(info=f'Authentication passed: {self.settings.verification.username}({self.settings.verification.user_id})', type=MsgType.LOG)
                    await messenger(websocket, 'maica_login_id', f"{self.settings.verification.user_id}", '200', no_print=True)
                    await messenger(websocket, 'maica_login_user', f"{self.settings.verification.username}", '200', no_print=True)
                    await messenger(websocket, 'maica_login_nickname', f"{self.settings.verification.nickname}", '200', no_print=True)
                    await messenger(websocket, 'maica_connection_security_cookie', cookie, '200', no_print=True)

                    return {'id': self.settings.verification.user_id, 'username': self.settings.verification.username}

            # Handle expected exceptions
            except CommonMaicaException as ce:
                if ce.is_critical or ce.is_breaking:
                    raise ce
                else:
                    await messenger(websocket, error=ce, no_raise=True)
                    continue
    
    # Stage 2 function router
    async def function_switch(self):

        # Initiation
        websocket, mcore_conn = self.websocket, self.mcore_conn

        await messenger(websocket, "maica_connection_established", "MAICA connection established", "201", type=MsgType.INFO, no_print=True)
        await messenger(websocket, "maica_provider_anno", f"Current service provider is {load_env('MAICA_DEV_IDENTITY') or 'UNKNOWN'}", "200", type=MsgType.INFO, no_print=True)
        await messenger(websocket, "maica_model_anno", f"Main model is {self.mcore_conn.model_actual}, MFocus model is {self.mfocus_conn.model_actual}", "200", type=MsgType.INFO, no_print=True)

        # Starting loop from here
        while True:
            try:

                # Initiation
                self.flush_traceray()
                return_status = 0

                # Resets
                self.settings.temp.reset()

                # Context security check first
                await self.hash_and_login(logged_in_already=True)

                # Then we examine the input
                recv_text = await websocket.recv()
                await messenger(info=f'Recieved an input on stage2: {recv_text}', type=MsgType.RECV)
                recv_loaded_json = await validate_input(recv_text, 4096, self.fsc.rsc, warn=['type'])

                recv_type = recv_loaded_json.get('type', 'unknown')

                # Handle this cookie thing
                if recv_loaded_json.get('cookie'):
                    if str(recv_loaded_json['cookie']) == self.cookie:
                        if not self.enforce_cookie:
                            await messenger(websocket, "security_cookie_accepted", "Cookie verification passed, enabling strict mode", "200", no_print=True)
                            self.enforce_cookie = True
                        else:
                            await messenger(websocket, "security_cookie_correct", "Cookie verification passed", "200", no_print=True)
                    else:
                        raise MaicaPermissionError('Cookie provided but mismatch', '403', 'maica_security_cookie_mismatch')
                elif self.enforce_cookie:
                    raise MaicaPermissionError('Cookie enforced but missing', '403', 'maica_security_cookie_missing')

                # Route request
                match recv_type.lower():
                    case 'ping':
                        await messenger(websocket, "pong", f"Ping recieved from {self.settings.verification.username} and responded", "200")
                    case 'params':
                        return_status = await self.def_model(recv_loaded_json)
                    case 'query':
                        return_status = await self.do_communicate(recv_loaded_json)
                        await self.reset_auxiliary_inst()
                    case placeholder if "chat_params" in recv_loaded_json:
                        return_status = await self.def_model(recv_loaded_json)
                    case placeholder if "chat_session" in recv_loaded_json:
                        return_status = await self.do_communicate(recv_loaded_json)
                        await self.reset_auxiliary_inst()
                    case _:
                        raise MaicaInputWarning('Type cannot be determined', '422', 'maica_request_type_unknown')

            # Handle expected exceptions
            except CommonMaicaException as ce:
                if ce.is_critical or ce.is_breaking:
                    raise ce
                else:
                    await messenger(websocket, error=ce, no_raise=True)
                    await messenger(websocket, 'maica_loop_warn_finished', 'Loop hit a user level exception, stopped and reset', '304')
                    continue

    # Param setting section
    async def def_model(self, recv_loaded_json: dict):

        # Initiations
        websocket = self.websocket
        try:
            chat_params: dict = recv_loaded_json['chat_params']
            in_params = len(chat_params)
            accepted_params = self.settings.update(**chat_params)
            await messenger(websocket, 'maica_params_accepted', f"{accepted_params} out of {in_params} settings accepted", "200")
        
        # Handle input errors here
        except Exception as e:
            if not isinstance(e, CommonMaicaException):
                raise MaicaInputWarning(str(e), '405', 'maica_params_denied')
            else:
                raise e

    # Completion section
    async def do_communicate(self, recv_loaded_json: dict):

        # Initiations
        websocket = self.websocket
        query_in = ''
        replace_generation = ''
        ms_cache_identity = ''

        # Param assertions here
        chat_session = int(default(recv_loaded_json.get('chat_session'), 0))
        maica_assert(-1 <= chat_session < 10, "chat_session")
        self.settings.temp.update(chat_session=chat_session)


        if 'reset' in recv_loaded_json:
            if recv_loaded_json['reset']:
                maica_assert(1 <= chat_session < 10, "chat_session")
                purge_result = await self.reset_chat_session(self.settings.temp.chat_session)
                if not purge_result:
                    await messenger(websocket, "maica_session_not_found", "Determined chat_session doesn't exist", "204", self.traceray_id)
                else:
                    await messenger(websocket, "maica_session_reset", "Determined chat_session reset", "204", self.traceray_id)
                return

        if 'inspire' in recv_loaded_json and not query_in:
            if recv_loaded_json['inspire']:
                maica_assert(0 <= chat_session < 10, "chat_session")
                if isinstance(recv_loaded_json['inspire'], dict):
                    query_insp = await mtools.make_inspire(title_in=recv_loaded_json['inspire'], target_lang=self.settings.basic.target_lang)
                else:
                    query_insp = await mtools.make_inspire(target_lang=self.settings.basic.target_lang)
                if recv_loaded_json.get('use_cache') and self.settings.temp.chat_session == 0:
                    self.settings.temp.update(ms_cache=True)
                self.settings.temp.update(bypass_mf=True, bypass_mt=True)
                if not query_insp[0]:
                    if str(query_insp[1]) == 'mspire_insanity_limit_reached':
                        raise MaicaInternetWarning('MSpire scraping failed', '404', 'maica_mspire_scraping_failed')
                    elif str(query_insp[1]) == 'mspire_title_insane':
                        raise MaicaInputWarning('MSpire prompt not found on wikipedia', '410', 'maica_mspire_prompt_bad')
                    else:
                        raise MaicaInternetWarning('MSpire failed connecting wikipedia', '408', 'maica_mspire_conn_failed')
                if self.settings.temp.ms_cache:
                    self.settings.temp.update(bypass_sup=True)
                    ms_cache_identity = query_insp[3]
                    cache_insp = await self.find_ms_cache(ms_cache_identity)
                    if cache_insp:
                        self.settings.temp.update(bypass_gen=True)
                        replace_generation = cache_insp
                        
                query_in = query_insp[2]

        if 'postmail' in recv_loaded_json and not query_in:
            if recv_loaded_json['postmail']:
                maica_assert(0 <= chat_session < 10, "chat_session")
                if isinstance(recv_loaded_json['postmail'], dict):
                    query_insp = await mtools.make_postmail(**recv_loaded_json['postmail'], target_lang=self.settings.basic.target_lang)
                    # We're using the old school way to avoid using eval()
                    if default(recv_loaded_json['postmail'].get('bypass_mf'), False):
                        self.settings.temp.update(bypass_mf=True)
                    if default(recv_loaded_json['postmail'].get('bypass_mt'), True):
                        self.settings.temp.update(bypass_mt=True)
                    if default(recv_loaded_json['postmail'].get('bypass_stream'), True):
                        self.settings.temp.update(bypass_stream=True)
                    if default(recv_loaded_json['postmail'].get('ic_prep'), True):
                        self.settings.temp.update(ic_prep=True)
                    if default(recv_loaded_json['postmail'].get('strict_conv'), False):
                        self.settings.temp.update(strict_conv=True)
                elif isinstance(recv_loaded_json['postmail'], str):
                    query_insp = await mtools.make_postmail(content=recv_loaded_json['postmail'], target_lang=self.settings.basic.target_lang)
                    self.settings.temp.update(bypass_stream=True, ic_prep=True, strict_conv=False)
                else:
                    maica_assert(False, "postmail")
                
                query_in = query_insp[2]

        # This is future reserved for MVista

        if 'vision' in recv_loaded_json and not query_in:
            if recv_loaded_json['vision']:
                if isinstance(recv_loaded_json['vision'], str):
                    pass
                else:
                    pass

        if not query_in:
            maica_assert(recv_loaded_json.get('query'), 'query')
            query_in = recv_loaded_json['query']
        
        await asyncio.gather(self.sf_inst.reset(), self.mt_inst.reset())

        if 'savefile' in recv_loaded_json:
            if self.settings.basic.sf_extraction:
                self.sf_inst.add_extra(**recv_loaded_json['savefile'])
            else:
                self.settings.temp.update(sf_extraction_once=True)
                self.sf_inst.use_only(**recv_loaded_json['savefile'])
        if 'trigger' in recv_loaded_json:
            if self.settings.basic.mt_extraction:
                self.mt_inst.add_extra(*recv_loaded_json['trigger'])
            else:
                self.settings.temp.update(mt_extraction_once=True)
                self.mt_inst.use_only(recv_loaded_json['trigger'])

        # Deprecated: The easter egg thing

        # global easter_exist
        # if easter_exist:
        #     easter_check = easter(query_in)
        #     if easter_check:
        #         await websocket.send(self.wrap_ws_deformatter('299', 'easter_egg', easter_check, 'info'))

        match int(self.settings.temp.chat_session):
            case -1:

                # chat_session == -1 means query contains an entire chat history(sequence mode)
                session_type = -1
                try:
                    messages = json.loads(query_in)
                    query_in = messages[-1]['text']
                    if len(messages) > 10:
                        raise MaicaInputWarning('Sequence exceeded 10 rounds for chat_session -1', '413', 'maica_sequence_rounds_exceeded')
                except Exception as excepted:
                    raise MaicaInputWarning('Sequence is not JSON for chat_session -1', '406', 'maica_sequence_not_json')

            case i if 0 <= i < 10:

                # chat_session == 0 means single round, else normal
                session_type = 0 if i == 0 else 1
                messages0 = {'role': 'user', 'content': query_in}

                if self.settings.basic.enable_mf and not self.settings.temp.bypass_mf:
                    message_agent_wrapped = await self.mfocus_coro.agenting(query_in)
                else:
                    message_agent_wrapped = None
                
                prompt = await self.gen_system_prompt(message_agent_wrapped, self.settings.temp.strict_conv)
                if session_type == 1:
                    messages = (await self.rw_chat_session('i', [messages0], prompt))[1]
                elif session_type == 0:
                    messages = [{'role': 'system', 'content': prompt}, messages0]

        # Construction part done, communication part started

        completion_args = {
            "messages": messages,
            "stream": self.settings.basic.stream_output,
            "stop": ['<|im_end|>', '<|endoftext|>'],
        }
        
        if not self.settings.temp.bypass_sup:
            completion_args.update(self.settings.super())
        else:
            completion_args.update(self.settings.super.default())
            self.settings.temp.update(bypass_sup=False)

        if self.settings.temp.bypass_stream:
            completion_args['stream'] = False
            self.settings.temp.update(bypass_stream=False)

        if self.settings.temp.ic_prep:
            completion_args['presence_penalty'] = 1.0 - (1.0 - completion_args['presence_penalty']) * (2/3)

        await messenger(info=f'\nQuery constrcted and ready to go, last input is:\n{query_in}\nSending query...', type=MsgType.PRIM_RECV)

        if not self.settings.temp.bypass_gen or not replace_generation: # They should present together

            # Generation here
            resp = await self.mcore_conn.make_completion(**completion_args)

            if completion_args['stream']:
                reply_appended = ''
                seq = 0
                async for chunk in resp:
                    token = chunk.choices[0].delta.content
                    if token:
                        await asyncio.sleep(0)
                        await messenger(websocket, 'maica_core_streaming_continue', token, '100')
                        reply_appended += token
                        seq += 1
                await messenger(info='\n', type=MsgType.PLAIN)
                await messenger(websocket, 'maica_core_streaming_done', f'Streaming finished with seed {completion_args['seed']} for {self.settings.verification.username}, {seq} packets sent', '1000', traceray_id=self.traceray_id)
            else:
                reply_appended = resp.choices[0].message.content
                await messenger(websocket, 'maica_core_nostream_reply', reply_appended, '200', type=MsgType.CARRIAGE)
                await messenger(None, 'maica_core_nostream_done', f'Reply sent with seed {completion_args['seed']} for {self.settings.verification.username}', '1000', traceray_id=self.traceray_id)

        else:

            # We just pretend it was generated
            reply_appended = replace_generation
            if completion_args['stream']:
                await messenger(websocket, 'maica_core_streaming_continue', reply_appended, '100'); await messenger(info='\n', type=MsgType.PLAIN)
                await messenger(websocket, 'maica_core_streaming_done', f'Streaming finished with cache for {self.settings.verification.username}', '1000', traceray_id=self.traceray_id)
            else:
                await messenger(websocket, 'maica_core_nostream_reply', reply_appended, '200', type=MsgType.CARRIAGE)
                await messenger(None, 'maica_core_nostream_done', f'Reply sent with cache for {self.settings.verification.username}', '1000', traceray_id=self.traceray_id)

        # Can be post-processed here
        reply_appended = mtools.post_proc(reply_appended, self.settings.basic.target_lang)
        reply_appended_insertion = {'role': 'assistant', 'content': reply_appended}

        # Trigger process
        if self.settings.basic.enable_mt and not self.settings.temp.bypass_mt:
            await self.mtrigger_coro.triggering(query_in, reply_appended)
        else:
            self.settings.temp.update(bypass_mt=False)

        if self.settings.temp.ms_cache and not self.settings.temp.bypass_gen and not replace_generation:
            await self.store_ms_cache(ms_cache_identity, reply_appended)

        # Store history here
        if session_type == 1:
            stored = await self.rw_chat_session('a', [messages0, reply_appended_insertion])
            match stored[1]:
                case 1:
                    await messenger(websocket, 'maica_history_sliced', f"Session {self.settings.temp.chat_session} of {self.settings.verification.username} exceeded {self.settings.basic.max_length} characters and sliced", '204')
                case 2:
                    await messenger(websocket, 'maica_history_slice_hint', f"Session {self.settings.temp.chat_session} of {self.settings.verification.username} exceeded {self.settings.basic.max_length * (2/3)} characters, will slice at {self.settings.basic.max_length}", '200', no_print=True)

            await messenger(websocket, 'maica_chat_loop_finished', f'Finished chat loop from {self.settings.verification.username}', '200', traceray_id=self.traceray_id, type=MsgType.INFO)
        else:
            
            await messenger(websocket, 'maica_chat_loop_finished', f'Finished non-recording chat loop from {self.settings.verification.username}', '200', traceray_id=self.traceray_id, type=MsgType.INFO)

# Reserved for whatever
def callback_func_switch(future):
    pass
def callback_check_permit(future):
    pass
    
# Main app driver

async def main_logic(websocket, auth_pool, maica_pool, mcore_conn, mfocus_conn, online_dict):
    unique_lock = asyncio.Lock()
    async with unique_lock:
        try:
            sentence_of_the_day = SentenceOfTheDay().get_sentence()
            await messenger(websocket, 'maica_connection_initiated', sentence_of_the_day, '200', type=MsgType.INFO, no_print=True)

            thread_instance = await WsCoroutine.async_create(websocket, auth_pool=auth_pool, maica_pool=maica_pool, mcore_conn=mcore_conn, mfocus_conn=mfocus_conn, online_dict=online_dict)

            permit = await thread_instance.check_permit()
            assert isinstance(permit, dict) and permit['id'], permit

            online_dict[permit['id']] = [thread_instance.fsc, unique_lock]
            await messenger(info=f"Locking session for {permit['id']} named {permit['username']}", type=MsgType.LOG)

            return_status = await thread_instance.function_switch()
            # We let the exception router to handle that
            raise Exception(return_status)
        
        except CommonMaicaException as ce:
            if ce.is_critical:
                traceback.print_exc()
            await messenger(websocket, error=ce, traceray_id=getattr(thread_instance, 'traceray_id', None), no_raise=True)

        except websockets.exceptions.WebSocketException as we:
            try:
                we_code, we_reason = we.code, we.reason
                await messenger(info=f'Connection closed with {we_code}: {we_reason or 'No reason provided'}', type=MsgType.PRIM_LOG)
            except Exception:
                await messenger(info=f'Connection establishment failed: {str(we)}', type=MsgType.PRIM_LOG)

        except Exception as e:
            traceback.print_exc()
            await messenger(info=f'Coroutine broke by an unknown exception: {str(e)}', type=MsgType.ERROR)

        finally:
            try:
                online_dict.pop(permit['id'])
                await messenger(info=f"Lock released for {permit['username']}({permit['id']})", type=MsgType.LOG)
            except Exception:
                await messenger(info=f"No lock for this connection", type=MsgType.DEBUG)
            await websocket.close()
            await websocket.wait_closed()
            await messenger(info=f"Closing connection gracefully", type=MsgType.DEBUG)

async def prepare_thread(**kwargs):
    online_dict = _onliners; auth_created = False; maica_created = False

    if kwargs.get('auth_pool'):
        auth_pool = kwargs.get('auth_pool')
    else:
        auth_pool = await ConnUtils.auth_pool()
        auth_created = True
    if kwargs.get('maica_pool'):
        maica_pool = kwargs.get('maica_pool')
    else:
        maica_pool = await ConnUtils.maica_pool()
        maica_created = True

    try:
        mcore_conn: AiConnCoroutine = default(kwargs.get('mcore_conn'), await ConnUtils.mcore_conn())
        mfocus_conn: AiConnCoroutine = default(kwargs.get('mfocus_conn'), await ConnUtils.mfocus_conn())
    except Exception:
        mcore_conn = mfocus_conn = None

    await messenger(info='MAICA WS server started!' if load_env('MAICA_DEV_STATUS') == 'serving' else 'MAICA WS server started in development mode!', type=MsgType.PRIM_SYS)

    try:
        await messenger(info=f"Main model is {mcore_conn.model_actual}, MFocus model is {mfocus_conn.model_actual}", type=MsgType.SYS)
    except Exception:
        await messenger(info=f"Model deployment cannot be reached -- running in minimal testing mode", type=MsgType.SYS)
    
    try:
        server = await websockets.serve(functools.partial(main_logic, auth_pool=auth_pool, maica_pool=maica_pool, mcore_conn=mcore_conn, mfocus_conn=mfocus_conn, online_dict=online_dict), '0.0.0.0', 5000)
        await server.wait_closed()
    except BaseException as be:
        if isinstance(be, Exception):
            error = CommonMaicaError(str(be), '504')
            await messenger(error=error, no_raise=True)
    finally:
        close_list = []
        if auth_created:
            close_list.append(auth_pool.close())
        if maica_created:
            close_list.append(maica_pool.close())

        await asyncio.gather(*close_list, return_exceptions=True)

        await messenger(info='MAICA WS server stopped!', type=MsgType.PRIM_SYS)

def run_ws(**kwargs):
    
    asyncio.run(prepare_thread(**kwargs))

if __name__ == '__main__':

    run_ws()