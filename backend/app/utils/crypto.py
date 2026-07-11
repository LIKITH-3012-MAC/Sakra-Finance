"""
Cryptographic utilities for Aadhaar data protection.

- AES-256-GCM encryption/decryption for storing Aadhaar numbers securely.
- SHA-256 hashing with salt for indexed lookups.
"""

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings


def _get_aes_key() -> bytes:
    """Decode the base64-encoded AES-256 key from settings."""
    return base64.b64decode(settings.AES_ENCRYPTION_KEY)


def encrypt_aadhaar(aadhaar: str) -> str:
    """
    Encrypt an Aadhaar number using AES-256-GCM.

    The 12-byte nonce is prepended to the ciphertext (which includes the
    16-byte GCM authentication tag). The combined result is base64-encoded.

    Args:
        aadhaar: The plaintext Aadhaar number.

    Returns:
        Base64-encoded string of (nonce + ciphertext + tag).
    """
    key = _get_aes_key()
    nonce = os.urandom(12)  # 96-bit nonce for GCM

    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, aadhaar.encode("utf-8"), None)

    # Prepend nonce to ciphertext for storage
    return base64.b64encode(nonce + ciphertext).decode("utf-8")


def decrypt_aadhaar(encrypted: str) -> str:
    """
    Decrypt an AES-256-GCM encrypted Aadhaar number.

    Expects the input to be a base64-encoded string of (nonce + ciphertext + tag).

    Args:
        encrypted: The base64-encoded encrypted Aadhaar string.

    Returns:
        The decrypted plaintext Aadhaar number.
    """
    key = _get_aes_key()
    raw = base64.b64decode(encrypted)

    nonce = raw[:12]
    ciphertext = raw[12:]

    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)

    return plaintext.decode("utf-8")


def hash_aadhaar(aadhaar: str) -> str:
    """
    Hash an Aadhaar number using SHA-256 with a salt for indexed lookups.

    Args:
        aadhaar: The plaintext Aadhaar number.

    Returns:
        The hex-encoded SHA-256 hash.
    """
    salted = f"{settings.AADHAAR_SALT}{aadhaar}"
    return hashlib.sha256(salted.encode("utf-8")).hexdigest()
