"""
Import layer 3.9
Here we handle the users things individually, and provide as mixins.
"""

import bcrypt

from typing import *
from pydantic import BaseModel, RootModel, EmailStr, Field, model_validator
from base64 import b64encode, b64decode
from .encryption_utils import crypto_object
from .maica_utils import *
from .transaction import MaicaTransaction

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
            
    class UserStatModel(RootModel):
        root: dict

    async def get_stat(self, column: Literal["status", "preferences"], ks: list):
        """
        Get account status / preferences.
        Notice: Use MaicaTransaction for integrity sensitive cases.
        """

        transaction = MaicaTransaction(
            self,
            table="account_status",
            column=column,
            jsonks=ks,
            where={"user_id": self.rsc.maica_settings.verification.user_id},
        )
        
        await transaction.get_oneshot()

    async def set_stat(self, column: Literal["status", "preferences"], kvs: dict):
        """
        Set account status / preferences.
        Notice: Use MaicaTransaction for integrity sensitive cases.
        """

        transaction = MaicaTransaction(
            self,
            table="account_status",
            column=column,
            jsonks=kvs.keys(),
            where={"user_id": self.rsc.maica_settings.verification.user_id},
        )
        
        await transaction.set_oneshot(kvs.values())

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

            sql_expression = f'SELECT id, username, nickname, email, is_email_confirmed, password, suspended_until FROM users WHERE {token_cridential.type} = %s'
            result = await self.csc.auth_pool.query_get(expression=sql_expression, values=(token_cridential.identity, ))
            if not result:
                raise MaicaPermissionWarning("User does not exist")

            (
                user_id,
                username,
                nickname,
                email,
                is_email_confirmed,
                password,
                suspended_until,
            ) = result

            # For consistency consideration (multiple logins simultaneously) we use transaction
            transaction = MaicaTransaction(
                self,
                table="account_status",
                column="status",
                jsonks=["f2b_count", "f2b_until"],
                where={"user_id": user_id},
            )
            async with transaction.acquire() as result_l:

                # F2B goes first
                f2b_count, f2b_until = result_l

                curr_timestamp = time.time()
                if (
                    f2b_until
                    and f2b_until > curr_timestamp
                ):
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
                        result_l[1] = f2b_until

                    result_l[0] = f2b_count
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
            assert self.rsc.maica_settings.verification.user_id, "Common checking require identities"

            sql_expression = f'SELECT is_email_confirmed, suspended_until FROM users WHERE id = %s'
            result = await self.csc.auth_pool.query_get(expression=sql_expression, values=(self.rsc.maica_settings.verification.user_id, ))
            if not result:
                raise MaicaPermissionWarning("User does not exist")

            (
                is_email_confirmed,
                suspended_until,
            ) = result


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