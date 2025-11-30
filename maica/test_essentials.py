import asyncio
import platform
import colorama

from maica.maica_utils import sync_messenger, load_env, MsgType


def basic_chk():
    sysstruct = platform.system()
    assert sysstruct in ['Windows', 'Linux'], 'Your system not supported'

    curr_version, legc_version = load_env('MAICA_CURR_VERSION'), load_env('MAICA_VERSION_CONTROL')
    sync_messenger(info=f"Running MAICA Illuminator V{curr_version} on {sysstruct}", type=MsgType.PRIM_SYS)

    try:
        proxyaddr = load_env('MAICA_PROXY_ADDR')
    except Exception:
        proxyaddr = ''
    if proxyaddr:
        print(f"Global proxy detected, using {proxyaddr}")

    else:
        print("Global proxy absent")