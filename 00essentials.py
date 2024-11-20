from loadenv import load_env
import platform
sysstruct = platform.system()
cur_v, last_v = load_env('VERSION_CONTROL').split(';',1)
print(f"Running MAICA Illuminator V{cur_v} on {sysstruct}")
match sysstruct:
    case 'Linux':
        filename = '.essentials_generated.sh'
    case 'Windows':
        filename = '.essentials_generated.ps1'
    case _:
        print('Your system is not supported!')
        quit()
try:
    proxyaddr = load_env('PROXY_ADDR')
except:
    proxyaddr = ''
if proxyaddr:
    print(f"Global proxy detected, using {proxyaddr}")
    with open(filename, 'w+') as emittion:
        match sysstruct:
            case 'Linux':
                emittion.write(f"export HTTP_PROXY={proxyaddr}\nexport HTTPS_PROXY={proxyaddr}\nexport http_proxy={proxyaddr}\nexport https_proxy={proxyaddr}")
            case 'Windows':
                emittion.write(f"set http_proxy={proxyaddr}\nset https_proxy={proxyaddr}")
else:
    print("Global proxy absent")
    with open(filename, 'w+') as emittion:
        pass
