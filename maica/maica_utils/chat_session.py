"""
Import layer 4.1
This module is for v2 session management, applied for DAA4.
"""
from __future__ import annotations

import time
import orjson
import types
import sqlalchemy
from sqlalchemy.orm import load_only

from typing import *
from pydantic import BaseModel, Field, model_validator
from pydantic.dataclasses import dataclass as pdataclass
from .maica_utils import *
from .fsc_late import *
from .db_bound_obj import DbBoundObject
from .database_utils import *
from .database_models import *
from .emotions import *

_Bt = BilingualText


def _list_to_bullets(l: list[str | BilingualText], indent: int = 0):
    """Has a leading slash n, no trailing."""
    bt = _Bt()
    for i in l:
        bt += " " * indent
        bt += "\n- "
        bt += i

    return bt


class MaicaSessionItem(BaseModel):
    """Element of MaicaSession."""


    class Context(BaseModel):
        """Specifically context object of MaicaSessionItem."""
        strict_conv: bool = True
        player_name: str = "[player]"
        apply_nickname: bool = True
        nsfw_acceptive: bool = True
        known_info: dict[
            str,
            Union[
                str,
                BilingualText,
            ]
        ] = Field(default_factory=dict)
        image_urls: list[str] = Field(default_factory=list)
        memory_concl: Optional[str] = None
        generic_help: list[str] = Field(default_factory=list)


    role: Literal["system", "user", "assistant", "misc"] = 'misc'
    content: str | BilingualText = ''
    target_lang: Optional[Literal['zh', 'en', 'auto']] = None
    context: Context = Field(default_factory=Context)

    # If item role is misc, we stop using maica format and store entire object.
    preserved: dict = Field(default_factory=dict)

    timestamp: float = Field(default_factory=time.time)


    # We override its init to allow position-arguments initialization
    def __init__(self, *args, **kwargs):
        if args:
            field_names = list(self.__class__.model_fields.keys())
            if len(args) > len(field_names):
                raise TypeError(f"Too many positional arguments for {self.__class__.__name__}")

            for i, value in enumerate(args):
                if i < len(field_names):
                    if field_names[i] not in kwargs:
                        kwargs[field_names[i]] = value
                    else:
                        raise RuntimeError(f"{field_names[i]} is passed twice for MaicaSessionItem")

        super().__init__(**kwargs)


    def json(self) -> dict:

        # exclude_unset does not track sub-attributes
        # Normally we just ignore those because only those on role=user is meaningful
        kwargs = {}
        if self.role != "user":
            kwargs["exclude_unset"] = True
        return self.model_dump(**kwargs)

    
    def utilize(self, text_only: Literal[False, None, True] = None) -> dict:
        """
        text_only:
        False: force image
        None: auto decide (for core model)
        True: disable image
        """
        if self.role in ["system", "user", "assistant"]:
            d = {"role": self.role}
            content = to_str(self.content, self.target_lang)

            if (
                (
                    is_mcore_vl()
                    and text_only is not True
                ) or
                text_only is False
            ):
                image_urls = self.context.image_urls
                if image_urls:
                    content = [
                        {"type": "text", "text": content}
                    ]
                    for url in image_urls:
                        content.append({"type": "image_url", "image_url": {"url": url}})

            d["content"] = content
            return d
        
        else:
            return self.preserved


    def form_known_info(self):
        """
        Form the known_info dict into a str. Maybe we use markdown since it's more modern.
        Note that in v1.3, we have unified known_info, so it's completely dict[str, str].
        """
        known_info = self.context.known_info
        # {
        #     "time_acquire": "现在是...",
        #     "date_acquire": "今天是...",
        #     "persistent_acquire": "莫妮卡...; [player]...",
        #     "mt_prediction": "用户的请求是可以完成的...",

        # Specially, mf_llm_concl is also here:
        #     "generated_guidance": "总的来说, ...",
        # If generated_guidance exist, we ignore everything else.
        # }

        if known_info:
            if "generated_guidance" in known_info:
                known_str = known_info["generated_guidance"]

            else:
                known_str = _list_to_bullets(known_info.values()).to_str(self.target_lang)
        else:
            known_str = ""
        return known_str


    def form_generic_help(self):
        """Much simpler. This needs a default placeholder since it could actually be empty."""
        generic_help = self.context.generic_help
        generic_str = _list_to_bullets(generic_help).to_str(self.target_lang)

        if not generic_str:
            generic_str = _Bt(
                "当前暂未提供.",
                "Currently not provided.",
            ).to_str(self.target_lang)

        return generic_str

    
    def context_from_fsc(self, fsc: FullSocketsContainer):
        """Gets session item specifics from a fsc."""
        self.target_lang = fsc.maica_settings.basic.target_lang

        context = self.context
        context.strict_conv = fsc.maica_settings.temp.common.strict_conv
        context.apply_nickname = fsc.maica_settings.extra.prompt_allow_nickname
        context.nsfw_acceptive = fsc.maica_settings.extra.nsfw_acceptive
        context.image_urls = fsc.maica_settings.temp.mvista.mv_imgs or []


class MaicaSession(list[MaicaSessionItem], DbBoundObject):
    """
    The v2 session.
    """
    SESSION_DB_MIN = 1
    _model = SqlChatSession

    def clear(self):
        list.clear(self)
        DbBoundObject.clear(self)

    def on_acquire(self):
        if self.session_num <= 0:
            self.reset()

    def __init__(self, session_num: int = 0, fsc: Optional[FullSocketsContainer] = None, *args, **kwargs):
        # Initialize the base list class
        list.__init__(self, *args, **kwargs)
        DbBoundObject.__init__(self, session_num, fsc)
        # It should also autorun DbBoundObject.__post_init__()
        # which also runs self.reset()
    
    def load(self, item: Union[list, str]):
        self.clear()
        super().load(item)
        for i in self.content:
            self.append(
                MaicaSessionItem.model_validate(i)
            )

    def local_sync(self, from_which = "content"):
        if from_which == "content":
            self.content = self.json()
        super().local_sync(from_which)

    def sanitize(self):
        # Make sure system is #0
        if not len(self) or not self[0].role == "system":
            self.insert(0, MaicaSessionItem("system"))

    def _utilize_context(
            self,
            manual_prompt: Optional[Literal[True] | str | BilingualText] = None,
            ignore_additions: bool = False,
            extra_info: Optional[str | BilingualText] = None,
        ):
        """
        Parses corresponding contexts into prompt information, and automatically replaces it.
        Manual prompt mainly for tool LLMs. This way we make messages construction look prettier.
        """

        # First sanitize
        self.sanitize()
        if not len(self) >= 1:
            raise MaicaInputWarning("No item could be utilized", 404)

        # Then acquire context
        prompt_item = self[0]
        prompt_context = prompt_item.context

        for item in reversed(self):
            if item.role == "user":
                curr_item = item
                break
        else:
            curr_item = prompt_item
        curr_context = curr_item.context

        target_lang = curr_item.target_lang

        # Then generate system prompt from context
        if curr_context.strict_conv:
            prompt = _Bt(
                G.A.PROMPT_ZC,
                G.A.PROMPT_EC,
                G.A.PROMPT_AC,
            )
        else:
            prompt = _Bt(
                G.A.PROMPT_ZW,
                G.A.PROMPT_EW,
                G.A.PROMPT_AW,
            )

        # Extend the prompt for conditions
        if curr_context.nsfw_acceptive:
            prompt += _Bt(
                G.A.PROMPT_ZNP,
                G.A.PROMPT_ENP,
                G.A.PROMPT_ANP
            )

        # At this point, manual_prompt should kick in
        # If manual_prompt is provided, we ignore strict_conv, nsfw_acceptive
        if manual_prompt:
            if manual_prompt is True:
                manual_prompt = prompt_item.content

            if isinstance(manual_prompt, _Bt):
                prompt = manual_prompt
            elif isinstance(manual_prompt, str):
                prompt = _Bt(manual_prompt)

        # For later formatting, like {known_info}
        format_kvs = {}

        if not ignore_additions:
            # Parse known info
            if curr_context.known_info:
                prompt += "\n"
                prompt += _Bt(
                    G.A.PROMPT_ZKP,
                    G.A.PROMPT_EKP,
                    G.A.PROMPT_AKP,
                )
                format_kvs["known_info"] = curr_item.form_known_info()

            # Add memory conclusion
            if prompt_context.memory_concl:
                prompt += "\n"
                prompt += _Bt(
                    G.A.PROMPT_ZMP,
                    G.A.PROMPT_EMP,
                    G.A.PROMPT_AMP,
                )
                format_kvs['memory_concl'] = '\n' + prompt_context.memory_concl

            # Add generic help
            # We do not want to add for mfocus, it's kinda useless, so judge by manual_prompt
            if not manual_prompt:
                # We decide by constant because even if no help text acquired, we still want to add emo help
                if G.A.MCORE_GENERIC and int(G.A.MCORE_GENERIC):
                    prompt += "\n"
                    prompt += _Bt(
                        G.A.PROMPT_ZGP,
                        G.A.PROMPT_EGP,
                        G.A.PROMPT_AGP,
                    )
                    format_kvs['emo_list'] = _list_to_bullets(zlist_ai if target_lang == 'zh' else elist_ai).to_str(target_lang)
                    format_kvs['ds_examples'] = curr_item.form_generic_help()

            # Add extra info if required
            if extra_info:
                prompt += "\n"
                prompt += extra_info

            for k, v in format_kvs.items():
                format_kvs[k] = to_str(v, target_lang)

        prompt = prompt.to_str(target_lang)

        nickname = _Bt(
            "(昵称[player_nickname])",
            "(nickname [player_nickname])",
        )
        pname_format_kvs = {
            "player_name": curr_context.player_name,
            "player_nickname": nickname.to_str(target_lang) if curr_context.apply_nickname else "",
        }
        # First handle info
        prompt = prompt.format_map(SafeFormatDict(format_kvs))
        # Then handle names, to include name in info
        prompt = prompt.format_map(SafeFormatDict(pname_format_kvs))

        # Then inject
        # Note that system prompt item should not be modified from external
        self[0].content = prompt

        # Uncomment this for debugging
        # print(prompt)

    def json(self) -> list:
        self._utilize_context()
        return [i.json() for i in self]
    
    def utilize(
            self,
            text_only: Literal[False, None, True] = None,
            manual_prompt: Optional[Literal[True] | str | BilingualText] = None,
            ignore_additions: bool = False,
            extra_info: Optional[str | BilingualText] = None,
        ):
        # If session == -1, we shall preserve the prompt as-is
        # If using custom inner sessions, override params insead of using -1
        session_num = self.session_num
        if session_num >= 0:
            self._utilize_context(manual_prompt, ignore_additions, extra_info)
        else:
            self.sanitize()
        return [i.utilize(text_only) for i in self]
    
    async def to_partial_archive(self):
        """To crop_archived."""
        # Common
        self._check_ess()

        # Ensure row exists
        if not self.prim_key_id:
            await self.init_db()

        async with DatabaseUtils.SessionData() as dbs:
            async with dbs.begin():
                model = SqlCropArchived

                stmt = sqlalchemy.select(model).where(
                    model.chat_session_id == self.prim_key_id,
                    model.archived.is_(False),
                ).options(
                    load_only(model.id, model.content)
                )

                obj = await dbs.scalar(stmt)
                archive_items = self.json()
                if not obj:
                    archive_content = orjson.dumps(archive_items).decode()
                    obj = model(
                        chat_session_id=self.prim_key_id,
                        content=archive_content,
                    )
                    dbs.add(obj)

                else:
                    archive_content = obj.content
                    archive_content_j = orjson.loads(archive_content) if archive_content else []
                    archive_content_j.extend(archive_items)
                    archive_content = orjson.dumps(archive_content_j).decode()
                    obj.content = archive_content

                should_seal = len(archive_content) >= 100000
                obj.archived = should_seal

        sync_messenger(info=f"Partial archive made for session id {self.prim_key_id}, current length {len(archive_content)}", type=MsgType.DEBUG)

    async def to_entire_archive(self):
        """To csession_archived."""
        # Common
        self._check_ess()

        # We don't need to archive if no actual content
        if not len(self) > 1:
            sync_messenger(info="Entire archive is equivalently empty, ignoring", type=MsgType.DEBUG)
            return

        # Ensure row exists
        if not self.prim_key_id:
            await self.init_db()

        async with DatabaseUtils.SessionData() as dbs:
            async with dbs.begin():
                model = SqlCsessionArchived

                obj = model(
                    chat_session_id=self.prim_key_id,
                    content=orjson.dumps(self.json()).decode(),
                )
                dbs.add(obj)

        sync_messenger(info=f"Entire archive made for session id {self.prim_key_id}, items {len(self)}", type=MsgType.DEBUG)
    
    async def crop_length(self) -> Tuple[MaicaSession, Literal[0, 1, 2]]:
        """Making it V2 style."""
        use_api = bool(int(G.A.CALC_TOKENS))
        max_length = self.fsc.maica_settings.basic.session_len_limit
        warn_length = int(max_length * (2/3))
        async def _tokens_calc(messages):
            # This method lets model deployment calculate tokens amount
            # With vllm optimizations and local network, it should be fast enough for loop calculation
            # I'm not that sure

            host_info = ExplainUrl(G.A.MCORE_ADDR)
            return (await dld_json(f"{host_info.scheme}://{host_info.hostname}:{host_info.port}/tokenize", method='post', carriage={"messages": messages}))['count']

        async def tokens_calc(messages):
            if use_api:
                return await _tokens_calc(messages)
            else:
                # It's binary already, we just take bytes / 3 as a approximation of token count
                return len(orjson.dumps(messages)) / 3

        def tokens_eval(count):
            match count:
                case x if x < warn_length:
                    return 0
                case x if warn_length <= x < max_length:
                    return 1
                case x if max_length <= x:
                    return 2
                
        cycle = 0
        last_self_len = len(self)
        archiver = MaicaSession(self.session_num, self.fsc)
        
        if not self.prim_key_id:
            await self.init_db()
        archiver.prim_key_id = self.prim_key_id

        while True:
            cycle += 1
            messages = self.utilize(text_only=True)
            message_len = await tokens_calc(messages)
            messages_stat = tokens_eval(message_len)

            # If the session exceeds max length, we want to crop it until it goes below warn length
            # So we don't have to perform this too often
            if cycle <= 1:
                initial_stat = messages_stat
                stat_threshold = 0 if initial_stat >= 2 else 1
            if messages_stat <= stat_threshold:
                break

            # Crop the oldest complete conversation round, preserving the
            # system prompt and chronological order.
            while len(self) > 1:
                item = self.pop(1)
                archiver.append(item)
                if item.role == "assistant":
                    break

            # Here be the deadlock preventions
            if last_self_len == len(self):
                raise MaicaDbWarning(f"Session cropper hit unexpected dead loop.\nSelf dump: {str(self)}\nArchiver dump: {str(archiver)}")
            last_self_len = len(self)

            if cycle >= 100:
                sync_messenger(f"Session cropper hit extreme fragmentation.\nSelf dump: {str(self)}\nArchiver dump: {str(archiver)}\nBreaking loop and trying to continue", tracker_id=self.fsc.tracker_id, type=MsgType.WARN)
                break

        # Now finished cropping
        return archiver, initial_stat
    
    async def wrapped_save(self) -> Literal[0, 1, 2]:
        """V1 comtatible behavior."""
        archiver, stat = await self.crop_length()
        await self.to_db()
        if len(archiver):
            await archiver.to_partial_archive()
        return stat
