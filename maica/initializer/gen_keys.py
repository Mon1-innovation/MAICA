import os
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from maica.maica_utils import get_inner_path, sync_messenger, MsgType

def get_keys_path():
    prv_path = get_inner_path('keys/prv.key')
    pub_path = get_inner_path('keys/pub.key')
    prv_path = os.path.abspath(prv_path)
    pub_path = os.path.abspath(pub_path)
    return prv_path, pub_path

def export_keys(to: str):
    prv_path, pub_path = get_keys_path()
    if not (os.path.isfile(prv_path) and os.path.isfile(pub_path)):
        sync_messenger(info=f'[maica-keys] {prv_path} and {pub_path} must exist, quitting...', type=MsgType.WARN)
        return
    try:
        with open(prv_path, "r") as prvkey_file:
            prvkey = prvkey_file.read()
        with open(pub_path, "r") as pubkey_file:
            pubkey = pubkey_file.read()
        
        sync_messenger(info="[maica-keys] Keys exist, exporting...", type=MsgType.DEBUG)
        
        prv_new = os.path.abspath(os.path.join(to, 'prv.key'))
        pub_new = os.path.abspath(os.path.join(to, 'pub.key'))

        yank_file(prv_new)
        yank_file(pub_new)

        with open(prv_new, "x") as prvkey_file:
            prvkey_file.write(prvkey)
        os.chmod(prv_new, 0o600)
        with open(pub_new, "x") as pubkey_file:
            pubkey_file.write(pubkey)

        sync_messenger(info=f"[maica-keys] Keys exported to {prv_new} and {pub_new}", type=MsgType.LOG)
        return

    except Exception as e:
        sync_messenger(info=f"[maica-keys] Error: {str(e)}", type=MsgType.ERROR)
        raise

def import_keys(frm: str):
    prv_new = os.path.abspath(os.path.join(frm, 'prv.key'))
    pub_new = os.path.abspath(os.path.join(frm, 'pub.key'))
    if not (os.path.isfile(prv_new) and os.path.isfile(pub_new)):
        sync_messenger(info=f'[maica-keys] {prv_new} and {pub_new} must exist, quitting...', type=MsgType.WARN)
        return
    try:
        with open(prv_new, "r") as prvkey_file:
            prvkey = prvkey_file.read()
        with open(pub_new, "r") as pubkey_file:
            pubkey = pubkey_file.read()
        
        sync_messenger(info="[maica-keys] Keys exist, importing...", type=MsgType.DEBUG)

        prv_path, pub_path = get_keys_path()

        yank_file(prv_path), yank_file(pub_path)

        with open(prv_path, "x") as prvkey_file:
            prvkey_file.write(prvkey)
        with open(pub_path, "x") as pubkey_file:
            pubkey_file.write(pubkey)

        os.chmod(prv_path, 0o600)
        sync_messenger(info=f"[maica-keys] Keys imported to {prv_path} and {pub_path}", type=MsgType.LOG)
        return

    except Exception as e:
        sync_messenger(info=f"[maica-keys] Error: {str(e)}", type=MsgType.ERROR)
        raise

def yank_file(path: str, prefix="[maica-keys] "):
    if os.path.isfile(path):
        yanked_path = path + ".old"
        sync_messenger(info=f"{prefix}Target file exists already, moving it to {yanked_path}...")

        # We only keep one old copy. You should have copied them away if they're indeed important
        os.replace(path, yanked_path)

def generate_rsa_keys():
    prv_path, pub_path = get_keys_path()
    if os.path.isfile(prv_path) and os.path.isfile(pub_path):
        sync_messenger(info="[maica-keys] Keys exist already, skipping...", type=MsgType.WARN)
        return
    else:
        sync_messenger(info="[maica-keys] Keys not exist, creating...", type=MsgType.DEBUG)
        os.makedirs(get_inner_path('keys'), exist_ok=True)
        yank_file(prv_path)
        yank_file(pub_path)
    
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_key = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )

        with open(prv_path, "wb") as prv_file:
            prv_file.write(private_key)
        os.chmod(prv_path, 0o600)
        
        public_key = key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        with open(pub_path, "wb") as pub_file:
            pub_file.write(public_key)

        sync_messenger(info="[maica-keys] Keys generated successfully, store with care!", type=MsgType.LOG)

# 使用示例
if __name__ == "__main__":
    generate_rsa_keys()  # 使用默认路径
