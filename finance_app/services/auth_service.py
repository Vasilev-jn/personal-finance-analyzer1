import base64
import hashlib
import hmac
import secrets
from typing import Optional


_DEFAULT_ITERATIONS = 240_000
_DKLEN = 32


def create_password_record(password: str, iterations: int = _DEFAULT_ITERATIONS) -> dict:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, dklen=_DKLEN)
    return {
        "v": 1,
        "algo": "pbkdf2_sha256",
        "iterations": iterations,
        "salt": base64.b64encode(salt).decode("ascii"),
        "hash": base64.b64encode(digest).decode("ascii"),
    }


def verify_password(password: str, record: dict) -> bool:
    if not isinstance(record, dict):
        return False
    if record.get("algo") != "pbkdf2_sha256":
        return False
    try:
        iterations = int(record.get("iterations") or 0)
        salt = base64.b64decode((record.get("salt") or "").encode("ascii"))
        expected = base64.b64decode((record.get("hash") or "").encode("ascii"))
    except Exception:
        return False
    if iterations < 50_000 or not salt or not expected:
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, dklen=len(expected))
    return hmac.compare_digest(actual, expected)


def record_secret(record: dict) -> Optional[str]:
    if not isinstance(record, dict):
        return None
    hash_value = record.get("hash")
    if isinstance(hash_value, str) and hash_value.strip():
        return hash_value.strip()
    return None
