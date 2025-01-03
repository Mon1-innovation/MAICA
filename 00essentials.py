from loadenv import load_env
import re
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
    if load_env('PROXY_EXCLUDE') == "1":
        main_host = load_env('MCORE_ADDR'); mfocus_host = load_env('MFOCUS_ADDR')
        urls = [main_host, mfocus_host]; hosts = []
        host_filter = re.compile(r"^http://(.*?)(:|/|$).*", re.I)
        for url in urls:
            hosts.append(host_filter.match(url)[1])
        hosts.append(load_env("DB_ADDR"))
        hosts_str = ", ".join(hosts)
        print(f"--Excluding {hosts_str} as local servers")
    with open(filename, 'w+') as emittion:
        match sysstruct:
            case 'Linux':
                emittion.write(f"export HTTP_PROXY={proxyaddr}\nexport HTTPS_PROXY={proxyaddr}\nexport http_proxy={proxyaddr}\nexport https_proxy={proxyaddr}\n")
                if load_env('PROXY_EXCLUDE'):
                    emittion.write(f"export NO_PROXY='{hosts_str}'\nexport no_proxy='{hosts_str}'\n")
            case 'Windows':
                emittion.write(f"set HTTP_PROXY={proxyaddr}\nset HTTPS_PROXY={proxyaddr}\nset http_proxy={proxyaddr}\nset https_proxy={proxyaddr}\n")
                if load_env('PROXY_EXCLUDE'):
                    emittion.write(f"set NO_PROXY='{hosts_str}'\nset no_proxy='{hosts_str}'\n")
else:
    print("Global proxy absent")
    with open(filename, 'w+') as emittion:
        pass
