import os
import time
import socket
import psutil
import platform
import subprocess
import schedule
import signal
from maica_utils import *
from rotate_cache import rotation_instance

def signal_handler(sig, frame):
    print(f'{__file__.split("/")[-1].split(".")[0]}: SIGINT recieved')
    exit(0)

signal.signal(signal.SIGINT, signal_handler)

def check_port(host, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    r = s.connect_ex((host, port))
    if r:
        return False
    else:
        return True

def force_ws_gc():
    while check_port('0.0.0.0', 5000):
        time.sleep(1)
        for c in psutil.net_connections():
            if c.laddr.port == 5000 and c.status == 'LISTEN':
                p = psutil.Process(c.pid)
                p.terminate()
                break
    print('Forcing gc: websocket process killed')
    p = subprocess.Popen([python3, "./maica_ws.py"])
    time.sleep(10)

def rotate_cache():
    rotation_instance()

if __name__ == "__main__":
    sysstruct = platform.system()
    match sysstruct:
        case 'Linux':
            python3 = 'python3'
        case 'Windows':
            python3 = 'python'
        case _:
            print('Your system is not supported!')
            quit()
    print(f'Keepalive daemon for {sysstruct} started')
    self_path = os.path.dirname(os.path.abspath(__file__))
    if load_env("FORCE_WSGC") == '1':
        schedule.every().day.at("04:00").do(force_ws_gc)
    if load_env('ROTATE_MSCACHE') != '0':
        schedule.every().day.at("04:00").do(rotate_cache)
    while True:
        time.sleep(5)
        ws_status = check_port('0.0.0.0', 5000)
        if not ws_status:
            print('Websocket process died, trying to pullup')
            try:
                p = subprocess.Popen([python3, os.path.join(self_path, "maica_ws.py")])
                i = 0
                while i <= 3:
                    i += 1
                    time.sleep(3)
                    statp = p.poll()
                    if statp == None:
                        print(f'Pullup check passed {i} times')
                    else:
                        broken = f'Websocket process pullup failed: {statp}'
                        break
            except Exception as excepted:
                broken = f'Host pullup command failed: {excepted}'
                break
        http_status = check_port('0.0.0.0', 6000)
        if not http_status:
            print('Http process died, trying to pullup')
            try:
                p = subprocess.Popen([python3, os.path.join(self_path, "maica_http.py")])
                i = 0
                while i <= 3:
                    i += 1
                    time.sleep(3)
                    statp = p.poll()
                    if statp == None:
                        print(f'Pullup check passed {i} times')
                    else:
                        broken = f'Http process pullup failed: {statp}'
                        break
            except Exception as excepted:
                broken = f'Host pullup command failed: {excepted}'
                break
        schedule.run_pending()
    if broken:
        print(f'Common failure caught in keepalived: {broken}\nStopping entire process')
        try:
            p = subprocess.Popen(["killall", python3])
            p.wait()
        except Exception:
            print('Stopping failed! Stop manually and check reason before restart')