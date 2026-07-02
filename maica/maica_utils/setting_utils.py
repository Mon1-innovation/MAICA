"""Import layer 2"""
import asyncio
from typing import *
from pydantic import (
    BaseModel,
    PrivateAttr,
    Field,
    ConfigDict,
    model_validator,
)
from .gvars import *
from .maica_utils import *

class SettingModel(BaseModel):
    """Just a template."""
    model_config = ConfigDict(
        validate_assignment=True
    )

def create_prop(
        name: str,
        getter_ext: list[Callable]=None,
        getter_kwargs: dict=None,
        setter_ext: list[Callable]=None,
        setter_kwargs: dict=None,
    ):
    """We still have to use the old way somewhere, because pydantic does not offer a better solution."""
    private_name = f"_{name}"
    if not isinstance(getter_kwargs, dict):
        getter_kwargs = {}
    if not isinstance(setter_kwargs, dict):
        setter_kwargs = {}
    
    def getter(self: SettingModel):
        value = getattr(self, private_name, None)
        if getter_ext:
            for func in getter_ext:
                value = func(self, n=name, v=value, **getter_kwargs)
        return value
    
    def setter(self: SettingModel, value):
        if setter_ext:
            for func in setter_ext:
                value = func(self, n=name, v=value, **setter_kwargs)
        setattr(self, private_name, value)
    
    return property(getter, setter)

def read_exist(self, n, v, **kwargs):
    """Value must exist on get."""
    assert v
    return v

def set_locked(self, n, v, **kwargs):
    """Value can only be rewritten from None."""
    prv_n = f"_{n}"
    if getattr(self, prv_n) is not None:
        print(getattr(self, prv_n))
    assert getattr(self, prv_n) is None
    return v

def set_literal(self, n, v, valid: list[any], **kwargs):
    """Value must in valid list on set."""
    assert v in valid
    return v

def set_range(self, n, v, lower: Union[int, float], upper: Union[int, float], soft_limit: bool=False, **kwargs):
    """Value must in range on set."""
    if isinstance(lower, str):
        lower = numeric(getattr(G.A, lower))
    if isinstance(upper, str):
        upper = numeric(getattr(G.A, upper))
    if isinstance(lower, float) or isinstance(upper, float):
        v = float(v)
    else:
        v = int(v)
    if soft_limit:
        new_v = max(lower, min(upper, v))
        if v != new_v:
            sync_messenger(info=f"{n}={v} out of range [{lower}, {upper}], limiting to {new_v}")
            v = new_v
    assert lower <= v <= upper
    return v

def set_instance(self, n, v, types: list[type], **kwargs):
    """Value must be of desired type."""
    for t in types:
        if t:
            if isinstance(v, t):
                break
        elif t is None:
            if v is None:
                break
    else:
        raise AssertionError
    return v

class ConfigurableSettingModel(SettingModel):
    """Do not use on cridentials."""
    @model_validator(mode="before")
    @classmethod
    def none_is_default(cls, data: Any):
        if isinstance(data, dict):
            for field_name, field_info in cls.model_fields.items():
                default = field_info.default
                expected_type = field_info.annotation

                value = data.get(field_name)
                if (
                    field_name in data
                    and value == None
                    and not isinstance(value, expected_type)
                ):
                    data[field_name] = default
        return data

class MaicaSettings(BaseModel):
    """All the per-client settings for MAICA."""

    class Identity(SettingModel):
        """Note that this identity is not verified and not safe to use in most cases. Use verification for those."""

        _user_id: int = None
        _username: str = None
        _nickname: Optional[str] = None
        _email: str = None

        user_id = create_prop('user_id', getter_ext=[read_exist], setter_ext=[set_instance], setter_kwargs={"types": [int]})
        username = create_prop('username', getter_ext=[read_exist], setter_ext=[set_instance], setter_kwargs={"types": [str]})
        nickname = create_prop('nickname', setter_ext=[set_instance], setter_kwargs={"types": [str, None]})
        email = create_prop('email', getter_ext=[read_exist], setter_ext=[set_instance], setter_kwargs={"types": [str]})

    class Verification(Identity):
        """Verified identity, safe to use."""

        user_id = create_prop('user_id', getter_ext=[read_exist], setter_ext=[set_locked, set_instance], setter_kwargs={"types": [int]})
        username = create_prop('username', getter_ext=[read_exist], setter_ext=[set_locked, set_instance], setter_kwargs={"types": [str]})
        # nickname = create_prop('nickname', setter_ext=[set_instance], setter_kwargs={"types": [str, None]})
        email = create_prop('email', getter_ext=[read_exist], setter_ext=[set_locked, set_instance], setter_kwargs={"types": [str]})

    class Basic(ConfigurableSettingModel):
        """Major params that decide MAICA's behavior."""

        stream_output: bool = True
        """Use stream output."""
        enable_mf: bool = True
        """Enable MFocus."""
        enable_mt: bool = True
        """Enable MTrigger."""
        savefile_access: bool = True
        """Enable savefile extraction."""
        target_lang: Literal['zh', 'en', 'auto'] = 'zh'
        """Target language."""
        tz: Optional[str] = None
        """Timezone."""
        session_len_limit: int = Field(
            default=8192,
            ge=512,
            le=28672,
        )
        """Max session length."""

    class Extra(ConfigurableSettingModel):
        """Params that aren't that important, but affect MAICA's behavior."""

        prompt_pname_repl: bool = False
        """Use name from savefile instead of [player] in prompts."""
        mf_llm_concl: bool = False
        """Use agent model's final output instead of instructed guidance."""
        mf_sf_access_impl: Literal[0, 1, 2] = 1
        """Use RAG/Reranker to acquire info from persistent instead of traditional MFocus impl."""
        mf_const_sf_access: Literal[0, 1, 2] = 1
        """Add persistent extraction to MFocus instructed guidance even if not called."""
        mf_const_tools: Literal[0, 1, 2] = 1
        """Add information to MFocus instructed guidance even if no tool used."""
        esearch_llm_concl: bool = True
        """Force agent to resort information acquired from Internet."""
        mf_precheck_mt: bool = True
        """Add MTrigger toollist to MFocus tools for a precheck."""
        mt_concl_memory: Literal[0, 1, 2] = 1
        """Conclude archived / purged sessions into summarizations."""
        nsfw_acceptive: bool = True
        """Alter prompt to ask model to handle toxic topics positively."""
        mf_context_rnds: Literal[0, 1, 2, 3, 4, 5] = 0
        """Add history rounds for MFocus to understand the conversation."""
        mt_context_rnds: Literal[0, 1, 2, 3, 4, 5] = 1
        """Add history rounds for MFocus to understand the conversation."""
        gen_quality_chk: bool = False
        """Check and warn about context quality descalation using MNerve."""
        mf_disable_loop: bool = True
        """Disable MFocus sequential toolcall to save time."""
        mt_disable_loop: bool = True
        """Disable MTrigger sequential toolcall to save time."""
        gen_enforce_lang: bool = True
        """Enforce target language (only applies to English currently)."""

    class Super(ConfigurableSettingModel):
        """Passthrough params to core LLM."""

        max_tokens: int = Field(
            default=1600,
            ge=1,
            le=2048,
        )
        seed: Optional[int] = None
        top_p: float = Field(
            default=0.7,
            ge=0.1,
            le=1.0,
        )
        temperature: float = Field(
            default=0.22,
            ge=0.0,
            le=1.0,
        )
        frequency_penalty: float = Field(
            default=0.44,
            ge=0.0,
            le=1.0,
        )
        presence_penalty: float = Field(
            default=0.34,
            ge=0.0,
            le=1.0,
        )

    class Temp(SettingModel):
        """Should be reset after each round of completion."""

        chat_session: int = Field(
            default=0,
            ge=-1,
            le=9,
        )
        bypass_mf: bool = False
        """Bypass MFocus once."""
        bypass_mt: bool = False
        """Bypass MTrigger once."""
        bypass_stream: bool = False
        """Bypass stream output once."""
        mv_imgs: Optional[list] = None
        """List of MVista images urls."""

    identity: Identity = Field(default_factory=Identity)
    verification: Verification = Field(default_factory=Verification)
    basic: Basic = Field(default_factory=Basic)
    extra: Extra = Field(default_factory=Extra)
    super: Super = Field(default_factory=Super)
    temp: Temp = Field(default_factory=Temp)

    def soft_reset(self):
        """This resets only passable params."""
        self.basic, self.extra, self.super = self.Basic(), self.Extra(), self.Super()

    def update_settings(self, **kwargs):
        """
        Used for handling manual settings.
        """
        accepted_params = set()

        for k, v in kwargs.items():
            for settings_name in ('basic', 'extra', 'super'):
                settings: ConfigurableSettingModel = getattr(self, settings_name)
                field_names = settings.__class__.model_fields.keys()
                if k in field_names:
                    setattr(settings, k, v)
                    accepted_params.add(k)

        return len(accepted_params)

if __name__ == "__main__":
    from maica import init
    init()
    ms = MaicaSettings()
    print(ms.super.top_p)

    # ms.basic.savefile_access = 123
