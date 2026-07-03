"""
Just as we said, we need a pipeline to connect everything pre-generation together.

Could include:
- MFocus main of course
- mf_check_mt
...
"""
import asyncio

from typing import *

from .mfocus_llm import MfPipeliner
from .agent_modules import AgentTools
from maica.mtools import make_postmail
from maica.maica_utils import *

_Bt = BilingualText

async def pre_core_pipelines(
        query: str,
        session: MaicaSession,
        fsc: FullSocketsContainer,
        sp: SessionPersistent,
        st: SessionTrigger,
    ):
    """Schedule everything here."""
    mfp = MfPipeliner(fsc, sp)

    session_item = session[-1]

    if not (
        isinstance(
            session_item.context.known_info,
            dict
        ) and not session_item.context.known_info
    ):
        session_item.context.known_info = {}

    async def mf_pipeline():
        """
        This shall go last in sequence, since any extra known_info is useful.
        The ultimate goal of MFocus is just filling known_info.
        """
        if (
            fsc.maica_settings.use_mf_now
        ):

            # prompt_pname_repl implementation
            if fsc.maica_settings.extra.prompt_pname_repl:
                pname = sp.pname
                if pname:
                    session_item.context.player_name = pname

            generated_guidance, parsed_results = await MfPipeliner.run_mf_pipeline(query)

            # Then we inject what we got into session
            if (
                fsc.maica_settings.extra.mf_llm_concl
                and generated_guidance
            ):
                session_item.context.known_info.update({"generated_guidance": generated_guidance})
            else:
                session_item.context.known_info.update(parsed_results)

    async def precheck_mt_pipeline():
        """Former react_trigger. Pre-detects if request could be satisfied by mt."""
        if (
            # This does not actually require mf, suprisingly
            fsc.maica_settings.use_mt_now
            and fsc.maica_settings.extra.mf_precheck_mt
        ):
            requested, operation = await st.predict_trigger(query)

            if requested:
                if operation:
                    t = _Bt(
                        f"你可以完成{{player_name}}的请求({operation}), 请作正面回答.",
                        f"You can satisfy {{player_name}}'s request({operation}), please answer positively.",
                    )
                else:
                    t = _Bt(
                        "{player_name}的请求可能无法完成, 请根据实际情况作答.",
                        "{player_name}'s request could be not satisfiable, please answer according to actual situation.",
                    )
                session_item.context.known_info.update({"mt_prediction": t})

    async def form_mp_pipeline():
        """
        This shall go first in sequence, since it fills content.
        We have a tiny clever design to let mn detect if mp is poem or letter. Now we do it here together with letter forming.
        """
        if (
            fsc.maica_settings.temp.mpostal.content
        ):
            prompt_text = await make_postmail(fsc)
            session_item.content = prompt_text

    async def const_mf_pipeline():
        """Call tools for mf_const_tools and mf_const_sf_access."""
        mf_const_tools = fsc.maica_settings.extra.mf_const_tools
        mf_sf_access_impl = fsc.maica_settings.extra.mf_sf_access_impl
        mf_const_sf_access = fsc.maica_settings.extra.mf_const_sf_access

        tools_results: dict[
            str,
            Tuple[str, Any],
        ] = {}

        if mf_const_tools >= 1:

            toolbox = AgentTools(fsc, sp)

            for tool_name in ("time_acquire", "event_acquire"):
                tools_results[tool_name] = await getattr(toolbox, tool_name)()

        if mf_const_tools >= 2:
            for tool_name in ("date_acquire", "weather_acquire"):
                tools_results[tool_name] = await getattr(toolbox, tool_name)()

        if (
            mf_const_sf_access >= 1
            and not mf_sf_access_impl <= 0
        ):
            tool_name = "persistent_acquire"
            tools_results[tool_name] = await getattr(toolbox, tool_name)(query=query)

        parsed_results = MfPipeliner.parse_tools_results(tools_results)
        session_item.context.known_info.update(parsed_results)

    # Finally, form all these together
    tasks_stages: list[list[Callable[[], Awaitable]]] = [
        [form_mp_pipeline],
        [precheck_mt_pipeline, const_mf_pipeline],
        [mf_pipeline],
    ]

    for stage in tasks_stages:
        await asyncio.gather(
            *[task() for task in stage]
        )

    # And we should be good to move on