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

_Bt = BilingualText

class SettingsModel(BaseModel):
    """Just a template."""
    model_config = ConfigDict(
        validate_assignment=True
    )

class IdentitySettingsModel(SettingsModel, PydHardResetMixin): ...

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
    
    def getter(self: SettingsModel):
        value = getattr(self, private_name, None)
        if getter_ext:
            for func in getter_ext:
                value = func(self, n=name, v=value, **getter_kwargs)
        return value
    
    def setter(self: SettingsModel, value):
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

class ConfigurableSettingsModel(SettingsModel, PydUpdateMixin, PydSoftResetMixin):
    """Do not use on cridentials."""
    @model_validator(mode="before")
    @classmethod
    def none_is_default(cls, data: Any):
        if isinstance(data, dict):
            for field_name, field_info in cls.model_fields.items():
                expected_type = field_info.annotation

                value = data.get(field_name)
                if (
                    field_name in data
                    and value == None
                    and not isinstance(value, expected_type)
                ):
                    data[field_name] = field_info.get_default(call_default_factory=True)
        return data

class MaicaSettings(BaseModel):
    """All the per-client settings for MAICA."""

    # class Identity(IdentitySettingsModel):
    #     """Note that this identity is not verified and not safe to use in most cases. Use verification for those."""

    #     _user_id: int = None
    #     _username: str = None
    #     _nickname: Optional[str] = None
    #     _email: str = None

    #     user_id = create_prop('user_id', getter_ext=[read_exist], setter_ext=[set_instance], setter_kwargs={"types": [int]})
    #     username = create_prop('username', getter_ext=[read_exist], setter_ext=[set_instance], setter_kwargs={"types": [str]})
    #     nickname = create_prop('nickname', setter_ext=[set_instance], setter_kwargs={"types": [str, None]})
    #     email = create_prop('email', getter_ext=[read_exist], setter_ext=[set_instance], setter_kwargs={"types": [str]})

    class Verification(IdentitySettingsModel):
        """Verified identity, safe to use."""

        _user_id: int = None
        _username: str = None
        _nickname: Optional[str] = None
        _email: str = None

        user_id: int = create_prop('user_id', getter_ext=[read_exist], setter_ext=[set_locked, set_instance], setter_kwargs={"types": [int]})
        username: str = create_prop('username', getter_ext=[read_exist], setter_ext=[set_locked, set_instance], setter_kwargs={"types": [str]})
        nickname: Optional[str] = create_prop('nickname', setter_ext=[set_instance], setter_kwargs={"types": [str, None]})
        email: str = create_prop('email', getter_ext=[read_exist], setter_ext=[set_locked, set_instance], setter_kwargs={"types": [str]})

    class Basic(ConfigurableSettingsModel):
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

    class Extra(ConfigurableSettingsModel):
        """Params that aren't that important, but affect MAICA's behavior."""

        prompt_pname_repl: bool = False
        """Use name from savefile instead of [player] in prompts."""
        prompt_allow_nickname: bool = False
        """Allow model to generate [player_nickname]."""
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

    class Super(ConfigurableSettingsModel):
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

    class Temp(ConfigurableSettingsModel):
        """
        Should be reset after each round of completion.
        Caution: This does not verify many things itself, especially when it comes to session -1 or things.
        Related verifications should be in ws_config.
        """

        class MSpire(ConfigurableSettingsModel):

            class MsFromCacheResult(BaseModel):
                hash: Optional[str] = None
                result: Optional[str] = None

            type: Literal[
                "precise_page",
                "fuzzy_page",
                "in_precise_category",
                "in_fuzzy_category",
                "in_fuzzy_all",
            ] = "in_fuzzy_all"
            sample: int = Field(
                default=250,
                ge=2,
                le=250,
            )
            ctg_weight: int = Field(
                default=10,
                ge=1,
                le=100,
            )
            title: Union[str, list] = Field(
                default_factory=lambda: [
                    _Bt('自然', 'Nature'),
                    _Bt('自然科学', 'Natural_sciences'),
                    _Bt('社会', 'Society'),
                    _Bt('人文學科', 'Humanities'),
                    _Bt('世界', 'World'),
                    _Bt('生活', 'Health'),
                    _Bt('艺术', 'The_arts'),
                    _Bt('文化', 'Culture'),
                ]
            )
            use_cache: bool = False
            _mfc_m: Optional[MsFromCacheResult] = None

            @model_validator(mode="after")
            def enhanced_defaults(self):
                if isinstance(self.title, str):
                    self.title = [self.title]

                return self

        class MPostal(ConfigurableSettingsModel):
            header: Optional[str] = None
            content: Optional[str] = None

        class MVista(ConfigurableSettingsModel):
            mv_imgs: Optional[list] = Field(
                default=None,
                max_length=3,
            )
            """List of MVista images urls."""

        class Common(ConfigurableSettingsModel):
            """These are used by several m-things."""
            bypass_mf: bool = False
            """Bypass MFocus once."""
            bypass_mt: bool = False
            """Bypass MTrigger once."""
            bypass_stream: bool = False
            """Bypass stream output once."""
            twk_super: bool = False
            """Tweak super params (for written language)."""
            strict_conv: bool = True
            """Restrict conversation schema."""

        chat_session: int = Field(
            default=0,
            ge=-1,
            le=9,
        )
        """This is standalone because it's important."""
        activated: Literal["query", "mspire", "mpostal"] = "query"

        mspire: MSpire = Field(default_factory=MSpire)
        mpostal: MPostal = Field(default_factory=MPostal)
        mvista: MVista = Field(default_factory=MVista)
        common: Common = Field(default_factory=Common)

    # identity: Identity = Field(
    #     default_factory=Identity,
    #     exclude=True,
    # )
    verification: Verification = Field(
        default_factory=Verification,
        exclude=True,
    )
    basic: Basic = Field(default_factory=Basic)
    extra: Extra = Field(default_factory=Extra)
    super: Super = Field(default_factory=Super)
    temp: Temp = Field(
        default_factory=Temp,
        exclude=True,
    )

    @property
    def use_mf_now(self):
        return (
            self.basic.enable_mf
            and self.prompt_writable
            and not self.temp.common.bypass_mf
        )

    @property
    def use_mt_now(self):
        return (
            self.basic.enable_mt
            and not self.temp.common.bypass_mt
        )
    
    @property
    def use_stream_now(self):
        return (
            self.basic.stream_output
            and not self.temp.common.bypass_stream
        )

    @property
    def prompt_writable(self):
        return (
            self.temp.chat_session >= 0
        )
    
    @property
    def super_writable(self):
        return (
            not self.temp.mspire.use_cache
        )
    
    @property
    def skip_generation(self):
        if (
            self.temp.mspire._mfc_m
            and self.temp.mspire._mfc_m.result
        ):
            return self.temp.mspire._mfc_m.result
        return False

    def reset(self):
        """This resets temp together with soft_reset."""
        self.temp = self.Temp()
        self.soft_reset()

    def soft_reset(self):
        """This resets only passable params."""
        self.basic, self.extra, self.super = self.Basic(), self.Extra(), self.Super()

    def update_settings(self, **kwargs):
        """
        Used for handling manual settings. Note that this is different with update().
        """
        accepted_params = set()

        for k, v in kwargs.items():
            for settings_name in ('basic', 'extra', 'super'):
                settings: ConfigurableSettingsModel = getattr(self, settings_name)
                model_fields = settings.__class__.model_fields
                if k in model_fields:
                    setattr(settings, k, v)
                    accepted_params.add(k)

        return len(accepted_params)

if __name__ == "__main__":
    from maica import init
    init()
    ms = MaicaSettings()
    print(ms.super.top_p)

    some_data = {
        "bypass_stream": True,
        "common": {
            "strict_conv": True,
        }
    }
    
    ms.temp.update(some_data)
    print(ms.temp)

    # ms.basic.savefile_access = 123

