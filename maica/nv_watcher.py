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
        if not self.node_name or not self.node_user or not self.node_pwd or not self.node_addr:
            return

        await self._connect_remotes()
        await self._initiate_db()

    async def _query_nvsmi(self, ssh_client: asyncssh.connection.SSHClientConnection, keys=[]):
        command = f"nvidia-smi --query-gpu={','.join(keys)} --format=csv"
        result = await ssh_client.run(command, check=True)
        csv_capt = csv.DictReader(result.stdout.split('\n'))
        return list(csv_capt)

    async def _connect_remotes(self):
        self.node_ssh = await asyncssh.connect(host=self.node_addr, username=self.node_user, password=self.node_pwd, known_hosts=None)

    async def _initiate_db(self):
        self.self_path = os.path.dirname(os.path.abspath(__file__))
        async with aiosqlite.connect(os.path.join(self.self_path, ".nvsw.db"), autocommit=True) as db_client:
            self.gpu_overall = []

            basis_keys = ['name', 'memory.total']
            basic_result = await self._query_nvsmi(self.node_ssh, basis_keys)
            await db_client.execute(f'CREATE TABLE IF NOT EXISTS `{self.node_name}` (id INT PRIMARY KEY, name TEXT, memory TEXT, tflops TEXT, dynamic TEXT);')

            for i, gpu in enumerate(basic_result):
                await db_client.execute(f'INSERT OR REPLACE INTO `{self.node_name}` (id, name, memory, tflops, dynamic) VALUES ({i}, "{gpu["name"]}", "{gpu[" memory.total [MiB]"]}", "400", "[]");')
                self.gpu_overall.append([i, gpu["name"], gpu[" memory.total [MiB]"], "400", []])

    async def _append_dynamic(self, history: list, gpu: dict):
        gpu_values = list(gpu.values())
        gpu_stats = {"u": gpu_values[0].strip('%').strip(), "m": gpu_values[1].strip('BiM').strip(), "p": gpu_values[2].strip('W').strip()}
        if len(history) >= 36:
            history.pop()
        history.insert(0, gpu_stats)
        return history

    async def main_watcher(self):
        if not self.node_name or not self.node_user or not self.node_pwd or not self.node_addr:
            await messenger(info=f"Necessary info not complete for watching {self.node}, freezing watcher", type=MsgType.PRIM_SYS)
            await sleep_forever()

        self.dynamics_curr = []
        dynamic_keys = ['utilization.gpu', 'memory.used', 'power.draw']
        while True:
            dynamics_new = await self._query_nvsmi(self.node_ssh, dynamic_keys)
            async with aiosqlite.connect(os.path.join(self.self_path, ".nvsw.db"), autocommit=True) as db_client:

                for i, gpu in enumerate(dynamics_new):
                    try:
                        gpu_curr = self.dynamics_curr.pop(i)
                    except Exception:
                        gpu_curr = []
                    gpu_curr = await self._append_dynamic(gpu_curr, gpu)
                    self.dynamics_curr.insert(i, gpu_curr)
                    await db_client.execute(f'UPDATE `{self.node_name}` SET dynamic = \'{json.dumps(gpu_curr, ensure_ascii=False)}\' WHERE id = {i}')
                    self.gpu_overall[i][4] = gpu_curr

            await asyncio.sleep(10)
    
    def get_statics_inside(self):
        node_info = {}
        for gpu_status in self.gpu_overall:
            gpuid, name, memory, tflops, dynamic = gpu_status
            u = 0; m = 0; p = 0
            for line in dynamic:
                u += float(line['u']); m += float(line['m']); p += float(line['p'])
            u /= len(dynamic); m /= len(dynamic); p /= len(dynamic)
            node_info[gpuid] = {'name': name, 'vram': memory, 'tflops': tflops, 'mean_utilization': int(u), 'mean_memory': int(m), 'mean_consumption': int(p)}
            
        return {self.node_name: node_info}

    def __del__(self):
        try:
            self.node_ssh.close()
            os.remove(os.path.join(self.self_path, ".nvsw.db"))
        except Exception:
            pass

async def prepare_watcher():
    watcher_mcore = await NvWatcher.async_create('mcore')
    watcher_mfocus = await NvWatcher.async_create('mfocus')
    try:
        await asyncio.gather(watcher_mcore.main_watcher(), watcher_mfocus.main_watcher())
    except Exception as e:
        traceback.print_exc()
        await messenger(info=str(e), type=MsgType.ERROR)

def start_watching():
    asyncio.run(prepare_watcher())

if __name__ == '__main__':

    start_watching()