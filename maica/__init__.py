"""
MAICA Illuminator (Backend) library.
Always call init() before actually using!
"""
from .maica_starter import check_params, check_data_init

def init(envdir: str=None, extra_envdir: list=None, silent=False, **kwargs):
    check_params(envdir=envdir, extra_envdir=extra_envdir, silent=silent, kwargs=kwargs)
    check_data_init()
