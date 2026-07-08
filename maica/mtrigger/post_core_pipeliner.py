"""
And as pre_core_pipeliner, we need a pipeline to connect everything post-generation together.

And ofc we start from MTrigger.
This could also include many things like saving session and MSpire cache.
And quality check, for sure.
"""

import asyncio

from typing import *

from .mtrigger_llm import MtPipeliner
from maica.mtools import ms_to_cache, quality_chk
from maica.maica_utils import *

_Bt = BilingualText

async def post_core_pipelines(
        session: MaicaSession,
        fsc: FullSocketsContainer,
        sp: SessionPersistent,
        st: SessionTrigger,
    ):
    """Schedule everything here."""
    session_item = session[-1]

    async def mt_pipeline():
        """
        I think this could go parallelly with other pipelines.
        """
        if (
            fsc.maica_settings.use_mt_now
        ):

            mtp = MtPipeliner(session, fsc, st)
            await mtp.run_mt_pipeline()

    async def quality_chk_pipeline():
        """gen_quality_chk implementation."""
        if (
            fsc.maica_settings.extra.gen_quality_chk
        ):
            res, cfd = await quality_chk(session, fsc)
            await fsc.messenger(
                'maica_quality_status',
                [res, cfd],
                200,
            )

    async def save_ms_pipeline():
        """If we have ms cache to save."""
        if (
            fsc.maica_settings.temp.mspire._mfc_m
            and fsc.maica_settings.temp.mspire._mfc_m.hash
            and not fsc.maica_settings.temp.mspire._mfc_m.result
        ):
            mfc_m = fsc.maica_settings.temp.mspire._mfc_m
            mfc_m.result = session_item.content

            await ms_to_cache(mfc_m, fsc)

    async def save_session_pipeline():
        """Saving session."""
        length_stat = await session.wrapped_save()

        match length_stat:
            case 2:
                await fsc.messenger(
                    'maica_history_sliced',
                    f"Session exceeded {fsc.maica_settings.basic.session_len_limit} characters and sliced",
                    204,
                )
            case 1:
                await fsc.messenger(
                    'maica_history_slice_hint',
                    f"Session exceeded {fsc.maica_settings.basic.session_len_limit * (2/3)} characters, will slice at {fsc.maica_settings.basic.session_len_limit}",
                    200,
                    no_print=True,
                )

