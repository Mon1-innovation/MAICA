import asyncio
from typing import *
from maica.maica_utils import *
"""Import layer 2"""

PRV_LIST = ['_lock', 'lock']

class MaicaSettings():
    """All the per-client settings for MAICA."""

    class _common_funcs():
        """Just a template. Do not initialize!"""

        def __init__(self):
            self._lock = False

        def reset(self):
            self.__init__()

        def __call__(self):
            return {k.lstrip('_'): getattr(self, k.lstrip('_')) for k, _ in vars(self).items() if not k in PRV_LIST}

        def update(self, **kwargs):
            kwargs = {k: v for k, v in kwargs.items() if not k in PRV_LIST}
            accepted_params = 0
            for k, v in kwargs.items():
                if hasattr(self, f'_{k}'):
                    setattr(self, k, v)
                    accepted_params += 1
            return accepted_params

        @classmethod
        def default(cls, key=None):
            inst = cls()
            defaults = {k.lstrip('_'): v for k, v in vars(inst).items() if not k in PRV_LIST}
            if not key:
                return defaults
            else:
                return defaults[key]

    class _identity(_common_funcs):
        """Note that this identity is not verified and not safe to use in most cases. Use verification for those."""

        def __init__(self):
            super().__init__()
            self._user_id: int = None
            self._username: str = None
            self._nickname: Optional[str] = None
            self._email: str = None

        def _try_lock(self):
            pass

        def force_lock(self):
            self._lock = True

        @property
        @Decos.report_reading_error
        def user_id(self):
            assert self._user_id
            return self._user_id
        @user_id.setter
        @Decos.report_limit_error
        def user_id(self, v: int):
            v = int(v)
            assert v > 0
            self._user_id = v

        @property
        @Decos.report_reading_error
        def username(self):
            assert self._username
            return self._username
        @username.setter
        @Decos.report_limit_error
        def username(self, v: str):
            v = str(v)
            assert v
            self._username = v

        @property
        @Decos.report_reading_error
        def nickname(self):
            return self._nickname
        @nickname.setter
        @Decos.report_limit_error
        def nickname(self, v: Optional[str]):
            self._nickname = v

        @property
        @Decos.report_reading_error
        def email(self):
            assert self._email
            return self._email
        @email.setter
        @Decos.report_limit_error
        def email(self, v: str):
            v = str(v)
            assert v
            self._email = v

    class _verification(_identity):
        """Verified identity, safe to use."""
        def _try_lock(self):
            self._lock = True

    class _basic(_common_funcs):
        """Major params that decide MAICA's behavior."""

        def __init__(self):
            super().__init__()
            self._stream_output: bool = True
            self._deformation: bool = False
            self._enable_mf: bool = True
            self._enable_mt: bool = True
            self._sf_extraction: bool = True
            self._mt_extraction: bool = True
            self._target_lang: str = 'zh'
            self._max_length: int = 8192

        @property
        def stream_output(self):
            """Use stream output."""
            return self._stream_output
        @stream_output.setter
        @Decos.report_limit_warning
        def stream_output(self, v: Optional[bool]):
            if v is None:
                self._stream_output = self.default('stream_output')
            else:
                self._stream_output = bool(v)

        @property
        def deformation(self):
            """Deprecated."""
            return self._deformation
        @deformation.setter
        @Decos.report_limit_warning
        def deformation(self, v: Optional[bool]):
            if v is None:
                self._deformation = self.default('deformation')
            else:
                self._deformation = bool(v)

        @property
        def enable_mf(self):
            """Enable MFocus."""
            return self._enable_mf
        @enable_mf.setter
        @Decos.report_limit_warning
        def enable_mf(self, v: Optional[bool]):
            if v is None:
                self._enable_mf = self.default('enable_mf')
            else:
                self._enable_mf = bool(v)

        @property
        def enable_mt(self):
            """Enable MTrigger."""
            return self._enable_mt
        @enable_mt.setter
        @Decos.report_limit_warning
        def enable_mt(self, v: Optional[bool]):
            if v is None:
                self._enable_mt = self.default('enable_mt')
            else:
                self._enable_mt = bool(v)

        @property
        def sf_extraction(self):
            """Enable savefile extraction."""
            return self._sf_extraction
        @sf_extraction.setter
        @Decos.report_limit_warning
        def sf_extraction(self, v: Optional[bool]):
            if v is None:
                self._sf_extraction = self.default('sf_extraction')
            else:
                self._sf_extraction = bool(v)

        @property
        def mt_extraction(self):
            """Enable trigger extraction."""
            return self._mt_extraction
        @mt_extraction.setter
        @Decos.report_limit_warning
        def mt_extraction(self, v: Optional[bool]):
            if v is None:
                self._mt_extraction = self.default('mt_extraction')
            else:
                self._mt_extraction = bool(v)

        @property
        def target_lang(self):
            """Target language."""
            return self._target_lang
        @target_lang.setter
        @Decos.report_limit_warning
        def target_lang(self, v: Optional[str]):
            if v is None:
                self._target_lang = self.default('target_lang')
            else:
                self._target_lang = 'zh' if v == 'zh' else 'en'

        @property
        def max_length(self):
            """Max session length."""
            return self._max_length
        @max_length.setter
        @Decos.report_limit_warning
        def max_length(self, v: Optional[int]):
            if v is None:
                self._max_length = self.default('max_length')
            else:
                assert 512 <= int(v) <= int(load_env('MAICA_SESSION_MAX_LENGTH'))
                self._max_length = int(v)

    class _extra(_common_funcs):
        """Params that aren't that important, but affect MAICA's behavior."""

        def __init__(self):
            super().__init__()
            self._sfe_aggressive: bool = False
            self._mf_aggressive: bool = False
            self._tnd_aggressive: int = 1
            self._esc_aggressive: bool = True
            self._amt_aggressive: bool = True
            self._nsfw_acceptive: bool = True
            self._pre_additive: int = 0
            self._post_additive: int = 1
            self._tz: Optional[str] = None

        @property
        def sfe_aggressive(self):
            """Use name from savefile instead of [player] in prompts."""
            return self._sfe_aggressive
        @sfe_aggressive.setter
        @Decos.report_limit_warning
        def sfe_aggressive(self, v: Optional[bool]):
            if v is None:
                self._sfe_aggressive = self.default('sfe_aggressive')
            else:
                self._sfe_aggressive = bool(v)

        @property
        def mf_aggressive(self):
            """Use agent model's final output instead of instructed guidance."""
            return self._mf_aggressive
        @mf_aggressive.setter
        @Decos.report_limit_warning
        def mf_aggressive(self, v: Optional[bool]):
            if v is None:
                self._mf_aggressive = self.default('mf_aggressive')
            else:
                self._mf_aggressive = bool(v)

        @property
        def tnd_aggressive(self):
            """Add information to MFocus instructed guidance even if no tool used."""
            return self._tnd_aggressive
        @tnd_aggressive.setter
        @Decos.report_limit_warning
        def tnd_aggressive(self, v: Optional[int]):
            if v is None:
                self._tnd_aggressive = self.default('tnd_aggressive')
            else:
                assert 0 <= int(v) <= 3
                self._tnd_aggressive = int(v)

        @property
        def esc_aggressive(self):
            """Force agent to resort information acquired from Internet."""
            return self._esc_aggressive
        @esc_aggressive.setter
        @Decos.report_limit_warning
        def esc_aggressive(self, v: Optional[bool]):
            if v is None:
                self._esc_aggressive = self.default('esc_aggressive')
            else:
                self._esc_aggressive = bool(v)

        @property
        def amt_aggressive(self):
            """Add MTrigger toollist to MFocus tools for a precheck."""
            return self._amt_aggressive
        @amt_aggressive.setter
        @Decos.report_limit_warning
        def amt_aggressive(self, v: Optional[bool]):
            if v is None:
                self._amt_aggressive = self.default('amt_aggressive')
            else:
                self._amt_aggressive = bool(v)

        @property
        def nsfw_acceptive(self):
            """Alter prompt to ask model to handle toxic topics positively."""
            return self._nsfw_acceptive
        @nsfw_acceptive.setter
        @Decos.report_limit_warning
        def nsfw_acceptive(self, v: Optional[bool]):
            if v is None:
                self._nsfw_acceptive = self.default('nsfw_acceptive')
            else:
                self._nsfw_acceptive = bool(v)

        @property
        def pre_additive(self):
            """Add history rounds for MFocus to understand the conversation."""
            return self._pre_additive
        @pre_additive.setter
        @Decos.report_limit_warning
        def pre_additive(self, v: Optional[int]):
            if v is None:
                self._pre_additive = self.default('pre_additive')
            else:
                assert 0 <= int(v) <= 5
                self._pre_additive = int(v)

        @property
        def post_additive(self):
            """Add history rounds for MFocus to understand the conversation."""
            return self._post_additive
        @post_additive.setter
        @Decos.report_limit_warning
        def post_additive(self, v: Optional[int]):
            if v is None:
                self._post_additive = self.default('post_additive')
            else:
                assert 0 <= int(v) <= 5
                self._post_additive = int(v)

        @property
        def tz(self):
            """Timezone. This is not fully checked, double check before use."""
            return self._tz
        @tz.setter
        @Decos.report_limit_warning
        def tz(self, v: Optional[str]):
            if v is None:
                self._tz = self.default('tz')
            else:
                self._tz = str(v)

    class _super(_common_funcs):
        """Passthrough params to core LLM."""

        def __init__(self):
            super().__init__()
            self._max_tokens: int = 1600
            self._seed: int = None
            self._top_p: float = 0.7
            self._temperature: float = 0.22
            self._frequency_penalty: float = 0.44
            self._presence_penalty: float = 0.34

        @property
        def max_tokens(self):
            return self._max_tokens
        @max_tokens.setter
        @Decos.report_limit_warning
        def max_tokens(self, v: Optional[int]):
            if v is None:
                self._max_tokens = self.default('max_tokens')
            else:
                assert 0 < int(v) <= 2048
                self._max_tokens = int(v)

        @property
        def seed(self):
            return self._seed
        @seed.setter
        @Decos.report_limit_warning
        def seed(self, v: Optional[int]):
            if v is None:
                self._seed = self.default('seed')
            else:
                self._seed = int(v)

        @property
        def top_p(self):
            return self._top_p
        @top_p.setter
        @Decos.report_limit_warning
        def top_p(self, v: Optional[float]):
            if v is None:
                self._top_p = self.default('top_p')
            else:
                assert 0.1 <= float(v) <= 1.0
                self._top_p = float(v)

        @property
        def temperature(self):
            return self._temperature
        @temperature.setter
        @Decos.report_limit_warning
        def temperature(self, v: Optional[float]):
            if v is None:
                self._temperature = self.default('temperature')
            else:
                assert 0.0 <= float(v) <= 1.0
                self._temperature = float(v)

        @property
        def frequency_penalty(self):
            return self._frequency_penalty
        @frequency_penalty.setter
        @Decos.report_limit_warning
        def frequency_penalty(self, v: Optional[float]):
            if v is None:
                self._frequency_penalty = self.default('frequency_penalty')
            else:
                assert 0.0 <= float(v) <= 1.0
                self._frequency_penalty = float(v)

        @property
        def presence_penalty(self):
            return self._presence_penalty
        @presence_penalty.setter
        @Decos.report_limit_warning
        def presence_penalty(self, v: Optional[float]):
            if v is None:
                self._presence_penalty = self.default('presence_penalty')
            else:
                assert 0.0 <= float(v) <= 1.0
                self._presence_penalty = float(v)

    class _temp(_common_funcs):
        """Should be reset after each round of completion."""

        def __init__(self):
            super().__init__()
            self._chat_session = 0
            self._sf_extraction_once = False
            self._mt_extraction_once = False
            self._bypass_mf = False
            self._bypass_mt = False
            self._bypass_stream = False
            self._bypass_sup = False
            self._bypass_gen = False
            self._ic_prep = False
            self._strict_conv = True
            self._ms_cache = False

        @property
        def chat_session(self):
            return self._chat_session
        @chat_session.setter
        @Decos.report_limit_warning
        def chat_session(self, v: Optional[int]):
            if v is None:
                self._chat_session = self.default('chat_session')
            else:
                assert -1 <= int(v) <= 9
                self._chat_session = int(v)

        @property
        def sf_extraction_once(self):
            """Enable sf_extraction once while sf provided with query."""
            return self._sf_extraction_once
        @sf_extraction_once.setter
        @Decos.report_limit_warning
        def sf_extraction_once(self, v: Optional[bool]):
            if v is None:
                self._sf_extraction_once = self.default('sf_extraction_once')
            else:
                self._sf_extraction_once = bool(v)

        @property
        def mt_extraction_once(self):
            """Enable mt_extraction once while mt provided with query"""
            return self._mt_extraction_once
        @mt_extraction_once.setter
        @Decos.report_limit_warning
        def mt_extraction_once(self, v: Optional[bool]):
            if v is None:
                self._mt_extraction_once = self.default('mt_extraction_once')
            else:
                self._mt_extraction_once = bool(v)

        @property
        def bypass_mf(self):
            """Bypass MFocus once."""
            return self._bypass_mf
        @bypass_mf.setter
        @Decos.report_limit_warning
        def bypass_mf(self, v: Optional[bool]):
            if v is None:
                self._bypass_mf = self.default('bypass_mf')
            else:
                self._bypass_mf = bool(v)

        @property
        def bypass_mt(self):
            """Bypass MTrigger once."""
            return self._bypass_mt
        @bypass_mt.setter
        @Decos.report_limit_warning
        def bypass_mt(self, v: Optional[bool]):
            if v is None:
                self._bypass_mt = self.default('bypass_mt')
            else:
                self._bypass_mt = bool(v)

        @property
        def bypass_stream(self):
            """Bypass stream output once."""
            return self._bypass_stream
        @bypass_stream.setter
        @Decos.report_limit_warning
        def bypass_stream(self, v: Optional[bool]):
            if v is None:
                self._bypass_stream = self.default('bypass_stream')
            else:
                self._bypass_stream = bool(v)

        @property
        def bypass_sup(self):
            """Bypass super params once."""
            return self._bypass_sup
        @bypass_sup.setter
        @Decos.report_limit_warning
        def bypass_sup(self, v: Optional[bool]):
            if v is None:
                self._bypass_sup = self.default('bypass_sup')
            else:
                self._bypass_sup = bool(v)

        @property
        def bypass_gen(self):
            """Bypass generation once."""
            return self._bypass_gen
        @bypass_gen.setter
        @Decos.report_limit_warning
        def bypass_gen(self, v: Optional[bool]):
            if v is None:
                self._bypass_gen = self.default('bypass_gen')
            else:
                self._bypass_gen = bool(v)

        @property
        def ic_prep(self):
            """Adjust generation params once, basically for MPostal."""
            return self._ic_prep
        @ic_prep.setter
        @Decos.report_limit_warning
        def ic_prep(self, v: Optional[bool]):
            if v is None:
                self._ic_prep = self.default('ic_prep')
            else:
                self._ic_prep = bool(v)

        @property
        def strict_conv(self):
            """Strict conversation prompt."""
            return self._strict_conv
        @strict_conv.setter
        @Decos.report_limit_warning
        def strict_conv(self, v: Optional[bool]):
            if v is None:
                self._strict_conv = self.default('strict_conv')
            else:
                self._strict_conv = bool(v)

        @property
        def ms_cache(self):
            """Cache the MSpire response."""
            return self._ms_cache
        @ms_cache.setter
        @Decos.report_limit_warning
        def ms_cache(self, v: Optional[bool]):
            if v is None:
                self._ms_cache = self.default('ms_cache')
            else:
                self._ms_cache = bool(v)

    def __init__(self):
        self.identity, self.verification, self.basic, self.extra, self.super, self.temp = self._identity(), self._verification(), self._basic(), self._extra(), self._super(), self._temp()

    def __call__(self):
        d = self.identity()
        for k, v in self.verification().items():
            if v is not None:
                d[k] = v
        d.update(self.basic())
        d.update(self.extra())
        d.update(self.super())
        d.update(self.temp())
        return d

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

