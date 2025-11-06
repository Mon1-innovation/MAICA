import time
import asyncio
from typing import *

from maica.maica_utils import *

class BufferDict(dict):
    """Specifically used for stream buffering."""
    def add_id(self, id: int):
        """Also overwrites."""
        self[id] = StreamBuffer()

    def del_id(self, id: int):
        self.pop(id, None)

class StreamBuffer:
    """A queue-like buffer."""
    
    def __init__(self):
        self.timestamp = time.time()
        self._queue = asyncio.Queue()
        self._exhausted = asyncio.Event()
    
    async def aexhaust(self):
        self._exhausted.set()

    async def aappend(self, item):
        await self._queue.put(item)
    
    def sappend(self, item):
        try:
            self._queue.put_nowait(item)
        except asyncio.QueueFull:
            pass
    
    def __aiter__(self):
        return self
    
    async def __anext__(self):
        if not len(self) and self._exhausted.is_set():
            raise StopAsyncIteration
        
        tasks = []
        tasks.append(asyncio.create_task(self._queue.get()))
        if not self._exhausted.is_set():
            tasks.append(asyncio.create_task(self._exhausted.wait()))

        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for future in pending:
            future.cancel()
            await future
        for future in done:
            item = future.result()
            if item == True:
                raise StopAsyncIteration
            elif item:
                return item
    
    def __iter__(self):
        while not self._queue.empty():
            try:
                yield self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
    
    def __len__(self):
        return self._queue.qsize()
    
buffer_dict: BufferDict[StreamBuffer] = BufferDict()