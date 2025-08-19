from .connection_utils import *
from .container_utils import *
from .maica_utils import *
"""Import layer 4"""

class SideBoundCoroutine():
    """This is just a template. Do not initialize!"""
    DB_NAME = 'persistents'
    PRIM_KEY = 'persistent_id'
    FUNC_NAME = 'mfocus'
    DATA_TYPE = dict
    EMPTY = {} if DATA_TYPE is dict else []


    def __init__(self, fsc: FullSocketsContainer) -> None:
        self.settings: MaicaSettings = fsc.maica_settings
        self.mfocus_conn: AiConnCoroutine = fsc.mfocus_conn
        self.websocket, self.traceray_id = fsc.rsc.websocket, fsc.rsc.traceray_id
        self.maica_pool = fsc.maica_pool
        self.sf_forming_buffer = self.EMPTY
        self.p_id = self.timestamp = None
        self.sf_content = self.EMPTY
        self.formed_info = None
        asyncio.run(self.reset(force=True))

    def _cap_2(text) -> str:
        if len(text) >= 2:
            return text[:2].upper() + text[2:]
        else:
            return text.upper()
        
    def _add(self, data, ex) -> Union[list, dict]:
        data.update(ex) if self.DATA_TYPE is dict else data.extend(ex)
            
    async def _find_session_or_default(self) -> int:
        sql_expression = f'SELECT {self.PRIM_KEY} FROM {self.DB_NAME} WHERE user_id = %s AND chat_session_num = %s'
        if not await self.maica_pool.query_get(sql_expression, (self.settings.verification.user_id, self.settings.temp.chat_session)):
            return 1
        else:
            return self.settings.temp.chat_session

    async def _check_expired_or_not(self) -> bool:
        if self.p_id and self.timestamp and self.sf_content:
            sql_expression_1 = f'SELECT timestamp FROM {self.DB_NAME} WHERE {self.PRIM_KEY} = %s'
            result = await self.maica_pool.query_get(sql_expression_1, (self.p_id))
            new_timestamp = result[0]
            if new_timestamp == self.timestamp:
                return False
        return True

    async def reset(self, force=False) -> None:
        if await self._check_expired_or_not() or force:
            try:
                sql_expression = f'SELECT {self.PRIM_KEY}, content, timestamp FROM {self.DB_NAME} WHERE user_id = %s AND chat_session_num = %s'
                result = await self.maica_pool.query_get(sql_expression, (self.settings.verification.user_id, await self._find_session_or_default()))

                p_id, content, timestamp = result
                self.p_id, self.timestamp = p_id, timestamp
                self.sf_content = json.loads(content)
            except Exception:
                self.p_id = self.timestamp = None
                self.sf_content = {}
                await messenger(self.websocket, f'{self.FUNC_NAME}_no_persistent', f'No persistent found for {self._cap_2(self.FUNC_NAME)}, using empty', '404', traceray_id=self.traceray_id)
            self.sf_forming_buffer = {}
            self._add(self.sf_forming_buffer, self.sf_content)
        else:
            # If the cache is not expired, we just reuse it
            self.sf_forming_buffer = {}
            self._add(self.sf_forming_buffer, self.sf_content)

    if DATA_TYPE is dict:
        def add_extra(self, **kwargs) -> None:
            self.sf_forming_buffer.update(kwargs)

        def use_only(self, **kwargs) -> None:
            self.sf_forming_buffer = kwargs

        def read_from_sf(self, key) -> any:
            return self.sf_forming_buffer.get(key)
    else:
        def add_extra(self, *args) -> None:
            self.sf_forming_buffer.extend(args)

        def use_only(self, *args) -> None:
            self.sf_forming_buffer = args

        def read_from_sf(self, seq) -> any:
            return self.sf_forming_buffer[seq]