"""Import layer 5"""
import asyncio
import base64

from typing import *

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from .maica_utils import *

class CryptoObject():
    public_key: Optional[rsa.RSAPublicKey] = None
    private_key: Optional[rsa.RSAPrivateKey] = None

    def filled(self):
        return bool(self.public_key and self.private_key)

crypto_object = CryptoObject()

def pkg_init_encryption_utils():
    _check_keys()

def _get_keys():
    prv_path = get_inner_path('keys/prv.key')
    pub_path = get_inner_path('keys/pub.key')

    with open(prv_path, "rb") as privkey_file:
        private_key = serialization.load_pem_private_key(privkey_file.read(), password=None)
    with open(pub_path, "rb") as pubkey_file:
        public_key = serialization.load_pem_public_key(pubkey_file.read())

    if not isinstance(private_key, rsa.RSAPrivateKey) or not isinstance(public_key, rsa.RSAPublicKey):
        raise TypeError("MAICA key files must contain RSA keys")
    return public_key, private_key

def _check_keys() -> bool:
    co = crypto_object
    if not co.filled():
        co.public_key, co.private_key = _get_keys()

def encrypt_token(cridential: str) -> str:
    """Generates an encrypted token. It does not care validity."""
    encoded_token = cridential.encode('utf-8')
    encrypted_token = crypto_object.public_key.encrypt(
        encoded_token,
        padding.OAEP(
            # SHA-1 is retained only for wire compatibility with tokens issued
            # by MAICA's historical PyCryptodome OAEP implementation.
            mgf=padding.MGF1(algorithm=hashes.SHA1()),  # nosec B303
            algorithm=hashes.SHA1(),  # nosec B303
            label=None,
        ),
    )
    decoded_token = base64.b64encode(encrypted_token).decode('utf-8')
    return decoded_token

def decrypt_token(token_b64: str) -> str:
    """Decrypt a base64-encoded MAICA credential token."""
    encrypted = base64.b64decode(token_b64, validate=True)
    decrypted = crypto_object.private_key.decrypt(
        encrypted,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA1()),  # nosec B303
            algorithm=hashes.SHA1(),  # nosec B303
            label=None,
        ),
    )
    return decrypted.decode("utf-8")

def sign_message(message: str):
    message = message.encode("utf-8")
    signature = crypto_object.private_key.sign(
        message,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=hashes.SHA256.digest_size,
        ),
        hashes.SHA256(),
    )
    sigb64 = base64.b64encode(signature).decode("utf-8")
    return sigb64

def verify_message(message: str, sigb64):
    message = message.encode("utf-8")
    signature = base64.b64decode(sigb64.encode("utf-8"))
    try:
        crypto_object.public_key.verify(
            signature,
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=hashes.SHA256.digest_size,
            ),
            hashes.SHA256(),
        )
    except InvalidSignature as exc:
        raise ValueError("Signature does not match") from exc

if __name__ == '__main__':
    from maica import init
    init(ignore_envc=True)
    pkg_init_encryption_utils()
    
    async def _atest():
        print(crypto_object.private_key)

    print(asyncio.run(_atest()))
