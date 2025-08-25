import asyncio
import maica_ws
import maica_http
import common_schedule
from maica_utils import *

async def start_all():
    auth_pool, maica_pool = await asyncio.gather(ConnUtils.auth_pool(), ConnUtils.maica_pool())
    kwargs = {"auth_pool": auth_pool, "maica_pool": maica_pool}
    task_ws = asyncio.create_task(maica_ws.prepare_thread(**kwargs))
    task_http = asyncio.create_task(maica_http.prepare_thread(**kwargs))
    task_schedule = asyncio.create_task(common_schedule.schedule_rotate_cache(**kwargs))

    await asyncio.wait([
        task_ws,
        task_http,
        task_schedule,
    ], return_when=asyncio.FIRST_COMPLETED)

if __name__ == "__main__":
    asyncio.run(start_all())