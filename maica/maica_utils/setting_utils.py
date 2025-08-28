import asyncio
from .maica_utils import *
"""Import layer 2"""

class MaicaSettings():
    """All the per-client settings for MAICA."""
    class _common_funcs():
        """Just a template. Do not initialize!"""
        def __init__(self):
            self.default = self._default()
            for k, v in self.default().items():
                setattr(self, k, v)
            self._lock = False
        def reset(self):
            self.__init__()
        def _try_lock(self):
            pass
        def force_lock(self):
            self._lock = True

    class _identity(_common_funcs):
        """Note that this identity is not verified and not safe to use in most cases. Use verification for those."""
        class _default():
            user_id = None
            username = None
            nickname = None
            email = None
            def __call__(self):
                return {
                    'user_id': self.user_id,
                    'username': self.username,
                    'nickname': self.nickname,
                    'email': self.email,
                }
        def __call__(self):
            return {
                'user_id': self.user_id,
                'username': self.username,
                'nickname': self.nickname,
                'email': self.email,
            }
        def update(self, rsc=None, **kwargs):
            if not rsc:
                rsc = FscPlain.RealtimeSocketsContainer()
            accepted_params = 0
            try:
                if self._lock:
                    raise Exception('This identity is locked')
                if 'user_id' in kwargs:
                    self.user_id = int(kwargs['user_id'])
                    accepted_params += 1
                if 'username' in kwargs:
                    self.username = str(kwargs['username'])
                    accepted_params += 1
                if 'nickname' in kwargs:
                    self.nickname = str(kwargs['nickname'])
                    accepted_params += 1
                if 'email' in kwargs:
                    self.email = str(kwargs['email'])
                    accepted_params += 1
                self._try_lock()
                return accepted_params
            except Exception as e:
                error = MaicaInputWarning(e, '422')
                asyncio.run(messenger(rsc.websocket, status='maica_settings_param_rejected', traceray_id=rsc.traceray_id, error=error))

    class _verification(_identity):
        """Verified identity, safe to use."""
        def _try_lock(self):
            self._lock = True

    class _basic(_common_funcs):
        """Major params that decide MAICA's behavior."""
        class _default():
            stream_output = True
            deformation = False
            enable_mf = True
            enable_mt = True
            sf_extraction = True
            mt_extraction = True
            target_lang = 'zh'
            max_length = 8192
            def __call__(self):
                return {
                    'stream_output': self.stream_output,
                    'deformation': self.deformation,
                    'enable_mf': self.enable_mf,
                    'enable_mt': self.enable_mt,
                    'sf_extraction': self.sf_extraction,
                    'mt_extraction': self.mt_extraction,
                    'target_lang': self.target_lang,
                    'max_length': self.max_length,
                }
        def __call__(self):
            return {
                'stream_output': self.stream_output,
                'deformation': self.deformation,
                'enable_mf': self.enable_mf,
                'enable_mt': self.enable_mt,
                'sf_extraction': self.sf_extraction,
                'mt_extraction': self.mt_extraction,
                'target_lang': self.target_lang,
                'max_length': self.max_length,
            }
        def update(self, rsc=None, **kwargs):
            if not rsc:
                rsc = FscPlain.RealtimeSocketsContainer()
            accepted_params = 0
            try:
                if 'enable_mf' in kwargs:
                    self.enable_mf = bool(default(kwargs['enable_mf'], self.default.enable_mf))
                    accepted_params += 1
                if 'enable_mt' in kwargs:
                    self.enable_mt = bool(default(kwargs['enable_mt'], self.default.enable_mt))
                    accepted_params += 1
                if 'sf_extraction' in kwargs:
                    self.sf_extraction = bool(default(kwargs['sf_extraction'], self.default.sf_extraction))
                    accepted_params += 1
                if 'mt_extraction' in kwargs:
                    self.mt_extraction = bool(default(kwargs['mt_extraction'], self.default.mt_extraction))
                    accepted_params += 1
                if 'stream_output' in kwargs:
                    self.stream_output = bool(default(kwargs['stream_output'], self.default.stream_output))
                    accepted_params += 1
                if 'deformation' in kwargs:
                    self.deformation = bool(default(kwargs['deformation'], self.default.deformation))
                    accepted_params += 1
                if 'target_lang' in kwargs:
                    self.target_lang = 'en' if kwargs['target_lang'] == 'en' else 'zh'
                    accepted_params += 1
                if 'max_length' in kwargs:
                    if kwargs['max_length'] is None:
                        self.max_length = self.default.max_length
                        accepted_params += 1
                    elif 512 <= int(kwargs['max_length']) <= 28672:
                        self.max_length = int(kwargs['max_length'])
                        accepted_params += 1
                return accepted_params
            except Exception as e:
                error = MaicaInputWarning(e, '422')
                asyncio.run(messenger(rsc.websocket, status='maica_settings_param_rejected', traceray_id=rsc.traceray_id, error=error))

    class _extra(_common_funcs):
        """Params that aren't that important, but affect MAICA's behavior."""
        class _default():
            sfe_aggressive = False
            """Means using name from savefile instead of [player] in prompts"""
            mf_aggressive = False
            """Means using agent model's final output instead of instructed guidance"""
            tnd_aggressive = 1
            """Means adding information to MFocus instructed guidance even if no tool used"""
            esc_aggressive = True
            """Means forcing agent to resort information acquired from Internet"""
            amt_aggressive = True
            """Means adding MTrigger toollist to MFocus tools for a precheck"""
            nsfw_acceptive = True
            pre_additive = 0
            """Means adding history rounds for MFocus to understand the conversation"""
            post_additive = 1
            """Means adding history rounds for MFocus to understand the conversation"""
            tz = None
            def __call__(self):
                return {
                    'sfe_aggressive': self.sfe_aggressive,
                    'mf_aggressive': self.mf_aggressive,
                    'tnd_aggressive': self.tnd_aggressive,
                    'esc_aggressive': self.esc_aggressive,
                    'amt_aggressive': self.amt_aggressive,
                    'nsfw_acceptive': self.nsfw_acceptive,
                    'pre_additive': self.pre_additive,
                    'post_additive': self.post_additive,
                    'tz': self.tz,
                }
        def __call__(self):
            return {
                'sfe_aggressive': self.sfe_aggressive,
                'mf_aggressive': self.mf_aggressive,
                'tnd_aggressive': self.tnd_aggressive,
                'esc_aggressive': self.esc_aggressive,
                'amt_aggressive': self.amt_aggressive,
                'nsfw_acceptive': self.nsfw_acceptive,
                'pre_additive': self.pre_additive,
                'post_additive': self.post_additive,
                'tz': self.tz,
            }
        def update(self, rsc=None, **kwargs):
            if not rsc:
                rsc = FscPlain.RealtimeSocketsContainer()
            accepted_params = 0
            try:
                if 'sfe_aggressive' in kwargs:
                    self.sfe_aggressive = bool(default(kwargs['sfe_aggressive'], self.default.sfe_aggressive))
                    accepted_params += 1
                if 'mf_aggressive' in kwargs:
                    self.mf_aggressive = bool(default(kwargs['mf_aggressive'], self.default.mf_aggressive))
                    accepted_params += 1
                if 'tnd_aggressive' in kwargs:
                    self.tnd_aggressive = int(default(kwargs['tnd_aggressive'], self.default.tnd_aggressive))
                    accepted_params += 1
                if 'esc_aggressive' in kwargs:
                    self.esc_aggressive = bool(default(kwargs['esc_aggressive'], self.default.esc_aggressive))
                    accepted_params += 1
                if 'amt_aggressive' in kwargs:
                    self.amt_aggressive = bool(default(kwargs['amt_aggressive'], self.default.amt_aggressive))
                    accepted_params += 1
                if 'nsfw_acceptive' in kwargs:
                    self.nsfw_acceptive = bool(default(kwargs['nsfw_acceptive'], self.default.nsfw_acceptive))
                    accepted_params += 1
                if 'pre_additive' in kwargs:
                    if kwargs['pre_additive'] is None:
                        self.pre_additive = self.default.pre_additive
                        accepted_params += 1
                    if 0 <= int(kwargs['pre_additive']) <= 5:
                        self.pre_additive = int(kwargs['pre_additive'])
                        accepted_params += 1
                if 'post_additive' in kwargs:
                    if kwargs['post_additive'] is None:
                        self.post_additive = self.default.post_additive
                        accepted_params += 1
                    elif 0 <= int(kwargs['post_additive']) <= 5:
                        self.post_additive = int(kwargs['post_additive'])
                        accepted_params += 1
                if 'tz' in kwargs and isinstance(kwargs['tz'], Optional[str]):
                    self.tz = default(kwargs['tz'], self.default.tz)
                    accepted_params += 1
                return accepted_params
            except Exception as e:
                error = MaicaInputWarning(e, '422')
                asyncio.run(messenger(rsc.websocket, status='maica_settings_param_rejected', traceray_id=rsc.traceray_id, error=error))

    class _super(_common_funcs):
        """Passthrough params to core LLM."""
        class _default():
            max_tokens = 1600
            seed = None
            top_p = 0.7
            temperature = 0.22
            frequency_penalty = 0.44
            presence_penalty = 0.34
            def __call__(self):
                return {
                    'max_tokens': self.max_tokens,
                    'seed': self.seed,
                    'top_p': self.top_p,
                    'temperature': self.temperature,
                    'frequency_penalty': self.frequency_penalty,
                    'presence_penalty': self.presence_penalty,
                }
        def __call__(self):
            return {
                'max_tokens': self.max_tokens,
                'seed': self.seed,
                'top_p': self.top_p,
                'temperature': self.temperature,
                'frequency_penalty': self.frequency_penalty,
                'presence_penalty': self.presence_penalty,
            }
        def update(self, rsc=None, **kwargs):
            if not rsc:
                rsc = FscPlain.RealtimeSocketsContainer()
            accepted_params = 0
            try:
                if 'max_tokens' in kwargs:
                    if isinstance(kwargs['max_tokens'], Optional[int]):
                        if kwargs['max_tokens'] is None:
                            self.max_tokens = self.default.max_tokens
                            accepted_params += 1
                        elif int(kwargs['max_tokens']) == -1 or 0 < int(kwargs['max_tokens']) <= 2048:
                            self.max_tokens = int(default(kwargs['max_tokens'], self.default.max_tokens, [None, -1]))
                            accepted_params += 1
                if 'seed' in kwargs:
                    if isinstance(kwargs['seed'], Optional[int]):
                        if kwargs['seed'] is None:
                            self.seed = self.default.seed
                            accepted_params += 1
                        elif int(kwargs['seed']) == -1 or 0 < int(kwargs['seed']) <= 99999:
                            self.seed = int(default(kwargs['seed'], self.default.seed, [None, -1]))
                            accepted_params += 1
                if 'top_p' in kwargs:
                    if isinstance(kwargs['top_p'], Union[int, float, None]):
                        if kwargs['top_p'] is None:
                            self.top_p = self.default.top_p
                            accepted_params += 1
                        elif int(kwargs['top_p']) == -1 or 0.1 < float(kwargs['top_p']) <= 1.0:
                            self.top_p = float(default(kwargs['top_p'], self.default.top_p, [None, -1]))
                            accepted_params += 1
                if 'temperature' in kwargs:
                    if isinstance(kwargs['temperature'], Union[int, float, None]):
                        if kwargs['temperature'] is None:
                            self.temperature = self.default.temperature
                            accepted_params += 1
                        elif int(kwargs['temperature']) == -1 or 0.0 < float(kwargs['temperature']) <= 1.0:
                            self.temperature = float(default(kwargs['temperature'], self.default.temperature, [None, -1]))
                            accepted_params += 1
                if 'frequency_penalty' in kwargs:
                    if isinstance(kwargs['frequency_penalty'], Union[int, float, None]):
                        if kwargs['frequency_penalty'] is None:
                            self.frequency_penalty = self.default.frequency_penalty
                            accepted_params += 1
                        elif int(kwargs['frequency_penalty']) == -1 or 0.2 < float(kwargs['frequency_penalty']) <= 1.0:
                            self.frequency_penalty = float(default(kwargs['frequency_penalty'], self.default.frequency_penalty, [None, 1]))
                            accepted_params += 1
                if 'presence_penalty' in kwargs:
                    if isinstance(kwargs['presence_penalty'], Union[int, float, None]):
                        if kwargs['presence_penalty'] is None:
                            self.presence_penalty = self.default.presence_penalty
                            accepted_params += 1
                        elif int(kwargs['presence_penalty']) == -1 or 0.0 < float(kwargs['presence_penalty']) <= 1.0:
                            self.presence_penalty = float(default(kwargs['presence_penalty'], self.default.presence_penalty, [None, -1]))
                            accepted_params += 1
                return accepted_params
            except Exception as e:
                error = MaicaInputWarning(e, '422')
                asyncio.run(messenger(rsc.websocket, status='maica_settings_param_rejected', traceray_id=rsc.traceray_id, error=error))

    class _temp(_common_funcs):
        """Should be reset after each round of completion."""
        class _default():
            chat_session = 0
            sf_extraction_once = False
            """Enable sf_extraction once while sf provided with query"""
            mt_extraction_once = False
            """Enable mt_extraction once while mt provided with query"""
            bypass_mf = False
            """Bypass MFocus once"""
            bypass_mt = False
            """Bypass MTrigger once"""
            bypass_stream = False
            """Bypass stream output once"""
            bypass_sup = False
            """Bypass super params once"""
            bypass_gen = False
            """Bypass generation once"""
            ic_prep = False
            """Adjust generation params once, basically for MPostal"""
            strict_conv = True
            """Strict conversation prompt"""
            ms_cache = False
            """Cache the MSpire response"""
            def __call__(self):
                return {
                    'chat_session': self.chat_session,
                    'sf_extraction_once': self.sf_extraction_once,
                    'mt_extraction_once': self.mt_extraction_once,
                    'bypass_mf': self.bypass_mf,
                    'bypass_mt': self.bypass_mt,
                    'bypass_stream': self.bypass_stream,
                    'bypass_sup': self.bypass_sup,
                    'bypass_gen': self.bypass_gen,
                    'ic_prep': self.ic_prep,
                    'strict_conv': self.strict_conv,
                    'ms_cache': self.ms_cache,
                }
        def __call__(self):
            return {
                'chat_session': self.chat_session,
                'sf_extraction_once': self.sf_extraction_once,
                'mt_extraction_once': self.mt_extraction_once,
                'bypass_mf': self.bypass_mf,
                'bypass_mt': self.bypass_mt,
                'bypass_stream': self.bypass_stream,
                'bypass_sup': self.bypass_sup,
                'bypass_gen': self.bypass_gen,
                'ic_prep': self.ic_prep,
                'strict_conv': self.strict_conv,
                'ms_cache': self.ms_cache,
            }
        def update(self, rsc=None, **kwargs):
            if not rsc:
                rsc = FscPlain.RealtimeSocketsContainer()
            accepted_params = 0
            try:
                if 'chat_session' in kwargs:
                    if isinstance(kwargs['chat_session'], Optional[int]):
                        if kwargs['chat_session'] is None:
                            self.chat_session = self.default.chat_session
                        elif -1 <= int(kwargs['chat_session']) < 10:
                            self.chat_session = int(kwargs['chat_session'])
                if 'sf_extraction_once' in kwargs:
                    self.sf_extraction_once = bool(default(kwargs['sf_extraction_once'], self.default.sf_extraction_once))
                    accepted_params += 1
                if 'mt_extraction_once' in kwargs:
                    self.mt_extraction_once = bool(default(kwargs['mt_extraction_once'], self.default.mt_extraction_once))
                    accepted_params += 1
                if 'bypass_mf' in kwargs:
                    self.bypass_mf = bool(default(kwargs['bypass_mf'], self.default.bypass_mf))
                    accepted_params += 1
                if 'bypass_mt' in kwargs:
                    self.bypass_mt = bool(default(kwargs['bypass_mt'], self.default.bypass_mt))
                    accepted_params += 1
                if 'bypass_stream' in kwargs:
                    self.bypass_stream = bool(default(kwargs['bypass_stream'], self.default.bypass_stream))
                    accepted_params += 1
                if 'bypass_sup' in kwargs:
                    self.bypass_sup = bool(default(kwargs['bypass_sup'], self.default.bypass_sup))
                    accepted_params += 1
                if 'bypass_gen' in kwargs:
                    self.bypass_gen = bool(default(kwargs['bypass_gen'], self.default.bypass_gen))
                    accepted_params += 1
                if 'ic_prep' in kwargs:
                    self.ic_prep = bool(default(kwargs['ic_prep'], self.default.ic_prep))
                    accepted_params += 1
                if 'strict_conv' in kwargs:
                    self.strict_conv = bool(default(kwargs['strict_conv'], self.default.strict_conv))
                    accepted_params += 1
                if 'ms_cache' in kwargs:
                    self.ms_cache = bool(default(kwargs['ms_cache'], self.default.ms_cache))
                    accepted_params += 1
                return accepted_params
            except Exception as e:
                error = MaicaInputWarning(e, '422')
                asyncio.run(messenger(rsc.websocket, status='maica_settings_param_rejected', traceray_id=rsc.traceray_id, error=error))

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

    def update(self, secure=None, rsc=None, **kwargs):
        """Used for handling manual settings."""
        if secure is False:
            accepted_params = self.identity.update(rsc, **kwargs)
        elif secure is True:
            accepted_params = self.verification.update(rsc, **kwargs)
        else:
            accepted_params = self.basic.update(rsc, **kwargs) + self.extra.update(rsc, **kwargs) + self.super.update(rsc, **kwargs)
            # We do not accept temps to be manually set
        return accepted_params

