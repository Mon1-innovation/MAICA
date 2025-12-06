"""Import layer 2"""
import asyncio
from typing import *
from typing_extensions import deprecated
from dataclasses import dataclass
from .gvars import *
from .maica_utils import *

@dataclass
class _CommonFuncs():
    """Just a template. Do not initialize!"""

    def reset(self):
        self.__init__()

    def _dict(self):
        return {k.removeprefix('_'): getattr(self, k.removeprefix('_')) for k in vars(self).keys()}
    
    def __iter__(self):
        return iter(self._dict().items())
    
    @deprecated("Use dict(instance) instead")
    def __call__(self, *args, **kwargs):
        return self._dict()

    def update(self, **kwargs):
        accepted_params = 0
        for k, v in kwargs.items():
            if hasattr(self, f'_{k}'):
                setattr(self, k, v)
                accepted_params += 1
        return accepted_params

    @classmethod
    def default(cls, key=None):
        inst = cls()
        defaults = dict(inst)
        if not key:
            return defaults
        else:
            return defaults[key]

def create_prop(
        name: str,
        getter_ext: list[Callable]=None,
        getter_kwargs: dict=None,
        setter_ext: list[Callable]=None,
        setter_kwargs: dict=None,
    ):
    """Creates a verificated property."""
    private_name = f"_{name}"
    if not isinstance(getter_kwargs, dict):
        getter_kwargs = {}
    if not isinstance(setter_kwargs, dict):
        setter_kwargs = {}
    
    def getter(self: _CommonFuncs):
        value = getattr(self, private_name, None)
        if getter_ext:
            for func in getter_ext:
                value = func(self, n=name, v=value, **getter_kwargs)
        return value
    
    def setter(self: _CommonFuncs, value):
        if setter_ext:
            for func in setter_ext:
                value = func(self, n=name, v=value, **setter_kwargs)
        setattr(self, private_name, value)
    
    return property(getter, setter)

@Decos.report_reading_error
def read_exist(self, n, v, **kwargs):
    """Value must exist on get."""
    assert v
    return v

@Decos.report_limit_error
def set_locked(self, n, v, **kwargs):
    """Value can only be rewritten from None."""
    prv_n = f"_{n}"
    if getattr(self, prv_n) is not None:
        print(getattr(self, prv_n))
    assert getattr(self, prv_n) is None
    return v

@Decos.report_limit_warning
def set_literal(self, n, v, valid: list[any], **kwargs):
    """Value must in valid list on set."""
    assert v in valid
    return v

@Decos.report_limit_warning
def set_range(self, n, v, lower: Union[int, float], upper: Union[int, float], **kwargs):
    """Value must in range on set."""
    if isinstance(lower, str):
        lower = numeric(getattr(G.A, lower))
    if isinstance(upper, str):
        upper = numeric(getattr(G.A, upper))
    if isinstance(lower, float) or isinstance(upper, float):
        v = float(v)
    else:
        v = int(v)
    assert lower <= v <= upper
    return v

@Decos.report_limit_warning
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

def set_spec_default(self, n, v, defaults: tuple=(None, ), **kwargs):
    """Value to default if specificated value passed in."""
    if v in defaults:
        v = self.default(n)
    return v

class MaicaSettings():
    """All the per-client settings for MAICA."""

    @dataclass
    class _Identity(_CommonFuncs):
        """Note that this identity is not verified and not safe to use in most cases. Use verification for those."""

        _user_id: int = None
        _username: str = None
        _nickname: Optional[str] = None
        _email: str = None

        user_id = create_prop('user_id', getter_ext=[read_exist], setter_ext=[set_instance], setter_kwargs={"types": [int]})
        username = create_prop('username', getter_ext=[read_exist], setter_ext=[set_instance], setter_kwargs={"types": [str]})
        nickname = create_prop('nickname', setter_ext=[set_instance], setter_kwargs={"types": [str, None]})
        email = create_prop('email', getter_ext=[read_exist], setter_ext=[set_instance], setter_kwargs={"types": [str]})

    @dataclass
    class _Verification(_Identity):
        """Verified identity, safe to use."""

        user_id = create_prop('user_id', getter_ext=[read_exist], setter_ext=[set_locked, set_instance], setter_kwargs={"types": [int]})
        username = create_prop('username', getter_ext=[read_exist], setter_ext=[set_locked, set_instance], setter_kwargs={"types": [str]})
        nickname = create_prop('nickname', setter_ext=[set_locked, set_instance], setter_kwargs={"types": [str, None]})
        email = create_prop('email', getter_ext=[read_exist], setter_ext=[set_locked, set_instance], setter_kwargs={"types": [str]})

    @dataclass
    class _Basic(_CommonFuncs):
        """Major params that decide MAICA's behavior."""

        _stream_output: bool = True
        _deformation: bool = False
        _enable_mf: bool = True
        _enable_mt: bool = True
        _sf_extraction: bool = True
        _mt_extraction: bool = True
        _target_lang: str = 'zh'
        _max_length: int = 8192

        stream_output = create_prop('stream_output', setter_ext=[set_spec_default, set_instance], setter_kwargs={"types": [bool]})
        """Use stream output."""
        deformation = create_prop('deformation', setter_ext=[set_spec_default, set_instance], setter_kwargs={"types": [bool]})
        """Deprecated."""
        enable_mf = create_prop('enable_mf', setter_ext=[set_spec_default, set_instance], setter_kwargs={"types": [bool]})
        """Enable MFocus."""
        enable_mt = create_prop('enable_mt', setter_ext=[set_spec_default, set_instance], setter_kwargs={"types": [bool]})
        """Enable MTrigger."""
        sf_extraction = create_prop('sf_extraction', setter_ext=[set_spec_default, set_instance], setter_kwargs={"types": [bool]})
        """Enable savefile extraction."""
        mt_extraction = create_prop('mt_extraction', setter_ext=[set_spec_default, set_instance], setter_kwargs={"types": [bool]})
        """Enable trigger extraction."""
        target_lang = create_prop('target_lang', setter_ext=[set_spec_default, set_literal], setter_kwargs={"valid": ['zh', 'en']})
        """Target language."""
        max_length = create_prop('max_length', setter_ext=[set_spec_default, set_range], setter_kwargs={"lower": 512, "upper": 'SESSION_MAX_LENGTH'})
        """Max session length."""

    @dataclass
    class _Extra(_CommonFuncs):
        """Params that aren't that important, but affect MAICA's behavior."""

        _sfe_aggressive: bool = False
        _mf_aggressive: bool = False
        _tnd_aggressive: int = 1
        _esc_aggressive: bool = True
        _amt_aggressive: bool = True
        _nsfw_acceptive: bool = True
        _pre_additive: int = 0
        _post_additive: int = 1
        _tz: Optional[str] = None
        _dscl_pvn: bool = False
        _pre_astp: bool = True
        _post_astp: bool = False
        _enforce_lang: bool = True

        sfe_aggressive = create_prop('sfe_aggressive', setter_ext=[set_spec_default, set_instance], setter_kwargs={"types": [bool]})
        """Use name from savefile instead of [player] in prompts."""
        mf_aggressive = create_prop('mf_aggressive', setter_ext=[set_spec_default, set_instance], setter_kwargs={"types": [bool]})
        """Use agent model's final output instead of instructed guidance."""
        tnd_aggressive = create_prop('tnd_aggressive', setter_ext=[set_spec_default, set_literal], setter_kwargs={"valid": [0, 1, 2, 3]})
        """Add information to MFocus instructed guidance even if no tool used."""
        esc_aggressive = create_prop('esc_aggressive', setter_ext=[set_spec_default, set_instance], setter_kwargs={"types": [bool]})
        """Force agent to resort information acquired from Internet."""
        amt_aggressive = create_prop('amt_aggressive', setter_ext=[set_spec_default, set_instance], setter_kwargs={"types": [bool]})
        """Add MTrigger toollist to MFocus tools for a precheck."""
        nsfw_acceptive = create_prop('nsfw_acceptive', setter_ext=[set_spec_default, set_instance], setter_kwargs={"types": [bool]})
        """Alter prompt to ask model to handle toxic topics positively."""
        pre_additive = create_prop('pre_additive', setter_ext=[set_spec_default, set_literal], setter_kwargs={"valid": [0, 1, 2, 3, 4, 5]})
        """Add history rounds for MFocus to understand the conversation."""
        post_additive = create_prop('post_additive', setter_ext=[set_spec_default, set_literal], setter_kwargs={"valid": [0, 1, 2, 3, 4, 5]})
        """Add history rounds for MFocus to understand the conversation."""
        tz = create_prop('tz', setter_ext=[set_instance], setter_kwargs={"types": [str, None]})
        """Timezone. This is not fully checked, double check before use."""
        dscl_pvn = create_prop('dscl_pvn', setter_ext=[set_spec_default, set_instance], setter_kwargs={"types": [bool]})
        """Check and warn about context quality descalation using MNerve."""
        pre_astp = create_prop('pre_astp', setter_ext=[set_spec_default, set_instance], setter_kwargs={"types": [bool]})
        """Disable MFocus sequential toolcall to save time."""
        post_astp = create_prop('post_astp', setter_ext=[set_spec_default, set_instance], setter_kwargs={"types": [bool]})
        """Disable MTrigger sequential toolcall to save time."""
        enforce_lang = create_prop('enforce_lang', setter_ext=[set_spec_default, set_instance], setter_kwargs={"types": [bool]})
        """Enforce target language (only applies to English currently)."""


    @dataclass
    class _Super(_CommonFuncs):
        """Passthrough params to core LLM."""

        _max_tokens: int = 1600
        _seed: Optional[int] = None
        _top_p: float = 0.7
        _temperature: float = 0.22
        _frequency_penalty: float = 0.44
        _presence_penalty: float = 0.34

        max_tokens = create_prop('max_tokens', setter_ext=[set_spec_default, set_range], setter_kwargs={"lower": 1, "upper": 2048})
        seed = create_prop('seed', setter_ext=[set_instance], setter_kwargs={"types": [int, None]})
        top_p = create_prop('top_p', setter_ext=[set_spec_default, set_range], setter_kwargs={"lower": 0.1, "upper": 1.0})
        temperature = create_prop('temperature', setter_ext=[set_spec_default, set_range], setter_kwargs={"lower": 0.0, "upper": 1.0})
        frequency_penalty = create_prop('frequency_penalty', setter_ext=[set_spec_default, set_range], setter_kwargs={"lower": 0.0, "upper": 1.0})
        presence_penalty = create_prop('presence_penalty', setter_ext=[set_spec_default, set_range], setter_kwargs={"lower": 0.0, "upper": 1.0})

    @dataclass
    class _Temp(_CommonFuncs):
        """Should be reset after each round of completion."""

        _chat_session: int=0
        _sf_extraction_once: bool=False
        _mt_extraction_once: bool=False
        _bypass_mf: bool=False
        _bypass_mt: bool=False
        _bypass_stream: bool=False
        _bypass_sup: bool=False
        _bypass_gen: bool=False
        _ic_prep: bool=False
        _strict_conv: bool=True
        _ms_cache: bool=False
        _mv_imgs: Optional[list]=None

        chat_session = create_prop('chat_session', setter_ext=[set_spec_default, set_instance, set_range], setter_kwargs={"types": [int], "lower": -1, "upper": 9})
        sf_extraction_once = create_prop('sf_extraction_once', setter_ext=[set_spec_default, set_instance], setter_kwargs={"types": [bool]})
        """Enable sf_extraction once while sf provided with query."""
        mt_extraction_once = create_prop('mt_extraction_once', setter_ext=[set_spec_default, set_instance], setter_kwargs={"types": [bool]})
        """Enable mt_extraction once while mt provided with query"""
        bypass_mf = create_prop('bypass_mf', setter_ext=[set_spec_default, set_instance], setter_kwargs={"types": [bool]})
        """Bypass MFocus once."""
        bypass_mt = create_prop('bypass_mt', setter_ext=[set_spec_default, set_instance], setter_kwargs={"types": [bool]})
        """Bypass MTrigger once."""
        bypass_stream = create_prop('bypass_stream', setter_ext=[set_spec_default, set_instance], setter_kwargs={"types": [bool]})
        """Bypass stream output once."""
        bypass_sup = create_prop('bypass_sup', setter_ext=[set_spec_default, set_instance], setter_kwargs={"types": [bool]})
        """Bypass super params once."""
        bypass_gen = create_prop('bypass_gen', setter_ext=[set_spec_default, set_instance], setter_kwargs={"types": [bool]})
        """Bypass generation once."""
        ic_prep = create_prop('ic_prep', setter_ext=[set_spec_default, set_instance], setter_kwargs={"types": [bool]})
        """Adjust generation params once, basically for MPostal."""
        strict_conv = create_prop('strict_conv', setter_ext=[set_spec_default, set_instance], setter_kwargs={"types": [bool]})
        """Strict conversation prompt."""
        ms_cache = create_prop('ms_cache', setter_ext=[set_spec_default, set_instance], setter_kwargs={"types": [bool]})
        """Cache the MSpire response."""
        mv_imgs = create_prop('mv_imgs', setter_ext=[set_instance], setter_kwargs={"types": [list, None]})

    def __init__(self):
        self.identity, self.verification, self.basic, self.extra, self.super, self.temp = self._Identity(), self._Verification(), self._Basic(), self._Extra(), self._Super(), self._Temp()

    def _dict(self):
        d = dict(self.identity)
        for k, v in dict(self.verification).items():
            if v is not None:
                d[k] = v
        d.update(dict(self.basic))
        d.update(dict(self.extra))
        d.update(dict(self.super))
        d.update(dict(self.temp))
        return d
    
    def __iter__(self):
        return iter(self._dict().items())

    def reset(self):
        self.__init__()

    def update(self, secure=None, **kwargs):
        """Used for handling manual settings."""
        if secure is False:
            accepted_params = self.identity.update(**kwargs)
        elif secure is True:
            accepted_params = self.verification.update(**kwargs)
        else:
            accepted_params = self.basic.update(**kwargs) + self.extra.update(**kwargs) + self.super.update(**kwargs)
            # We do not accept temps to be manually set
        return accepted_params

if __name__ == "__main__":
    ms = MaicaSettings()
    # ms.temp.chat_session = 1
    print(dict(ms.super))
    print(dict(ms.basic))
    # ms2 = MaicaSettings()
    print(dict(ms.temp))