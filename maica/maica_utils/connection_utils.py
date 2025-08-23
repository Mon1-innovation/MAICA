import aiomysql
import asyncio
import traceback
from openai import AsyncOpenAI
from .maica_utils import *
from .setting_utils import *
"""Import layer 3"""

DB_ADDR = load_env('DB_ADDR')
DB_USER = load_env('DB_USER')
DB_PASSWORD = load_env('DB_PASSWORD')
AUTH_DB = load_env('AUTH_DB')
MAICA_DB = load_env('MAICA_DB')
MCORE_ADDR = load_env('MCORE_ADDR')
MFOCUS_ADDR = load_env('MFOCUS_ADDR')

class DbPoolCoroutine():
    """Maintain a database connection pool so you don't have to."""
    def __init__(self, host, user, password, db, ro=False):
        self.host, self.user, self.password, self.db, self.ro = host, user, password, db, ro
        asyncio.run(self._ainit())

    async def _ainit(self):
        self.pool: aiomysql.Pool = await aiomysql.create_pool(host=self.host, user=self.user, password=self.password, db=self.db, autocommit=True)

    async def keep_alive(self):
        try:
            async with self.pool.acquire():
                pass
        except Exception:
            # traceback.print_exc()
            await messenger(None, f'{self.db}_reconn', f"Recreating {self.db} pool since cannot acquire", '301', type='warn')
            try:
                self.pool.close()
                await self._ainit()
            except Exception:
                error = MaicaDbError(f'Failure when trying reconnecting to {self.db}', '502')
                await messenger(None, f'{self.db}_reconn_failure', traceray_id='db_handling', type='error')

    async def query_get(self, expression, values=None, fetchall=False) -> list:
        results = None
        for tries in range(0, 3):
            try:
                await self.keep_alive()
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        if not values:
                            await cur.execute(expression)
                        else:
                            await cur.execute(expression, values)
                        results = await cur.fetchone() if not fetchall else await cur.fetchall()
                break
            except Exception:
                if tries < 2:
                    await messenger(info=f'DB temporary failure, retrying {str(tries + 1)} time(s)')
                    await asyncio.sleep(0.5)
                else:
                    error = MaicaDbError(f'DB connection failure after {str(tries + 1)} times', '502')
                    await messenger(None, 'db_connection_failed', traceray_id='db_handling', error=error)
        return results

    async def query_modify(self, expression, values=None, fetchall=False) -> int:
        if self.ro:
            error = MaicaDbError(f'DB marked as ro, no modify permitted', '403')
            await messenger(None, 'db_modification_denied', traceray_id='db_handling', error=error)
        lrid = None
        for tries in range(0, 3):
            try:
                await self.keep_alive()
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        if not values:
                            await cur.execute(expression)
                        else:
                            await cur.execute(expression, values)
                        await conn.commit()
                        lrid = cur.lastrowid
                break
            except Exception:
                if tries < 2:
                    await messenger(info=f'DB temporary failure, retrying {str(tries + 1)} time(s)')
                    await asyncio.sleep(0.5)
                else:
                    error = MaicaDbError(f'DB connection failure after {str(tries + 1)} times', '502')
                    await messenger(None, 'db_connection_failed', traceray_id='db_handling', error=error)
        return lrid

class AiConnCoroutine():
    """Maintain an AI connection so you don't have to."""
    def __init__(self, api_key, base_url, name='mcore_cli', model: Union[int, str]=0):
        self.test = False
        self.api_key, self.base_url, self.name, self.model = api_key, base_url, name, model
        self.websocket = None
        self.traceray_id = ''
        asyncio.run(self._ainit(model))

    async def _ainit(self, model):
        if not self.base_url:
            self.test = True
            return
        else:
            self.socket = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        await self.keep_alive()
        if isinstance(model, str):
            await self.use_model(model) 

    def init_rsc(self, rsc: FSCPlain.RealtimeSocketsContainer):
        self.websocket, self.traceray_id = rsc.websocket, rsc.traceray_id

    async def keep_alive(self):
        try:
            model_list = await self.socket.models.list()
            if isinstance(self.model, int):
                self.model_actual = model_list[0].id
        except Exception:
            await messenger(None, f'{self.name}_reconn', f"Recreating {self.name} client since cannot conn", '301', type='warn')
            try:
                await self.socket.close()
                await self._ainit()
            except Exception:
                error = MaicaResponseError(f'Failure when trying reconnecting to {self.name}', '502')
                await messenger(None, f'{self.name}_reconn_failure', traceray_id='ai_handling', type='error')

    async def use_model(self, model: Union[int, str]=0):
        assert isinstance(model, Union[int, str]), "Model choice unrecognizable"
        self.model = model
        if isinstance(model, int):
            self.model_actual = (await self.socket.models.list())[model].id
        else:
            self.model_actual = model
            
    async def make_completion(self, **kwargs):
        for tries in range(0, 3):
            try:
                await self.keep_alive()
                kwargs.update(
                    {
                        "model": self.model_actual
                    }
                )
                task_stream_resp = asyncio.create_task(self.socket.chat.completions.create(**kwargs))
                await task_stream_resp
                return task_stream_resp.result()
            except Exception:
                if tries < 2:
                    await messenger(info=f'Model temporary failure, retrying {str(tries + 1)} time(s)')
                    await asyncio.sleep(0.5)
                else:
                    error = MaicaResponseError(f'Cannot reach model endpoint after {str(tries + 1)} times', '502')
                    await messenger(self.websocket, 'maica_core_model_inaccessible', traceray_id=self.traceray_id, error=error)

class ConnUtils():
    """Just a wrapping for functions."""
    def auth_pool():
        return DbPoolCoroutine(
            host=DB_ADDR,
            user=DB_USER,
            password=DB_PASSWORD,
            db=AUTH_DB,
            ro=True,
        )

    def maica_pool():
        return DbPoolCoroutine(
            host=DB_ADDR,
            user=DB_USER,
            password=DB_PASSWORD,
            db=MAICA_DB,
        )

    def mcore_conn(rsc):
        return AiConnCoroutine(
            rsc=rsc,
            api_key='EMPTY',
            base_url=MCORE_ADDR,
            name='mcore_cli'
        )

    def mfocus_conn(rsc):
        return AsyncOpenAI(
            rsc=rsc,
            api_key='EMPTY',
            base_url=MFOCUS_ADDR,
            name='mfocus_cli'
        )

async def validate_input(input: str, limit: int=4096, rsc: Optional[FSCPlain.RealtimeSocketsContainer]=None, must: list=[], warn: list=[]) -> Union[dict, list]:
    """
    Mostly for ws.
    """
    try:
        if not input:
            raise MaicaInputWarning('Input is empty', '410')
        assert isinstance(input, str), 'Input must be str'
        if len(input) > limit:
            raise MaicaInputWarning('Input length exceeded', '413')
        try:
            input_json = json.loads(input)
        except:
            raise MaicaInputWarning('Request body not JSON', '400')
        if must:
            for mustkey in must:
                if not input_json.get(mustkey):
                    raise MaicaInputWarning(f'Request contains no necessary {mustkey}', '405')
        if warn:
            for warnkey in warn:
                if not warnkey in input_json:
                    if rsc:
                        await messenger(rsc.websocket, 'maica_future_warning', f'Requests containing no {warnkey} will likely be deprecated in the future', '302')
        
        return input_json
    
    except CommonMaicaException as ce:
        if rsc:
            await messenger(rsc.websocket, 'input_validation_denied', traceray_id=rsc.traceray_id, error=ce)
        else:
            raise ce
        
    except Exception as e:
        if rsc:
            error = MaicaInputError(str(e), '400')
            await messenger(rsc.websocket, 'input_validation_error', traceray_id=rsc.traceray_id, error=error)
        else:
            raise e