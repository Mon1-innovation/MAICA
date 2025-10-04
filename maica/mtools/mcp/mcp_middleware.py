import os
import stat
import platform

from typing import *
from maica.maica_utils import *

def prep_bin(bin):
    st = os.stat(bin)
    os.chmod(bin, st.st_mode | stat.S_IEXEC)

def _serp_bin():
    match sysstruct():
        case 'Windows':
            return get_inner_path('bin/mi-serp-precompiled-binary-win.exe')
        case 'Linux':
            return get_inner_path('bin/mi-serp-precompiled-binary-linux')
        case _:
            raise OSError('Your system not supported')