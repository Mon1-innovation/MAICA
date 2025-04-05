import os
import re
import json
import time
import csv
import sqlite3
import traceback
import paramiko
from maica_utils import *

def nvbasis(ssh_client, db_client, table_name):
    stdin, stdout, stderr = ssh_client.exec_command("nvidia-smi --query-gpu=name,memory.total --format=csv")
    std_out = stdout.read()
    std_err = stderr.read()
    if not std_out:
        raise Exception(f'Empty stdout: {std_err}')
    # print(std_out.decode())
    csv_capt = csv.DictReader(std_out.decode().split('\n'))
    gpu_basis = []
    for line in csv_capt:
        gpu_basis.append(line)
    print(gpu_basis)
    return gpu_basis

def nvwatch(ssh_client, db_client, table_name):
    stdin, stdout, stderr = ssh_client.exec_command("nvidia-smi --query-gpu=utilization.gpu,memory.used,power.draw --format=csv")
    std_out = stdout.read()
    std_err = stderr.read()
    if not std_out:
        raise Exception(f'Empty stdout: {std_err}')
    # print(std_out.decode())
    csv_capt = csv.DictReader(std_out.decode().split('\n'))
    # gpu id, [[0%, 0%, 50w], [100%, 100%, 500w]]
    gpu_curr_stat = []
    for line in csv_capt:
        gpu_curr_stat.append(line)
    #print(gpu_curr_stat)
    gpu_count = len(gpu_curr_stat)
    for gpu in [x for x in range(gpu_count)]:
        try:
            res1 = db_client.execute(f'SELECT history FROM `{table_name}` WHERE id = {gpu};')
            if not res1:
                raise Exception('No data')
            else:
                history = json.loads(res1.fetchall()[0][0])
        except:
            traceback.print_exc()
            history = []
        this_gpu_curr_stat = {"u":gpu_curr_stat[gpu]["utilization.gpu [%]"].strip('%').strip(' '),"m":gpu_curr_stat[gpu][" memory.used [MiB]"].strip('BiM').strip(' '),"p":gpu_curr_stat[gpu][" power.draw [W]"].strip('W').strip(' ')}
        history.insert(0, this_gpu_curr_stat)
        #print(history)
        if len(history) > 36:
            history.pop()
        db_client.execute(f'UPDATE `{table_name}` SET history = \'{json.dumps(history, ensure_ascii=False)}\' WHERE id = {gpu}')

def nvwatchd(hosts, users, pwds, tables):
    excepted = ''
    client_list = []
    try:
        i=0
        for host in hosts:
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy)
            ssh_client.connect(hostname=host, port=22, username=users[i], password=pwds[i])
            client_list.append(ssh_client)
            i+=1
        db_client = sqlite3.connect('./.nvsw.db', autocommit=True)
        db_client.execute(f'CREATE TABLE IF NOT EXISTS `{load_env('MCORE_NODE')}` (id INT PRIMARY KEY, name TEXT, memory TEXT, history TEXT);')
        db_client.execute(f'CREATE TABLE IF NOT EXISTS `{load_env('MFOCUS_NODE')}` (id INT PRIMARY KEY, name TEXT, memory TEXT, history TEXT);')
        i=0
        for client in client_list:
            basis = nvbasis(client, db_client, tables[i])
            j=0
            for gpu_info in basis:
                db_client.execute(f'INSERT OR REPLACE INTO `{tables[i]}` (id, name, memory, history) VALUES ({j}, "{gpu_info["name"]}", "{gpu_info[" memory.total [MiB]"]}", "[]");')
                j+=1
            i+=1
        while True:
            i=0
            for client in client_list:
                nvwatch(client, db_client, tables[i])
                i+=1
            time.sleep(5)
    except Exception as excepted:
        #traceback.print_exc()
        pass
    finally:
        for client in client_list:
            client.close()
        try:
            os.remove('./.nvsw.db')
        except:
            pass
        print(f'Quiting nvwatchd!')

if __name__ == '__main__':
    if load_env("ENABLE_NVW") == '1':
        host_filter = re.compile(r"^https?://(.*?)(:|/|$).*", re.I)
        mcore_addr = host_filter.match(load_env('MCORE_ADDR'))[1]
        mfocus_addr = host_filter.match(load_env('MFOCUS_ADDR'))[1]
        hosts = [mcore_addr, mfocus_addr]
        users = [load_env('MCORE_USER'), load_env('MFOCUS_USER')]
        pwds = [load_env('MCORE_PWD'), load_env('MFOCUS_PWD')]
        tables = [load_env('MCORE_NODE'), load_env('MFOCUS_NODE')]
        while True:
            try:
                nvwatchd(hosts, users, pwds, tables)
            except:
                time.sleep(10)