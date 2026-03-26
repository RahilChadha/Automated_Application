import os
import base64
from cryptography.fernet import Fernet
from dotenv import load_dotenv, set_key

load_dotenv()

_ENV_FILE = ".env"
_KEY_VAR = "ENCRYPTION_KEY"


def _get_or_create_key() -> bytes:
    key = os.getenv(_KEY_VAR)
    if key:
        return key.encode()
    new_key = Fernet.generate_key().decode()
    # Persist the key to .env
    if not os.path.exists(_ENV_FILE):
        open(_ENV_FILE, "w").close()
    set_key(_ENV_FILE, _KEY_VAR, new_key)
    os.environ[_KEY_VAR] = new_key
    return new_key.encode()


def encrypt_password(plaintext: str) -> str:
    f = Fernet(_get_or_create_key())
    return f.encrypt(plaintext.encode()).decode()


def decrypt_password(ciphertext: str) -> str:
    f = Fernet(_get_or_create_key())
    return f.decrypt(ciphertext.encode()).decode()
