
import asyncio

from typing import *

from maica.maica_utils import *


class GenericModelHelper(AsyncCreator):
    """Main toolbox."""

    def __init__(self, fsc: FullSocketsContainer):
        self.fsc = fsc

    async def _ainit(self):
        pass


