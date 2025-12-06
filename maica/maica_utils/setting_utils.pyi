from typing import *
from typing_extensions import deprecated
from dataclasses import dataclass

MAX_LENGTH: int

@dataclass
class _CommonFuncs:
    def reset(self) -> None: ...
    
    def _dict(self) -> Dict[str, Any]: ...
    
    def __iter__(self) -> Iterator[Tuple[str, Any]]: ...
    
    @deprecated("Use dict(instance) instead")
    def __call__(self, *args: Any, **kwargs: Any) -> Dict[str, Any]: ...
    
    def update(self, **kwargs: Any) -> int: ...
    
    @classmethod
    def default(cls, key: Optional[str] = None) -> Union[Dict[str, Any], Any]: ...

def create_prop(
    name: str,
    getter_ext: Optional[List[Callable]] = None,
    getter_kwargs: Optional[Dict[str, Any]] = None,
    setter_ext: Optional[List[Callable]] = None,
    setter_kwargs: Optional[Dict[str, Any]] = None,
) -> property: ...

def read_exist(self: Any, n: str, v: Any, **kwargs: Any) -> Any: ...

def set_locked(self: Any, n: str, v: Any, **kwargs: Any) -> Any: ...

def set_literal(self: Any, n: str, v: Any, valid: List[Any], **kwargs: Any) -> Any: ...

def set_range(
    self: Any, 
    n: str, 
    v: Any, 
    lower: Union[int, float], 
    upper: Union[int, float], 
    **kwargs: Any
) -> Any: ...

def set_instance(self: Any, n: str, v: Any, types: List[Optional[Type[Any]]], **kwargs: Any) -> Any: ...

def set_spec_default(self: Any, n: str, v: Any, defaults: List[Any] = ..., **kwargs: Any) -> Any: ...

class MaicaSettings:
    @dataclass
    class _Identity(_CommonFuncs):
        user_id: int
        username: str
        nickname: Optional[str]
        email: str
        
    @dataclass
    class _Verification(_Identity):...

    @dataclass
    class _Basic(_CommonFuncs):
        stream_output: bool
        deformation: bool
        enable_mf: bool
        enable_mt: bool
        sf_extraction: bool
        mt_extraction: bool
        target_lang: Literal['zh', 'en']
        max_length: int

    @dataclass
    class _Extra(_CommonFuncs):
        sfe_aggressive: bool
        mf_aggressive: bool
        tnd_aggressive: int
        esc_aggressive: bool
        amt_aggressive: bool
        nsfw_acceptive: bool
        pre_additive: int
        post_additive: int
        tz: Optional[str]
        dscl_pvn: bool
        pre_astp: bool
        post_astp: bool
        enforce_lang: bool

    @dataclass
    class _Super(_CommonFuncs):
        max_tokens: int
        seed: Optional[int]
        top_p: float
        temperature: float
        frequency_penalty: float
        presence_penalty: float

    @dataclass
    class _Temp(_CommonFuncs):
        chat_session: int
        sf_extraction_once: bool
        mt_extraction_once: bool
        bypass_mf: bool
        bypass_mt: bool
        bypass_stream: bool
        bypass_sup: bool
        bypass_gen: bool
        ic_prep: bool
        strict_conv: bool
        ms_cache: bool
        mv_imgs: Optional[list]

    identity: _Identity
    verification: _Verification
    basic: _Basic
    extra: _Extra
    super: _Super
    temp: _Temp
    
    def __init__(self) -> None: ...
    
    def _dict(self) -> Dict[str, Any]: ...
    
    def __iter__(self) -> Iterator[Tuple[str, Any]]: ...
    
    def reset(self) -> None: ...
    
    def update(self, secure: Optional[bool] = None, **kwargs: Any) -> int: ...