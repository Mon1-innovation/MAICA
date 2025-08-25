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

class NvWatcher(AsyncCreator):
    def __init__(self, node):
        self.node = node
        self.node_name = load_env(f'{node.upper()}_NODE')
        self.node_user = load_env(f'{node.upper()}_USER')
        self.node_pwd = load_env(f'{node.upper()}_PWD')
        self.node_addr = ReUtils.re_search_host_addr.search(load_env(f'{node.upper()}_ADDR'))[1]

    async def _ainit(self):
        """Must run in the action loop."""
        await self.connect_remotes()
        await self.initiate_db()

    async def query_nvsmi(self, ssh_client: asyncssh.connection.SSHClientConnection, keys=[]):
        command = f"nvidia-smi --query-gpu={','.join(keys)} --format=csv"
        result = await ssh_client.run(command, check=True)
        csv_capt = csv.DictReader(result.stdout.split('\n'))
        return list(csv_capt)

    async def connect_remotes(self):
        self.node_ssh = await asyncssh.connect(host=self.node_addr, username=self.node_user, password=self.node_pwd, known_hosts=None)

    async def initiate_db(self):
        self.self_path = os.path.dirname(os.path.abspath(__file__))
        self.db_client = await aiosqlite.connect(os.path.join(self.self_path, ".nvsw.db"), autocommit=True)

        basis_keys = ['name', 'memory.total']
        basic_result = await self.query_nvsmi(self.node_ssh, basis_keys)
        await self.db_client.execute(f'CREATE TABLE IF NOT EXISTS `{self.node_name}` (id INT PRIMARY KEY, name TEXT, memory TEXT, tflops TEXT, dynamic TEXT);')

        for i, gpu in enumerate(basic_result):
            await self.db_client.execute(f'INSERT OR REPLACE INTO `{self.node_name}` (id, name, memory, tflops, dynamic) VALUES ({i}, "{gpu["name"]}", "{gpu[" memory.total [MiB]"]}", "400", "[]");')

    async def append_dynamic(self, history: list, gpu: dict):
        gpu_values = list(gpu.values())
        gpu_stats = {"u": gpu_values[0].strip('%').strip(), "m": gpu_values[1].strip('BiM').strip(), "p": gpu_values[2].strip('W').strip()}
        if len(history) >= 36:
            history.pop()
        history.insert(0, gpu_stats)
        return history

    async def main_watcher(self):
        await self._ainit()
        dynamics_curr = []
        while True:
            dynamic_keys = ['utilization.gpu', 'memory.used', 'power.draw']
            dynamics_new = await self.query_nvsmi(self.node_ssh, dynamic_keys)
            for i, gpu in enumerate(dynamics_new):
                try:
                    gpu_curr = dynamics_curr.pop(i)
                except Exception:
                    gpu_curr = []
                gpu_curr = await self.append_dynamic(gpu_curr, gpu)
                dynamics_curr.insert(i, gpu_curr)
                await self.db_client.execute(f'UPDATE `{self.node_name}` SET dynamic = \'{json.dumps(gpu_curr, ensure_ascii=False)}\' WHERE id = {i}')
            
            await asyncio.sleep(10)

    def __del__(self):
        try:
            os.remove(os.path.join(self.self_path, ".nvsw.db"))
            self.node_ssh.close()
        except Exception:
            pass

async def prepare_watcher():
    watcher_mcore = await NvWatcher.async_create('mcore')
    watcher_mfocus = await NvWatcher.async_create('mfocus')
    try:
        await asyncio.gather(watcher_mcore.main_watcher(), watcher_mfocus.main_watcher())
    except Exception as e:
        traceback.print_exc()
        await messenger(info=str(e), type='error')

def start_watching():
    asyncio.run(prepare_watcher())

if __name__ == '__main__':

    start_watching()