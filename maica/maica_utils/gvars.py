"""Import layer 0"""
import os

from dataclasses import dataclass
from typing import *

online_dict = {}

def pkg_init_gvars():
    global G

    for k, v in {k: v for k, v in os.environ.items() if k.startswith('MAICA_')}.items():
        setattr(G.A, k.removeprefix('MAICA_'), v)

    for k, v in {k: v for k, v in os.environ.items() if k.startswith('MTTS_')}.items():
        setattr(G.T, k.removeprefix('MTTS_'), v)

    # print(vars(G.A))

@dataclass
class _G():
    """All env vars."""

    @dataclass
    class _A():
        """
        MAICA ... env vars.
        Notice: anything under this is string!
        """
        def __getattr__(self, k):
            return None
        
    @dataclass
    class _T():
        """
        MTTS ... env vars.
        Notice: anything under this is string!
        """
        def __getattr__(self, k):
            return None
        
    def __post_init__(self):
        self.A = self._A()
        self.T = self._T()
        
G = _G()