import base64
import hashlib
import hmac
import json
import os
from typing import Optional


_STATE_LABEL = b"moneymap-state-v1"
_KDF_ITERATIONS = 200_000
_NONCE_SIZE = 16


def _b64encode(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.b64decode(value.encode("ascii"))


def _derive_key(secret: str) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256",
        secret.encode("utf-8"),
        _STATE_LABEL,
        _KDF_ITERATIONS,
        dklen=32,
    )


def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        block = hmac.new(key, nonce + counter.to_bytes(4, "big"), hashlib.sha256).digest()
        out.extend(block)
        counter += 1
    return bytes(out[:length])


def _xor_bytes(left: bytes, right: bytes) -> bytes:
    return bytes(a ^ b for a, b in zip(left, right))


def encrypt_json(data: dict, secret: str) -> str:
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    nonce = os.urandom(_NONCE_SIZE)
    key = _derive_key(secret)
    stream = _keystream(key, nonce, len(raw))
    ciphertext = _xor_bytes(raw, stream)
    tag = hmac.new(key, _STATE_LABEL + nonce + ciphertext, hashlib.sha256).digest()
    envelope = {
        "_enc": "moneymap.v1",
        "nonce": _b64encode(nonce),
        "ciphertext": _b64encode(ciphertext),
        "tag": _b64encode(tag),
    }
    return json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))


def decrypt_json(payload: str, secret: str) -> Optional[dict]:
    try:
        envelope = json.loads(payload)
    except Exception:
        return None

    if not isinstance(envelope, dict) or envelope.get("_enc") != "moneymap.v1":
        return None

    try:
        nonce = _b64decode(envelope["nonce"])
        ciphertext = _b64decode(envelope["ciphertext"])
        expected_tag = _b64decode(envelope["tag"])
    except Exception:
        return None

    key = _derive_key(secret)
    actual_tag = hmac.new(key, _STATE_LABEL + nonce + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(expected_tag, actual_tag):
        return None

    raw = _xor_bytes(ciphertext, _keystream(key, nonce, len(ciphertext)))
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None
