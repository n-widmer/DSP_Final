import os
import json
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Load AES-GCM key from environment
_key_b64 = os.environ.get("GENDER_AGE_KEY")
if not _key_b64:
    raise RuntimeError("GENDER_AGE_KEY not set in environment")
KEY = base64.b64decode(_key_b64)

def encrypt_gender_age(gender: str, age: int) -> tuple[bytes, bytes]:
    """
    Encrypt gender and age as a single JSON blob using AES-GCM.
    Returns (nonce_bytes, ciphertext_bytes) for the DB.
    """
    aesgcm = AESGCM(KEY)
    nonce = os.urandom(12)  # 96-bit nonce
    plaintext = json.dumps({"gender": gender, "age": int(age)}).encode("utf-8")
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return nonce, ciphertext

def decrypt_gender_age(nonce: bytes, ciphertext: bytes) -> tuple[str, int]:
    """
    Decrypt nonce + ciphertext and return (gender, age).
    Raises if data is tampered with.
    """
    aesgcm = AESGCM(KEY)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    obj = json.loads(plaintext.decode("utf-8"))
    return obj["gender"], int(obj["age"])
