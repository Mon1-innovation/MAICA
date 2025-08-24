import asyncio
import datetime
import schedule

from typing import *
from maica_utils import *

async def rotate_cache(maica_pool: DbPoolCoroutine):
    keep_time = load_env('ROTATE_MSCACHE')
    if int(keep_time):
        timestamp = datetime.datetime.now()
        sql_expression_1 = "SELECT spire_id, timestamp FROM ms_cache"
        sql_expression_2 = "DELETE FROM ms_cache WHERE spire_id = %s"
        result = await maica_pool.query_get(sql_expression_1)
        for row in result:
            if row[1] + datetime.timedelta(hours=int(keep_time)) <= timestamp:
                await maica_pool.query_modify(sql_expression_2, (row[0]))

def wrap_rotate_cache(maica_pool=None):
    maica_pool = default(maica_pool, ConnUtils.maica_pool())
    asyncio.run(rotate_cache(maica_pool))

async def schedule_rotate_cache(*args, **kwargs):
    if load_env('ROTATE_MSCACHE') != '0':
        schedule.every().day.at("04:00").do(wrap_rotate_cache, *args, **kwargs)
    while True:
        schedule.run_pending()
        asyncio.sleep(60)