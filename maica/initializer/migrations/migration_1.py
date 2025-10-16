import asyncio
import os
from typing import *
from maica.maica_utils import *

upper_version = "1.1.007.post3"

async def migrate():

    maica_pool = await ConnUtils.maica_pool()
    try:
        await maica_pool.query_modify('RENAME TABLE cchop_archived TO crop_archived')
    except Exception as e:
        raise MaicaDbWarning(f'Couldn\'t rename table cchop_archived to crop_archived: {str(e)}, maybe manually done already?') from e
    finally:
        await maica_pool.close()
