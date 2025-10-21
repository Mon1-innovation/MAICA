import json
from dataclasses import dataclass

from maica.maica_utils import *

@dataclass
class TpAPIKeys():...

def pkg_init_api_keys():
    api_keys: dict = json.loads(G.A.TP_APIS)
    for k, v in api_keys.items():
        setattr(TpAPIKeys, k, v)

if __name__ == "__main__":
    pkg_init_api_keys()