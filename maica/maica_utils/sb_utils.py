"""Import layer 5"""
import asyncio
import json
from openai.types.chat import ChatCompletionMessage
from .connection_utils import *
from .fsc_late import *
from maica.maica_utils import *

class PersistentManager(AsyncCreator):
    """This is just a template. Do not initialize!"""
    DB_NAME = 'persistents'
    PRIM_KEY = 'persistent_id'
    FUNC_NAME = 'mfocus'

    @staticmethod
    def EMPTY():
        return {}

    @staticmethod
    def test_log_cache_stats(func):
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            print(f'Cache expired: {result}')
            return result
        return wrapper

    def __init__(self, fsc: FullSocketsContainer) -> None:
        self.settings: MaicaSettings = fsc.maica_settings
        self.mfocus_conn = fsc.mfocus_conn
        self.mnerve_conn = fsc.mnerve_conn
        self.websocket, self.traceray_id = fsc.rsc.websocket, fsc.rsc.traceray_id
        self.maica_pool = fsc.maica_pool
        self.sf_forming_buffer = self.EMPTY()
        self.p_id = self.timestamp = None
        self.sf_content = self.EMPTY()
        self.formed_info = None

    async def _ainit(self):
        await self.reset(force=True)

    def _cap_2(self, text) -> str:
        if len(text) >= 2:
            return text[:2].upper() + text[2:]
        else:
            return text.upper()
        
    def _add(self, data, ex) -> Union[list, dict]:
        data.update(ex) if isinstance(data, dict) else data.extend(ex)
            
    async def _find_session_or_default(self) -> int:
        sql_expression = f'SELECT {self.PRIM_KEY} FROM {self.DB_NAME} WHERE user_id = %s AND chat_session_num = %s'
        if not await self.maica_pool.query_get(sql_expression, (self.settings.verification.user_id, self.settings.temp.chat_session)):
            return 0
        else:
            return self.settings.temp.chat_session

    # @test_log_cache_stats
    async def _check_expired_or_not(self) -> bool:
        if self.p_id and self.timestamp and self.sf_content:
            sql_expression_1 = f'SELECT timestamp FROM {self.DB_NAME} WHERE {self.PRIM_KEY} = %s'
            try:
                result = await self.maica_pool.query_get(sql_expression_1, (self.p_id, ))
                new_timestamp = result[0]
                if new_timestamp == self.timestamp:
                    return False
            except Exception:
                if self.sf_content is self.EMPTY():
                    return False
                else:
                    return True
        return True

    async def reset(self, force=False) -> None:
        if  force or await self._check_expired_or_not():
            try:
                sql_expression = f'SELECT {self.PRIM_KEY}, content, timestamp FROM {self.DB_NAME} WHERE user_id = %s AND chat_session_num = %s'
                result = await self.maica_pool.query_get(sql_expression, (self.settings.verification.user_id, await self._find_session_or_default()))

                p_id, content, timestamp = result
                self.p_id, self.timestamp = p_id, timestamp
                self.sf_content = json.loads(content)
            except Exception:
                self.p_id = self.timestamp = None
                self.sf_content = self.EMPTY()
                await messenger(self.websocket, f'{self.FUNC_NAME}_no_persistent', f'No persistent found for {self._cap_2(self.FUNC_NAME)}, using empty', '204', traceray_id=self.traceray_id)
            self.sf_forming_buffer = self.EMPTY()
            self._add(self.sf_forming_buffer, self.sf_content)
        else:
            # If the cache is not expired, we just reuse it
            self.sf_forming_buffer = self.EMPTY()
            self._add(self.sf_forming_buffer, self.sf_content)

class AgentContextManager(AsyncCreator):
    """This is just a template. Do not initialize!"""
    def __init__(self, fsc: FullSocketsContainer, sf_inst=None, mt_inst=None):
        self.settings = fsc.maica_settings
        self.websocket, self.traceray_id = fsc.rsc.websocket, fsc.rsc.traceray_id
        self.mfocus_conn = fsc.mfocus_conn
        self.mnerve_conn = fsc.mnerve_conn
        self.sf_inst, self.mt_inst = sf_inst, mt_inst
        self.maica_pool = fsc.maica_pool

    async def _ainit(self):
        await self.reset()

    async def reset(self):
        """Caution: we should reset sf_inst and mt_inst here, but these are done more manually to prevent duplication."""
        self.tools = []
        self.serial_messages = []

    async def full_reset(self):
        """This resets sf_inst and mt_inst too."""
        reset_list = []
        if self.sf_inst:
            reset_list.append(self.sf_inst.reset())
        if self.mt_inst:
            reset_list.append(self.mt_inst.reset())
        await asyncio.gather(*reset_list)
        await self.reset()

    async def _construct_query(self, user_input=None, tool_input=None, tool_id=None, pre_post: Literal['pre', 'post']=None):
        match pre_post:
            case 'pre':
                additive_setting = self.settings.extra.pre_additive
            case 'post':
                additive_setting = self.settings.extra.post_additive
            case _:
                raise MaicaInputError('Need type assignment on use', '500')
        if not self.serial_messages and additive_setting and 1 <= self.settings.temp.chat_session <= 9:
            sql_expression = 'SELECT content FROM chat_session WHERE user_id = %s AND chat_session_num = %s'
            result = await self.maica_pool.query_get(expression=sql_expression, values=(self.settings.verification.user_id, self.settings.temp.chat_session))
            if result and result[0]:
                res_list = json.loads(f'[{result[0]}]')
                lines_num = min(self.settings.extra.pre_additive * 2, len(res_list) - 1)
                message_additive = res_list[-lines_num:] if lines_num > 0 else []
                if message_additive:
                    self.serial_messages.extend(message_additive)
                    assert self.serial_messages[-1]['role'] == 'assistant', 'Additive got corrupted chat history'

        if user_input:
            # The new OpenAI standard fucked all previous procedures
            self.serial_messages = clean_msgs(self.serial_messages, exclude=['reasoning_content'])
            self.serial_messages.append({'role': 'user', 'content': user_input})

        elif tool_input:
            self.serial_messages.append({'role': 'tool', 'tool_call_id': tool_id, 'content': tool_input})

    async def _send_query(self, thinking: Literal[True, False, None]=True) -> tuple[str, list]:
        self.serial_messages = apply_postfix(self.serial_messages, thinking)
        
        completion_args = {
            "messages": self.serial_messages,
            "tools": self.tools,
        }
        # print(completion_args)

        resp = await self.mfocus_conn.make_completion(**completion_args)
        content, rcontent, tool_calls = resp.choices[0].message.content, getattr(resp.choices[0].message, 'reasoning_content', None), resp.choices[0].message.tool_calls

        if G.A.ALT_TOOLCALL != '0':
            self.serial_messages.append(resp.choices[0].message)
        else:
            self.serial_messages.append({"role": "assistant", "content": content})

        return content, rcontent, tool_calls
