"""Import layer 2.1"""

import orjson
import ipaddress
import socket
from urllib.parse import urlsplit

from typing import *
from pydantic import BaseModel, RootModel, Field

from .setting_utils import MaicaSettings
from .maica_utils import *

_Bt = BilingualText


def _parse_vision_host_rules(raw_rules: str):
    denied_hosts: set[str] = set()
    allowed_hosts: set[str] = set()
    denied_networks = []
    allowed_networks = []
    deny_unmarked = False

    for raw_rule in (raw_rules or "").split(","):
        raw_rule = raw_rule.strip()
        if not raw_rule:
            continue
        denied = raw_rule.startswith("!")
        rule = raw_rule[1:].strip() if denied else raw_rule
        if not rule:
            raise ValueError("MAICA_VISION_HOST_ALLOWLIST contains an empty negated rule")
        if rule == "*":
            if not denied:
                raise ValueError("MAICA_VISION_HOST_ALLOWLIST supports only the !* wildcard")
            deny_unmarked = True
            continue

        try:
            network = ipaddress.ip_network(rule, strict=False)
        except ValueError as exc:
            if "/" in rule or ":" in rule:
                raise ValueError(
                    f"Invalid MAICA_VISION_HOST_ALLOWLIST rule: {raw_rule}"
                ) from exc
            (denied_hosts if denied else allowed_hosts).add(rule.lower().rstrip("."))
        else:
            (denied_networks if denied else allowed_networks).append(network)

    return (
        denied_hosts,
        allowed_hosts,
        denied_networks,
        allowed_networks,
        deny_unmarked,
    )


def _vision_host_allowed(host: str, raw_rules: str) -> bool:
    host = host.lower().rstrip(".")
    (
        denied_hosts,
        allowed_hosts,
        denied_networks,
        allowed_networks,
        deny_unmarked,
    ) = _parse_vision_host_rules(raw_rules)

    if host in denied_hosts:
        return False
    if host in allowed_hosts:
        return True

    try:
        host_ip = ipaddress.ip_address(host)
        resolved_ips = {host_ip}
    except ValueError:
        if not denied_networks and not allowed_networks:
            return not deny_unmarked
        try:
            resolved_ips = {
                ipaddress.ip_address(item[4][0])
                for item in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
            }
        except socket.gaierror as exc:
            raise MaicaInputWarning(
                f"MVista image URL host cannot be resolved: {host}"
            ) from exc

    def matches(networks) -> bool:
        return any(
            ip.version == network.version and ip in network
            for ip in resolved_ips
            for network in networks
        )

    if matches(denied_networks):
        return False
    if matches(allowed_networks):
        return True
    return not deny_unmarked

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

            for image_url in self.root:
                if len(image_url) > 2048:
                    raise MaicaInputWarning("MVista image URL is too long")
                parsed = urlsplit(image_url)
                if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                    raise MaicaInputWarning("MVista accepts only absolute HTTP(S) image URLs")
                if parsed.username or parsed.password:
                    raise MaicaInputWarning("MVista image URLs cannot contain credentials")
                if not _vision_host_allowed(parsed.hostname, G.A.VISION_HOST_ALLOWLIST):
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
                    raise MaicaInputWarning(f"-1 session requires list input, got {type(self.query).__name__}")
                
                if len(self.query) > 10:
                    raise MaicaInputWarning(f"-1 session cannot exceed 10 rounds, got {len(self.query)}")
                
                if self.activated != "query":
                    raise MaicaInputWarning("MS/MP not allowed for session -1")
            
            if (
                self.chat_session >= 0
                and self.activated == "query"
                and not isinstance(self.query, str)
            ):
                raise MaicaInputWarning(f"0~9 session requires str input, got {type(self.query).__name__}")
            
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

type Stage1Settings = Annotated[
    Union[
        WsPermissionConfig,
        WsPingConfig,
        WsSPingConfig,
    ],
    Field(discriminator="type"),
]
type Stage2Settings = Annotated[
    Union[
        WsPingConfig,
        WsSPingConfig,
        WsReconnConfig,
        WsSettingsConfig,
        WsQueryConfig,
    ],
    Field(discriminator="type"),
]
