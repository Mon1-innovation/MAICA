from Crypto.PublicKey import RSA
import os
from maica.maica_utils import get_outer_path

def generate_rsa_keys():

    prv_path = get_outer_path('keys/prv.key')
    pub_path = get_outer_path('keys/pub.key')

    try:
        with open(prv_path, "r") as privkey_file:
            privkey = privkey_file.read()
        with open(pub_path, "r") as pubkey_file:
            pubkey = pubkey_file.read()
        
        print("Keys exist already, skipping...")
        return
    
    except:
        print("Keys not exist, creating...")
        os.makedirs(get_outer_path('keys'))
    
        key = RSA.generate(2048)
        
        private_key = key.export_key()

        with open(prv_path, "wb") as priv_file:
            priv_file.write(private_key)
        
        public_key = key.publickey().export_key()

        with open(pub_path, "wb") as pub_file:
            pub_file.write(public_key)

        print("Keys generated successfully, store with care!")

# 使用示例
if __name__ == "__main__":
    generate_rsa_keys()  # 使用默认路径
