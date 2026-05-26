import base64
import hashlib
import hmac
import secrets
from typing import Optional

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError


_PBKDF2_DEFAULT_ITERATIONS = 240_000
_PBKDF2_DKLEN = 32
_ARGON2_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=64 * 1024,
    parallelism=2,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)


def create_password_record(password: str) -> dict:
    return {
        "v": 2,
        "algo": "argon2id",
        "hash": _ARGON2_HASHER.hash(password),
    }


def create_pbkdf2_password_record(password: str, iterations: int = _PBKDF2_DEFAULT_ITERATIONS) -> dict:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, dklen=_PBKDF2_DKLEN)
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

    if record.get("algo") == "argon2id":
        try:
            return _ARGON2_HASHER.verify(str(record.get("hash") or ""), password)
        except (InvalidHashError, VerificationError, TypeError, ValueError):
            return False

    if record.get("algo") == "pbkdf2_sha256":
        return _verify_pbkdf2_password(password, record)

    return False


def password_needs_rehash(record: dict) -> bool:
    if not isinstance(record, dict):
        return True
    if record.get("algo") != "argon2id":
        return True
    try:
        return _ARGON2_HASHER.check_needs_rehash(str(record.get("hash") or ""))
    except (InvalidHashError, TypeError, ValueError):
        return True


def _verify_pbkdf2_password(password: str, record: dict) -> bool:
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
