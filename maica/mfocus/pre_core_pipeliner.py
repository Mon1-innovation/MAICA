"""
Just as we said, we need a pipeline to connect everything pre-generation together.

Could include:
- MFocus main of course
- mf_check_mt
...
"""
from typing import *

from .mfocus_llm import MfPipeliner
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

    if not isinstance(
        session_item.context.get("known_info"),
        dict
    ):
        session_item.context["known_info"] = {}

    async def mf_pipeline():
        """The ultimate goal of MFocus is just filling known_info."""
        generated_guidance, tools_results = await MfPipeliner.run_mf_pipeline(query)

        # Then we inject what we got into session
        if (
            fsc.maica_settings.extra.mf_llm_concl
            and generated_guidance
        ):
            session_item.context["known_info"].update({"generated_guidance": generated_guidance})
        else:
            session_item.context["known_info"].update({k: v[0] for k, v in tools_results.items()})

        # prompt_pname_repl implementation
        if fsc.maica_settings.extra.prompt_pname_repl:
            pname = sp.pname
            if pname:
                session_item.context["player_name"] = pname

    async def precheck_mt_pipeline():
        """Former react_trigger. Pre-detects if request could be satisfied by mt."""
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
            session_item.context["known_info"].update({"mt_prediction": t})

    async def precheck_mp_pipeline():
        """We have a tiny clever design to let mn detect if mp is poem or letter. Now we do it here."""