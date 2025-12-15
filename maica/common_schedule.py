import asyncio
import datetime
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from typing import *
from maica.mtools import ProcessingImg
from maica.maica_utils import *

_CONNS_LIST = ['maica_pool']

class CommonScheduler():
    """Keeps a schedule running."""

    root_csc: ConnSocketsContainer = None
    """Don't forget to implement at first!"""

    def __init__(self, involve_chat=True, involve_tts=True):
        rsc = RealtimeSocketsContainer()
        csc = self.__class__.root_csc.spawn_sub(rsc)
        self.fsc = FullSocketsContainer(rsc, csc)
        self.maica_pool = self.fsc.maica_pool

        self.schedule = AsyncIOScheduler()
        if involve_chat:
            self.schedule.add_job(
                self.rotate_ms_cache,
                trigger=IntervalTrigger(hours=1),
                id='rotate_ms_cache',
            )
            self.schedule.add_job(
                self.rotate_mv_imgs,
                trigger=IntervalTrigger(hours=1),
                id='rotate_mv_imgs'
            )
        if involve_tts:
            self.schedule.add_job(
                self.rotate_mtts_cache,
                trigger=IntervalTrigger(hours=1),
                id='rotate_mtts_cache'
            )
        self.schedule.start()

    @Decos.log_task
    async def rotate_ms_cache(self):
        """Deletes outdated mscache. We usually want to keep them for trainings."""
        keep_time = int(G.A.ROTATE_MSCACHE)
        if keep_time:
            timestamp = datetime.datetime.now()
            earliest_timestamp = timestamp - datetime.timedelta(hours=keep_time)
            sql_expression_1 = "DELETE FROM ms_cache WHERE timestamp < %s"
            rows = (await self.maica_pool.query_modify(expression=sql_expression_1, values=(earliest_timestamp, )))[0]
            sync_messenger(info=f'Removed {rows} rows of MSpire cache', type=MsgType.LOG)

    @Decos.log_task
    async def rotate_mv_imgs(self):
        """Deletes outdated mv_img."""
        keep_time = int(G.A.ROTATE_MVISTA)
        if keep_time:
            timestamp = datetime.datetime.now()
            earliest_timestamp = timestamp - datetime.timedelta(hours=keep_time)

            sql_expression_1 = "SELECT uuid FROM mv_meta WHERE timestamp < %s"
            result = await self.maica_pool.query_get(expression=sql_expression_1, values=(earliest_timestamp, ), fetchall=True)
            uuids = [i[0] for i in result]
            for uuid in uuids:

                processing_img = ProcessingImg()
                processing_img.det_path(uuid)
                processing_img.delete()

                sql_expression_2 = "DELETE FROM mv_meta WHERE uuid = %s"
                await self.maica_pool.query_modify(expression=sql_expression_2, values=(uuid, ))

            sync_messenger(info=f'Removed {len(uuids)} MVista images', type=MsgType.LOG)

    @Decos.log_task
    async def rotate_mtts_cache(self):
        """Deletes long-unused mtts cache."""
        def sync_rotation(earliest_timestamp):
            base_path = get_inner_path('fs_storage/mtts')
            mtts_cache_entries = os.scandir(base_path)
            delete_list = []
            for entry in mtts_cache_entries:
                if entry.is_file() and not entry.name.startswith('.'):
                    path = entry.path
                    last_atime = os.path.getatime(path)
                    if last_atime < earliest_timestamp:
                        delete_list.append(path)
            
            for path in delete_list:
                try:
                    os.remove(path)
                except Exception:...

            return len(delete_list)

        keep_time = int(G.T.ROTATE_TTSCACHE)
        if keep_time:
            timestamp = datetime.datetime.now()
            earliest_timestamp_float = (timestamp - datetime.timedelta(hours=keep_time)).timestamp()
            deleted_count = await wrap_run_in_exc(None, sync_rotation, earliest_timestamp_float)

            sync_messenger(info=f'Removed {deleted_count} MTTS caches', type=MsgType.LOG)

    async def run_schedule(self):
        """The schedule starter."""
        await sleep_forever()

    async def close(self):
        self.schedule.shutdown()

async def prepare_thread(**kwargs):

    # Construct csc first
    root_csc_kwargs = {k: kwargs.get(k) for k in _CONNS_LIST}
    root_csc = ConnSocketsContainer(**root_csc_kwargs)
    CommonScheduler.root_csc = root_csc

    await messenger(info='MAICA scheduler started!', type=MsgType.PRIM_SYS)
    
    try:
        common_scheduler = CommonScheduler(kwargs.get('involve_chat', True), kwargs.get('involve_tts', True))
        await common_scheduler.run_schedule()
        common_scheduler.close()

    except BaseException as be:
        if isinstance(be, Exception):
            error = CommonMaicaError(str(be), '504')
            await messenger(error=error, no_raise=True)
    finally:
        await messenger(info='MAICA scheduler stopped!', type=MsgType.PRIM_SYS)

async def _run_shd():
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
    await messenger(info='Individual MAICA scheduler cleaning done', type=MsgType.DEBUG)

def run_shd():
    asyncio.run(_run_shd())

if __name__ == '__main__':
    run_shd()
