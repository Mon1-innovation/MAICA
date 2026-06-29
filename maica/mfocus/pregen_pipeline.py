

from typing import *

from maica.maica_utils import *

class SessionPersistentPipeliner():
    """Mostly ex-bound methods here to keep SessionPersistent flexible."""
    session_num: int
    fsc: FullSocketsContainer
    content: dict
    content_temp: dict

