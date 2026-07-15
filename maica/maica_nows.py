from typing import *
from maica.maica_utils import *

class NoWsCoroutine(AsyncCreator):
    """
    The fundation of workers.
    Most things here have been moved away since v1.3, but we still keep it.
    """

    # Initialization
    def __init__(
            self,
            fsc: FullSocketsContainer
        ):
        self.fsc = fsc

        self.settings = fsc.maica_settings
        self.remote_addr = None

    async def _ainit(self):
        pass

if __name__ == "__main__":
    pass
