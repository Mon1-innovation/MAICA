"""Import layer 2.1"""

import orjson
from urllib.parse import urlsplit

from typing import *
from pydantic import BaseModel, RootModel, Field

from .setting_utils import MaicaSettings
from .maica_utils import *

_Bt = BilingualText

class WsBasicConfig(BaseModel):
    type: Literal["auth", "ping", "sping", "reconn", "params", "query"]

class WsPermissionConfig(WsBasicConfig):
    """This takes and validates a login input."""
    type: Literal["auth"]
    access_token: str = Field(min_length=1, max_length=4096)

class WsPingConfig(WsBasicConfig):
    type: Literal["ping"]

class WsSPingConfig(WsBasicConfig):
    """Silent Ping."""
    type: Literal["sping"]

class WsReconnConfig(WsBasicConfig):
    type: Literal["reconn"]

class WsSettingsConfig(WsBasicConfig):
    type: Literal["params"]
    chat_params: dict = Field(default_factory=dict)
    reset: bool = False

class WsQueryConfig(WsBasicConfig):
    """This takes and validates a query input."""
    type: Literal["query"]

    class MCommonConfig(BaseModel):
        bypass_mf: bool = False
        bypass_mt: bool = False
        bypass_stream: bool = False
        twk_super: bool = False
        strict_conv: bool = True

    class MSpireConfig(MCommonConfig, MaicaSettings.Temp.MSpire):

        # And its defaults
        bypass_mf: bool = True
        bypass_mt: bool = True

    class MPostalConfig(MCommonConfig, MaicaSettings.Temp.MPostal):
        """content is enforced for MPostal, ofc."""

        # And its defaults
        bypass_mf: bool = True
        bypass_mt: bool = True
        bypass_stream: bool = True
        twk_super: bool = True
        strict_conv: bool = False

    class MVistaConfig(RootModel):
        """This is not the same as above, kinda."""
        root: str | list[str]

        @model_validator(mode="after")
        def enhanced_defaults(self):
            if isinstance(self.root, str):
                self.root = [self.root]

            if len(self.root) > int(G.A.KEEP_MVISTA):
                raise MaicaInputWarning(f"At most {G.A.KEEP_MVISTA} images are allowed per query")

            allowed_hosts = {
                host.strip().lower()
                for host in G.A.VISION_HOST_ALLOWLIST.split(",")
                if host.strip()
            }
            for image_url in self.root:
                if len(image_url) > 2048:
                    raise MaicaInputWarning("MVista image URL is too long")
                parsed = urlsplit(image_url)
                if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                    raise MaicaInputWarning("MVista accepts only absolute HTTP(S) image URLs")
                if parsed.username or parsed.password:
                    raise MaicaInputWarning("MVista image URLs cannot contain credentials")
                if allowed_hosts and parsed.hostname.lower() not in allowed_hosts:
                    raise MaicaPermissionWarning("MVista image URL host is not allowed", 403)

            return self

    class ExSavefile(RootModel):
        """Extra persistent."""
        root: dict[str, Any]

    class ExTriggers(RootModel):
        """Extra triggers."""
        root: list[dict]

    class PprtConfig(BaseModel):
        yield_interval: list[Annotated[int, Field(ge=1, le=1000)]] = Field(
            default_factory=lambda: [40, 20, 10, 5, 3, 1],
            min_length=1,
            max_length=10,
        )
        split_limit: int = Field(
            default=180,
            ge=-1,
            le=4096,
        )
        correct_malform: bool = True

    chat_session: int = Field(
        default=0,
        ge=-1,
        le=9,
    )
    query: Optional[str | list] = None
    reset: Optional[bool] = None
    """True for resetting a session."""
    vision: Optional[MVistaConfig] = None
    """One or several images' url."""
    inspire: Optional[MSpireConfig] = None
    """MSpire config."""
    postmail: Optional[MPostalConfig] = None
    """MPostal config."""
    savefile: Optional[ExSavefile] = None
    """Temp persistent."""
    triggers: Optional[ExTriggers] = None
    """Temp triggers."""
    pprt: Union[bool, PprtConfig] = True
    """Post-proc-realtime."""

    activated: Literal["query", "mspire", "mpostal"] = "query"

    @model_validator(mode="after")
    def exclusion_det(self):
        excl_set = set()
        for item_name in (
            "query",
            "reset",
            "inspire",
            "postmail",
        ):
            if getattr(self, item_name):
                excl_set.add(item_name)
        
        if len(excl_set) > 1:
            raise MaicaInputWarning(f"Params are exclusive: {', '.join(excl_set)}")
        elif not excl_set:
            raise MaicaInputWarning("No action chosen")
        
        match list(excl_set)[0]:
            case "query":
                self.activated = "query"
            case "inspire":
                self.activated = "mspire"
            case "postmail":
                self.activated = "mpostal"
                if not self.postmail.content:
                    raise MaicaInputWarning("MPostal must have content")
            case _:
                # If it's reset this doesn't matter
                self.activated = "query"

        return self
    
    @model_validator(mode="after")
    def session_validations(self):
        if not self.reset:
            if self.chat_session <= -1:
                if not isinstance(self.query, list):
                    raise MaicaInputWarning("-1 session requires list input")
                
                if len(self.query) > 10:
                    raise MaicaInputWarning(f"-1 session cannot exceed 10 rounds, got {len(self.query)}")
                
                if self.activated != "query":
                    raise MaicaInputWarning("MS/MP not allowed for session -1")
            
            if (
                self.chat_session >= 0
                and not isinstance(self.query, str)
            ):
                raise MaicaInputWarning("0~9 session requires str input")
            
            if (
                self.chat_session != 0
                and self.inspire
                and self.inspire.use_cache
            ):
                raise MaicaInputWarning("MSpire use_cache only applies to session 0")
            
        else:
            if self.chat_session <= 0:
                raise MaicaInputWarning("session <= 0 cannot be reset due to not hosted")

        return self

    @model_validator(mode="after")
    def size_validations(self):
        if isinstance(self.query, list):
            b = orjson.dumps(self.query)
            if len(b) > 16 * 1024:
                raise MaicaInputWarning(f"-1 session cannot exceed 16KB, got {(len(b) / 1024):.2f}KB")
            
        elif isinstance(self.query, str):
            b = self.query.encode()
            if len(b) > 4 * 1024:
                raise MaicaInputWarning(f"0~9 session input cannot exceed 4KB, got {(len(b) / 1024):.2f}KB")
            
        return self

type UnionStage1Settings = Union[
    WsPermissionConfig,
    WsPingConfig,
    WsSPingConfig,
]
type UnionStage2Settings = Union[
    WsPingConfig,
    WsSPingConfig,
    WsReconnConfig,
    WsSettingsConfig,
    WsQueryConfig,
]
Stage1Settings = Annotated[
    UnionStage1Settings,
    Field(discriminator="type"),
]
Stage2Settings = Annotated[
    UnionStage2Settings,
    Field(discriminator="type"),
]
