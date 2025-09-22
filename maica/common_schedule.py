import asyncio
import datetime
import schedule

from typing import *
from maica.maica_utils import *

async def rotate_cache(maica_pool: DbPoolCoroutine):
    """Always provide a pool in production deployment!"""
    keep_time = load_env('MAICA_ROTATE_MSCACHE')
    if int(keep_time):
        timestamp = datetime.datetime.now()
        sql_expression_1 = "SELECT spire_id, timestamp FROM ms_cache"
        sql_expression_2 = "DELETE FROM ms_cache WHERE spire_id = %s"
        result = await maica_pool.query_get(sql_expression_1)
        for row in result:
            if row[1] + datetime.timedelta(hours=int(keep_time)) <= timestamp:
                await maica_pool.query_modify(sql_expression_2, (row[0]))

def wrap_rotate_cache(maica_pool):
    asyncio.run(rotate_cache(maica_pool))

async def schedule_rotate_cache(**kwargs):
    maica_created = False
    if kwargs.get('maica_pool'):
        maica_pool = kwargs.get('maica_pool')
    else:
        maica_pool = await ConnUtils.maica_pool()
        maica_created = True

    await messenger(info="MAICA scheduler started!", type=MsgType.SYS)
    if load_env('MAICA_ROTATE_MSCACHE') != '0':
        await messenger()
        schedule.every().day.at("04:00").do(wrap_rotate_cache, maica_pool=maica_pool)
    try:
        while True:
            schedule.run_pending()
            await asyncio.sleep(60)
    except BaseException as be:
        if isinstance(be, Exception):
            error = CommonMaicaError(str(be), '504')
            await messenger(error=error, no_raise=True)
    finally:
        if maica_created:
            await maica_pool.close()
            
        await messenger(info="MAICA scheduler stopped!", type=MsgType.SYS)
