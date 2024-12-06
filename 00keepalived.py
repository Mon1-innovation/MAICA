import os
import time
import socket
import platform
import subprocess

def check_port(host, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    r = s.connect_ex((host, port))
    if r:
        return False
    else:
        return True

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
    while True:
        time.sleep(5)
        ws_status = check_port('0.0.0.0', 5000)
        if not ws_status:
            print('Websocket process died, trying to pullup')
            try:
                p = subprocess.Popen([python3, "./maica_ws.py"])
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
                p = subprocess.Popen([python3, "./maica_http.py"])
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
    if broken:
        print(f'Common failure caught in keepalived: {broken}\nStopping entire process')
        try:
            p = subprocess.Popen(["killall", python3])
            p.wait()
        except:
            print('Stopping failed! Stop manually and check reason before restart')