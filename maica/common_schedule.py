import asyncio
import datetime
import os
import sqlalchemy

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from typing import *
from maica.mtools import ImgByUuid
from maica.maica_utils import *

_CONNS_LIST = []

class CommonScheduler():
    """Keeps a schedule running."""

    root_csc: ConnSocketsContainer = None
    """Don't forget to fill at first!"""

    def __init__(self, involve_chat=True, involve_tts=True):

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
            self.schedule.add_job(
                self.gc_sessions,
                trigger=IntervalTrigger(hours=1),
                id='gc_sessions'
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

            async with DatabaseUtils.SessionData() as dbs:

                stmt = sqlalchemy.delete(SqlMsCache).where(
                    SqlMsCache.timestamp < earliest_timestamp
                )

                er = await dbs.execute(stmt)
                await dbs.commit()
                rows = er.rowcount

            sync_messenger(info=f'Removed {rows} rows of MSpire cache', type=MsgType.LOG)

    @Decos.log_task
    async def rotate_mv_imgs(self):
        """Deletes outdated mv_img."""
        keep_time = int(G.A.ROTATE_MVISTA)
        if keep_time:
            timestamp = datetime.datetime.now()
            earliest_timestamp = timestamp - datetime.timedelta(hours=keep_time)

            async with DatabaseUtils.SessionData() as dbs:

                stmt = sqlalchemy.select(SqlMvMeta).where(
                    SqlMvMeta.timestamp < earliest_timestamp
                )

                metas = (await dbs.scalars(stmt)).all()
                
                for meta in metas:
                    try:
                        processing_img = ImgByUuid()
                        processing_img.uuid = meta.uuid
                        await asyncio.to_thread(processing_img.delete)
                    except Exception:
                        # We ignore file <= db inconsistency, because they're temporary anyway
                        pass

                    await dbs.delete(meta)

                await dbs.commit()

            sync_messenger(info=f'Removed {len(metas)} MVista images', type=MsgType.LOG)

    @Decos.log_task
    async def gc_sessions(self):
        """Releases stale V2 sessions from ram."""
        keep_time = int(G.A.GC_SESSIONS)
        if keep_time:
            timestamp = datetime.datetime.now()
            earliest_timestamp = timestamp - datetime.timedelta(hours=keep_time)
            ftime = earliest_timestamp.timestamp()

            gced = dbos_gc(ftime)
            sync_messenger(info=f'Destroyed {len(gced)} session handlers', type=MsgType.LOG)
            gced2 = buffers_gc(ftime)
            sync_messenger(info=f'Destroyed {len(gced2)} websocket buffers', type=MsgType.LOG)

    @Decos.log_task
    async def rotate_mtts_cache(self):
        """Deletes long-unused mtts cache."""
        def sync_rotation(earliest_timestamp):
            base_path = get_inner_path('fs_storage/mtts')
            delete_list = []
            all_count = 0
            with os.scandir(base_path) as mtts_cache_entries:
                for entry in mtts_cache_entries:
                    if entry.is_file() and not entry.name.startswith('.'):
                        all_count += 1
                        path = entry.path
                        last_atime = os.path.getatime(path)
                        if last_atime < earliest_timestamp:
                            delete_list.append(path)
            
            for path in delete_list:
                try:
                    os.remove(path)
                except Exception:...

            return len(delete_list), all_count

        keep_time = int(G.T.ROTATE_TTSCACHE)
        if keep_time:
            timestamp = datetime.datetime.now()
            earliest_timestamp_float = (timestamp - datetime.timedelta(hours=keep_time)).timestamp()
            deleted_count, all_count = await asyncio.to_thread(sync_rotation, earliest_timestamp_float)

            sync_messenger(info=f'Removed {deleted_count} MTTS caches, {all_count} remaining', type=MsgType.LOG)

    async def run_schedule(self):
        """The schedule starter."""
        await sleep_forever()

    async def close(self):
        if self.schedule.running:
            self.schedule.shutdown(wait=False)

async def prepare_thread(**kwargs):

    # Construct csc first
    root_csc_kwargs = {k: kwargs.get(k) for k in _CONNS_LIST}
    root_csc = ConnSocketsContainer(**root_csc_kwargs)
    CommonScheduler.root_csc = root_csc
    
    common_scheduler = None
    try:
        common_scheduler = CommonScheduler(kwargs.get('involve_chat', True), kwargs.get('involve_tts', True))

        sync_messenger(info='MAICA scheduler started!', type=MsgType.PRIM_SYS)

        await common_scheduler.run_schedule()

    except asyncio.CancelledError:
        raise
    except Exception as e:
        error = CommonMaicaError(str(e), '504')
        sync_messenger(error=error)
        raise

    finally:
        if common_scheduler:
            await common_scheduler.close()
        sync_messenger(info='MAICA scheduler stopped!', type=MsgType.PRIM_SYS)

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
    sync_messenger(info='Individual MAICA scheduler cleaning done', type=MsgType.DEBUG)

def run_shd():
    asyncio.run(_run_shd())

if __name__ == '__main__':
    run_shd()
