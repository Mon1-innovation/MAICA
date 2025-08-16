#!/bin/bash

# 存储所有后台进程PID
pids_2=();pids_9=()

cleanup() {
    echo -e "\nCaught SIGINT, cleaning up..."
    # 向所有后台进程发送SIGINT
    for pid in "${pids_2[@]}"; do
        echo "$pid"
        kill -2 "$pid" 
    done
    for pid in "${pids_9[@]}"; do
        echo "$pid"
        kill -9 "$pid" 
    done
    echo "Quitting now!"
}

trap cleanup EXIT

# 启动主进程（前台）
python3 ../maica/00essentials.py

# 启动所有后台进程并记录PID
python3 ../maica/maica_ws.py &
pids_9+=($!)
python3 ../maica/maica_http.py &
pids_2+=($!)
python3 ../maica/00keepalived.py &
pids_2+=($!)
python3 ../maica/00nvsmiwatch.py &
pids_2+=($!)

for pid in "${pids[@]}"; do
    echo "$pid"
done


# 等待用户输入后退出
while true
    do read -p ""
done