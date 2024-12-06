python ./00essentials.py
. ./essentials_generated.ps1
Start-Process powershell.exe -ArgumentList "-Command python ./maica_ws.py" 
Start-Process powershell.exe -ArgumentList "-Command python ./maica_http.py" 
Start-Process powershell.exe -ArgumentList "-Command python ./00keepalived.py" 