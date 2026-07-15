"""
Import layer 2.4
"""
import time
import asyncio

from typing import *
from contextlib import asynccontextmanager
from .maica_utils import *

class StreamBuffer[T](asyncio.Queue[T]):
    """
    A queue-like buffer.
    In v1.3, we change its behavior, use None as termination sign.
    """
    def __init__(self, maxsize = 0):
        super().__init__(maxsize)
        self.lock = asyncio.Lock()

    def kill(self):
        self.put_nowait(None)

    def clear(self):
        self._queue.clear()
        self._unfinished_tasks = 0
        self._finished.set()

    def __aiter__(self):
        return self

    async def __anext__(self) -> T:
        item = await self.get()
        if item is None:
            self.task_done()
            raise StopAsyncIteration
        return item

_buffers_index: dict[
    int,
    Tuple[
        StreamBuffer,
        float,
    ]
] = {}

def no_lock_acquire_buffer(user_id: int):
    """
    asyncio.Queue is not something cannot be occupied twice ofc.
    The locked method is for ensure single writing, we use this to acquire for reading.
    """
    if user_id not in _buffers_index:
        _buffers_index[user_id] = [StreamBuffer(), time.time()]
    else:
        _buffers_index[user_id][1] = time.time()

    buffer = _buffers_index[user_id][0]
    return buffer

@asynccontextmanager
async def acquire_buffer(user_id: int):
    """Pass in user_id is enough."""
    buffer = no_lock_acquire_buffer(user_id)

    async with buffer.lock:
        yield buffer

def buffers_gc(timestamp):
    gced: List[Tuple] = []
    stale_keys = []
    for k, v in _buffers_index.items():
        if v[1] < timestamp and not v[0].lock.locked():
            stale_keys.append(k)
    for k in stale_keys:
        _buffers_index.pop(k, None)
        gced.append(k)
    return gced
