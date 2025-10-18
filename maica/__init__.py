"""
MAICA Illuminator (Backend) library.
Always call init() before actually using!
"""
from .maica_utils import silent

from .maica_starter import check_params, check_data_init

def init(envdir: str=None, extra_envdir: list=None, silent=False, ignore_envc=False, **kwargs):
    if ignore_envc:
        kwargs['MAICA_IS_REAL_ENV'] = '1'
    check_params(envdir=envdir, extra_envdir=extra_envdir, silent=silent, **kwargs)
    check_data_init()

# Exports

from . import maica_utils
from .maica_starter import start_all

__all__ = [
    'maica_utils',
    'init',
    'start_all',
]