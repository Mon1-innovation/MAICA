import asyncio
import os
import re
import json
import time
import csv
import aiosqlite
import traceback
import asyncssh
import signal
from maica_utils import *

class NvWatcher():
    def __init__(self):
        self.nodes = ['mcore', 'mfocus']

    async def _ainit(self):
        """Must run in the action loop."""
        await self.connect_remotes()
        await self.initiate_db()

    def _g(self, k):
        return getattr(self, k)

    def _s(self, k, v):
        setattr(self, k, v)

    async def query_nvsmi(self, ssh_client: asyncssh.connection.SSHClientConnection, keys=[]):
        command = f"nvidia-smi --query-gpu={','.join(keys)} --format=csv"
        result = await ssh_client.run(command, check=True)
        csv_capt = csv.DictReader(result.stdout.split('\n'))
        return list(csv_capt)

    async def connect_remotes(self):
        for node in self.nodes:
            self._s(f'{node}_name', load_env(f'{node.upper()}_NODE'))
            self._s(f'{node}_user', load_env(f'{node.upper()}_USER'))
            self._s(f'{node}_pwd', load_env(f'{node.upper()}_PWD'))
            self._s(f'{node}_addr', ReUtils.re_search_host_addr.search(load_env(f'{node.upper()}_ADDR'))[1])
            # print(self._g(f'{node}_addr'), self._g(f'{node}_user'), self._g(f'{node}_pwd'))
            self._s(f'{node}_ssh', (await asyncssh.connect(host=self._g(f'{node}_addr'), username=self._g(f'{node}_user'), password=self._g(f'{node}_pwd'), known_hosts=None)))

    async def initiate_db(self):
        self.self_path = os.path.dirname(os.path.abspath(__file__))
        self.db_client = await aiosqlite.connect(os.path.join(self.self_path, ".nvsw.db"), autocommit=True)

        basis = {}; basis_keys = ['name', 'memory.total']
        for node in self.nodes:
            basis[node] = await self.query_nvsmi(self._g(f'{node}_ssh'), basis_keys)
            await self.db_client.execute(f'CREATE TABLE IF NOT EXISTS `{self._g(f'{node}_name')}` (id INT PRIMARY KEY, name TEXT, memory TEXT, tflops TEXT, dynamic TEXT);')
            for i, gpu in enumerate(basis[node]):
                await self.db_client.execute(f'INSERT OR REPLACE INTO `{self._g(f'{node}_name')}` (id, name, memory, tflops, dynamic) VALUES ({i}, "{gpu["name"]}", "{gpu[" memory.total [MiB]"]}", "400", "[]");')

    async def append_dynamic(self, history: list, gpu: dict):
        gpu_values = list(gpu.values())
        gpu_stats = {"u": gpu_values[0].strip('%').strip(), "m": gpu_values[1].strip('BiM').strip(), "p": gpu_values[2].strip('W').strip()}
        if len(history) >= 36:
            history.pop()
        history.insert(0, gpu_stats)
        return history

    async def main_watcher(self):
        await self._ainit()
        dynamics_curr = {}
        while True:
            dynamics_new = {}; dynamic_keys = ['utilization.gpu', 'memory.used', 'power.draw']
            for node in self.nodes:
                if not dynamics_curr.get(node):
                    dynamics_curr[node] = []
                dynamics_new[node] = await self.query_nvsmi(self._g(f'{node}_ssh'), dynamic_keys)
                for i, gpu in enumerate(dynamics_new[node]):
                    try:
                        gpu_curr = dynamics_curr[node].pop(i)
                    except Exception:
                        gpu_curr = []
                    gpu_curr = await self.append_dynamic(gpu_curr, gpu)
                    dynamics_curr[node].insert(i, gpu_curr)
                    await self.db_client.execute(f'UPDATE `{self._g(f'{node}_name')}` SET dynamic = \'{json.dumps(gpu_curr, ensure_ascii=False)}\' WHERE id = {i}')
            
            await asyncio.sleep(10)
            print(1)

    def __del__(self):
        try:
            os.remove(os.path.join(self.self_path, ".nvsw.db"))
            for node in self.nodes:
                self._g(f'{node}_ssh').close()
                asyncio.run(self._g(f'{node}_ssh').wait_closed())
            asyncio.run(self.db_client.close())
        except Exception:
            pass

def start_watching():
    watcher = NvWatcher()
    try:
        asyncio.run(watcher.main_watcher())
    except Exception as e:
        traceback.print_exc()
        asyncio.run(messenger(info=str(e), type='error'))

if __name__ == '__main__':

    start_watching()