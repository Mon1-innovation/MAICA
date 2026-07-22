"""
Import layer 3.9
Here we handle the users things individually, and provide as mixins.
"""
from __future__ import annotations

import asyncio
import bcrypt
import datetime
import hashlib
import orjson
import time

import sqlalchemy
from sqlalchemy.orm import load_only

from typing import *
from pydantic import BaseModel, RootModel, EmailStr, Field, model_validator
from .encryption_utils import crypto_object, decrypt_token, encrypt_token
from .maica_utils import *
from .database_utils import *
from .database_models import *
from .gvars import online_dict, online_dict_guard

_DUMMY_PASSWORD_HASH = bcrypt.hashpw(b"maica-invalid-credential", bcrypt.gensalt())


def auth_token_reference(token: str) -> str:
    """Return a short, non-reusable identifier for correlating auth logs."""
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()[:12]
    return f"sha256:{digest}/{len(token)}ch"

if TYPE_CHECKING:
    from .fsc_late import *

class FscUsersFuncMixin():
    """User functions for MaicaSetting.Identity, such as logging in."""
    rsc: RealtimeSocketsContainer
    csc: ConnSocketsContainer

    class TokenCridential(BaseModel):
        """The auth crids."""
        username: Optional[str] = Field(default=None, min_length=1, max_length=100)
        email: Optional[EmailStr] = Field(default=None, max_length=150)
        password: str = Field(min_length=1, max_length=72)
        type: Optional[Literal["username", "email"]] = None
        
        @property
        def identity(self):
            if self.type == "username":
                return self.username
            elif self.type == "email":
                return self.email
            else:
                raise MaicaInputError("No type determined before access")

        @model_validator(mode="after")
        def det_type(self):
            if bool(self.username) == bool(self.email):
                raise MaicaInputWarning("Exactly one of username or email must exist")
            if self.username:
                self.type = "username"
            else:
                self.type = "email"
            
            return self
        
        async def generate_token(self):
            """Used in http token generation phase."""
            data_j = {"password": self.password}
            
            match self.type:
                case "username":
                    data_j["username"] = self.username
                case "email":
                    data_j["email"] = self.email

            data_str = orjson.dumps(data_j).decode()
            key_size_bytes = crypto_object.public_key.key_size // 8
            max_plaintext = key_size_bytes - 2 * 20 - 2
            if len(data_str.encode("utf-8")) > max_plaintext:
                raise MaicaInputWarning("Credentials are too long for this server's RSA key")
            token = await asyncio.to_thread(encrypt_token, data_str)

            return token

    async def login(self, crid_b64: Optional[str] = None):
        """
        This replaces the former hash_and_login, and all complex procedures.
        - crid_b64: str, base64 encoded. If not provided, we're running common checks.
        """
        if crid_b64:
            token_ref = auth_token_reference(crid_b64)
            sync_messenger(info=f"Authentication attempt token={token_ref}", type=MsgType.RECV)

            try:
                crid = await asyncio.to_thread(decrypt_token, crid_b64)

                token_cridential = self.TokenCridential.model_validate_json(crid)

            except Exception as exc:
                sync_messenger(
                    info=(
                        f"Authentication token={token_ref} failed during token decode or validation "
                        f"({type(exc).__name__})"
                    ),
                    type=MsgType.WARN,
                )
                raise MaicaInputWarning("Failed parsing access_token") from exc

            sync_messenger(
                info=(
                    f"Authentication token={token_ref} decoded for "
                    f"{token_cridential.type}={token_cridential.identity!s} "
                    f"with password_length={len(token_cridential.password)}"
                ),
                type=MsgType.DEBUG,
            )

            async with DatabaseUtils.SessionAuth() as aus:

                stmt = sqlalchemy.select(SqlUser).where(
                    getattr(SqlUser, token_cridential.type) == token_cridential.identity,
                )
                obj = await aus.scalar(stmt)

                if not obj:
                    await asyncio.to_thread(
                        bcrypt.checkpw,
                        token_cridential.password.encode(),
                        _DUMMY_PASSWORD_HASH,
                    )
                    sync_messenger(
                        info=f"Authentication token={token_ref} failed: account was not found",
                        type=MsgType.WARN,
                    )
                    raise MaicaPermissionWarning("Invalid username/email or password")

            user_id = obj.id
            username = obj.username
            nickname = obj.nickname
            email = obj.email
            is_email_confirmed = obj.is_email_confirmed
            password = obj.password
            suspended_until = obj.suspended_until

            # SQLA transaction for strict security
            block_auth = False
            async with DatabaseUtils.SessionData() as dbs:
                async with dbs.begin():

                    obj = await sqla_get_or_create(
                        dbs,
                        SqlAccountStatus,
                        {"id": user_id},
                        requires=("status", ),
                    )

                    if obj.status is None:
                        obj.status = {}
                    status = obj.status

                    f2b_count: int = status.get("f2b_count") or 0
                    f2b_until: float = status.get("f2b_until") or 0.0

                    # Check if currently blocked by f2b
                    curr_timestamp = time.time()
                    if f2b_until > curr_timestamp:

                        f2b_display = datetime.datetime.fromtimestamp(f2b_until).isoformat()
                        raise MaicaPermissionWarning(f"Fail2Ban interventing until {f2b_display}")
                    
                    # Then password verification
                    user_pwd_encoded = token_cridential.password.encode()
                    db_pwd_encoded = password.encode()
                    is_pwd_correct = await asyncio.to_thread(bcrypt.checkpw, user_pwd_encoded, db_pwd_encoded)

                    # If not correct, we add to F2B and break
                    if not is_pwd_correct:
                        f2b_count += 1

                        sys_f2b_count = int(G.A.F2B_COUNT)
                        sys_f2b_time = float(G.A.F2B_TIME)

                        if f2b_count >= sys_f2b_count:
                            f2b_count = 0
                            f2b_until = time.time() + sys_f2b_time
                            status["f2b_until"] = f2b_until

                        status["f2b_count"] = f2b_count

                        block_auth = True
                    
                    # If correct, we clear f2b count
                    elif f2b_count:
                        status["f2b_count"] = 0

            # It should have committed by now
            if block_auth:
                sync_messenger(
                    info=f"Authentication token={token_ref} failed: password mismatch for user_id={user_id}",
                    type=MsgType.WARN,
                )
                raise MaicaPermissionWarning("Invalid username/email or password")
            
        # If running common check, we assert logged in already
        else:
            user_id = self.rsc.maica_settings.verification.user_id
            if not user_id:
                raise MaicaPermissionError("Common login checks require an authenticated identity")

            async with DatabaseUtils.SessionAuth() as aus:

                stmt = sqlalchemy.select(SqlUser).where(
                    SqlUser.id == user_id,
                ).options(
                    load_only(SqlUser.is_email_confirmed, SqlUser.suspended_until)
                )
                obj = await aus.scalar(stmt)
                if obj is None:
                    raise MaicaPermissionError("User no longer exists, something might went wrong")

                is_email_confirmed = obj.is_email_confirmed
                suspended_until = obj.suspended_until

        # Check if banned here
        time_now = (
            datetime.datetime.now(tz=suspended_until.tzinfo)
            if suspended_until and suspended_until.tzinfo
            else datetime.datetime.now()
        )
        if (
            suspended_until
            and suspended_until > time_now
        ):
            raise MaicaPermissionWarning(f"User banned until {suspended_until.isoformat()}")

        # Check if email verified here
        if not is_email_confirmed:
            raise MaicaPermissionWarning("Email not verified, check your inbox")

        # Only assign these if not common check
        if crid_b64:

            # We should be all set
            verification = self.rsc.maica_settings.verification
            (
                verification.user_id,
                verification.username,
                verification.email,
                verification.nickname,
            ) = (
                user_id,
                username,
                email,
                nickname,
            )

            if self.rsc.websocket:
                connection_lock = self.rsc.session_lock
                if connection_lock is None:
                    raise MaicaConnectionWarning("WebSocket session lock is missing")

                async with online_dict_guard:
                    stale_entry = online_dict.get(user_id)
                    if stale_entry and stale_entry[1].locked() and not int(G.A.KICK_STALE_CONNS):
                        raise MaicaConnectionWarning(
                            'A connection was established already and kicking is disabled',
                            406,
                            'maica_connection_reuse_denied',
                        )
                    online_dict[user_id] = (self, connection_lock)

                if stale_entry and stale_entry[1].locked():
                    try:
                        await self.rsc.messenger(
                            "maica_connection_reuse_attempt",
                            "A connection was established already",
                            300,
                        )
                    except Exception as exc:
                        sync_messenger(info=f"Could not announce stale replacement: {exc}", type=MsgType.DEBUG)
                    stale_fsc, stale_lock = stale_entry
                    try:
                        await stale_fsc.messenger(
                            'maica_connection_reuse_stale',
                            'A new connection has been established',
                            300,
                        )
                        await stale_fsc.websocket.close(1000, 'Displaced as stale')
                    except Exception as exc:
                        sync_messenger(
                            info=f'The stale connection has died already: {exc}',
                            type=MsgType.LOG,
                        )

                    async with stale_lock:
                        sync_messenger(
                            status='maica_connection_stale_kicked',
                            info='The stale connection is kicked',
                            code=204,
                        )

        # Return a True, though we don't need it
        return True
