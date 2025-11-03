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
from maica.maica_utils import *

class _FakeSQLiteConn():
    async def __aenter__(self):
        return self
    async def execute(self, *args, **kwargs):
        return self
    async def __aexit__(self, exc_type, exc_val, exc_tb):...

class NvWatcher(AsyncCreator):
    def __init__(self, node: str, prefix="maica"):
        self.write_nvw = G.A.WRITE_NVW == '1'
        self.node = node
        subset_name = 'A' if prefix in ['maica', 'a'] else 'T'
        subset = getattr(G, subset_name)

        self.node_name = getattr(subset, f'{node.upper()}_NODE')
        self.node_user = getattr(subset, f'{node.upper()}_USER')
        self.node_pwd = getattr(subset, f'{node.upper()}_PWD')
        self.is_dead = False

        self.node_addr = get_host(getattr(subset, f'{node.upper()}_ADDR'))

    async def _ainit(self):
        if self.is_active:
            try:
                await self._connect_remotes()
                await self._initiate_db()
            except Exception:
                self.is_dead = True

    @property
    def is_active(self):
        if not self.node_name or not self.node_user or not self.node_pwd or not self.node_addr or self.is_dead:
            return False
        else:
            return True

    async def _query_nvsmi(self, ssh_client: asyncssh.connection.SSHClientConnection, keys=[]):
        command = f"nvidia-smi --query-gpu={','.join(keys)} --format=csv"
        result = await ssh_client.run(command, check=True)
        csv_capt = csv.DictReader(result.stdout.split('\n'))
        return list(csv_capt)

    async def _connect_remotes(self):
        self.node_ssh = await asyncssh.connect(host=self.node_addr, username=self.node_user, password=self.node_pwd, known_hosts=None)

    async def _initiate_db(self):
        self.db_path = get_inner_path('.nvsw.db')
        async with aiosqlite.connect(self.db_path, autocommit=True) if self.write_nvw else _FakeSQLiteConn() as db_client:
            self.gpu_overall = []

            basis_keys = ['name', 'memory.total']
            basic_result = await self._query_nvsmi(self.node_ssh, basis_keys)
            await db_client.execute(f'CREATE TABLE IF NOT EXISTS `{self.node_name}` (id INT PRIMARY KEY, name TEXT, memory TEXT, tflops TEXT, dynamic TEXT);')

            for i, gpu in enumerate(basic_result):
                name = gpu["name"]; memory = gpu[" memory.total [MiB]"]; tflops = '200'
                
                match name:
                    case n if 'PRO 6000' in n:
                        tflops = '460'
                    case n if '5090' in n:
                        tflops = '420'
                    case n if '4090' in n:
                        tflops = '330'

                await db_client.execute(f'INSERT OR REPLACE INTO `{self.node_name}` (id, name, memory, tflops, dynamic) VALUES ({i}, "{name}", "{memory}", "{tflops}", "[]");')
                self.gpu_overall.append([i, name, memory, tflops, []])

    async def _append_dynamic(self, history: list, gpu: dict):
        gpu_values = list(gpu.values())
        gpu_stats = {"u": gpu_values[0].strip('%').strip(), "m": gpu_values[1].strip('BiM').strip(), "p": gpu_values[2].strip('W').strip()}
        if len(history) >= 36:
            history.pop()
        history.insert(0, gpu_stats)
        return history

    async def main_watcher(self):
        if not self.is_active:
            if self.is_dead:
                await messenger(info=f"Cannot connect to SSH of {self.node}, freezing watcher", type=MsgType.WARN)
            else:
                await messenger(info=f"Necessary info not complete for watching {self.node}, freezing watcher", type=MsgType.LOG)
            await sleep_forever()
        else:
            await messenger(info=f'Necessities complete for watching {self.node}, starting watcher', type=MsgType.PRIM_LOG)

        self.dynamics_curr = []
        dynamic_keys = ['utilization.gpu', 'memory.used', 'power.draw']
        while True:
            dynamics_new = await self._query_nvsmi(self.node_ssh, dynamic_keys)
            async with aiosqlite.connect(self.db_path, autocommit=True) if self.write_nvw else _FakeSQLiteConn() as db_client:

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

    async def wrapped_main_watcher(self):
        FAIL_TIMES = 5
        FAIL_PERIOD = 300
        start_times = LimitedList(FAIL_TIMES, [time.time()])
        while len(start_times.list) <= 5 or start_times[-1] - start_times[0] >= FAIL_PERIOD:

            # We consider 5 failures in 5 minute as complete failure
            try:
                await self.main_watcher()
            except Exception as e:
                time_now = time.time()
                await messenger(info=f'Watcher temporary failure after {int(time_now - start_times[-1])}sec: {str(e)}', type=MsgType.WARN)
                start_times.append(time_now)
        
        # If while loop quitted, the complete failure has happened
        raise MaicaConnectionWarning(f'Watcher query failed {FAIL_TIMES} times in {FAIL_PERIOD}sec', '503')
    
    def get_statics_inside(self):
        if not self.is_active:
            return {}
        
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
            os.remove(self.db_path)
        except Exception:
            pass

async def prepare_watcher():
    watcher_mcore = await NvWatcher.async_create('mcore', 'maica')
    watcher_mfocus = await NvWatcher.async_create('mfocus', 'maica')
    try:
        await asyncio.gather(watcher_mcore.main_watcher(), watcher_mfocus.main_watcher())
    except Exception as e:
        traceback.print_exc()
        await messenger(info=str(e), type=MsgType.ERROR)

def start_watching():
    asyncio.run(prepare_watcher())

if __name__ == '__main__':

    start_watching()