python ../maica/00essentials.py
#. ./essentials_generated.ps1
Start-Process powershell.exe -ArgumentList "-Command python ../maica/maica_ws.py" 
Start-Process powershell.exe -ArgumentList "-Command python ../maica/maica_http.py" 
Start-Process powershell.exe -ArgumentList "-Command python ../maica/00keepalived.py" 
Start-Process powershell.exe -ArgumentList "-Command python ../maica/00nvsmiwatch.py" 