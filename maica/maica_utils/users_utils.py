"""
Import layer 3.9
Here we handle the users things individually, and provide as mixins.
"""

import asyncio
import bcrypt
import orjson

import sqlalchemy
from sqlalchemy.orm import load_only

from typing import *
from pydantic import BaseModel, RootModel, EmailStr, Field, model_validator
from base64 import b64encode, b64decode
from .encryption_utils import crypto_object
from .maica_utils import *

if TYPE_CHECKING:
    from .fsc_late import *
else:
    class ConnSocketsContainer(): ...
    class RealtimeSocketsContainer(): ...

class FscUsersFuncMixin():
    """User functions for MaicaSetting.Identity, such as logging in."""
    rsc: RealtimeSocketsContainer
    csc: ConnSocketsContainer

    class TokenCridential(BaseModel):
        """The auth crids."""
        username: Optional[str] = None
        email: Optional[EmailStr] = None
        password: str
        type: ClassVar[Literal["username", "email"]]
        identity: ClassVar[str]

        @model_validator(mode="after")
        def det_type(self):
            if self.username:
                self.type = "username"
                self.identity = self.username
            elif self.email:
                self.type = "email"
                self.identity = self.email
            else:
                raise MaicaInputWarning("username or email must exist")
            
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
            token = await asyncio.to_thread(encrypt_token, data_str)

            return token

    async def login(self, crid_b64: Optional[str] = None):
        """
        This replaces the former hash_and_login, and all complex procedures.
        - crid_b64: str, base64 encoded. If not provided, we're running common checks.
        """
        if crid_b64:

            try:
                crid_ub = await asyncio.to_thread(b64decode, crid_b64)
                crid_ue = await asyncio.to_thread(crypto_object.decryptor.decrypt, crid_ub)
                crid = crid_ue.decode()

                token_cridential = self.TokenCridential.model_validate_json(crid)

            except Exception as e:
                raise MaicaInputWarning(f"Failed parsing access_token: {str(e)}")


            async with DatabaseUtils.SessionAuth() as aus:

                stmt = sqlalchemy.select(SqlUser).where(
                    getattr(SqlUser, token_cridential.type) == token_cridential.identity,
                )
                obj = await aus.scalar(stmt)

                if not obj:
                    raise MaicaPermissionWarning("User does not exist")

            (
                user_id,
                username,
                nickname,
                email,
                is_email_confirmed,
                password,
                suspended_until,
            ) = obj.model_to_dict().values()

            # SQLA transaction for strict security
            block_auth = False
            async with DatabaseUtils.SessionData() as dbs:
                async with dbs.begin():

                    obj = await sqla_get_or_create(
                        dbs,
                        SqlAccountStatus,
                        {"user_id": user_id},
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

                        if f2b_count >= G.A.F2B_COUNT:
                            f2b_count = 0
                            f2b_until = time.time() + G.A.F2B_TIME
                            status["f2b_until"] = f2b_until

                        status["f2b_count"] = f2b_count

                        block_auth = True
                    
                    # If correct, we clear f2b count
                    elif f2b_count:
                        status["f2b_count"] = 0

            # It should have committed by now
            if block_auth:
                raise MaicaPermissionWarning(f"Wrong password, check and retry")
            
            # Check if this account is logged in already
            # If websocket filled, we know it's websocket login and must stay unique
            # else we don't have to
            if (
                self.rsc.websocket
                and online_dict.get(user_id)
                and online_dict[user_id][1].locked()
            ):
                if not int(G.A.KICK_STALE_CONNS):
                    raise MaicaConnectionWarning('A connection was established already and kicking not enabled', 406, 'maica_connection_reuse_denied')
                
                else:
                    await self.rsc.messenger(
                        "maica_connection_reuse_attempt",
                        "A connection was established already",
                        300,
                    )

                    stale_fsc, stale_lock = online_dict[user_id]
                    try:
                        await stale_fsc.messenger(
                            'maica_connection_reuse_stale',
                            'A new connection has been established',
                            300,
                        )
                        await stale_fsc.websocket.close(1000, 'Displaced as stale')

                    except Exception as e:
                        sync_messenger(info=f'The stale connection has died already: {str(e)}', type=MsgType.LOG)

                    try:
                        online_dict.pop(self.settings.verification.user_id)

                    except Exception:
                        pass

                    # We acquire stale lock here, to ensure stale session released it
                    async with stale_lock:
                        await messenger(None, 'maica_connection_stale_kicked', 'The stale connection is kicked', 204)

                    # Then we discard its reference
                    pass
            
        # If running common check, we assert logged in already
        else:
            user_id = self.rsc.maica_settings.verification.user_id
            assert user_id, "Common checking require identities"

            async with DatabaseUtils.SessionAuth() as aus:

                stmt = sqlalchemy.select(SqlUser).where(
                    SqlUser.id == user_id,
                ).options(
                    load_only(SqlUser.is_email_confirmed, SqlUser.suspended_until)
                )
                obj = await aus.scalar(stmt)

                is_email_confirmed = obj.is_email_confirmed
                suspended_until = obj.suspended_until

        # Check if banned here
        time_now = datetime.datetime.now()
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

        # Return a True, though we don't need it
        return True