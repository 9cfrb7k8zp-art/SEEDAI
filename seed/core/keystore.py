"""
FILE: keystore.py
PATH: seed/core/keystore.py

SEED MODULE: Identity Core
COMPONENT: Secure Key Storage & Encryption

VERSION: 0.1.1
STATUS: Stable (Foundational)
"""

import os
import json
import hashlib
import platform
import getpass
import datetime
from typing import Optional

from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import (
    ChaCha20Poly1305,
    AESGCM
)
from cryptography.hazmat.backends import default_backend


# ==========================================================
# Cipher Backend Selector
# ==========================================================
class CipherBackend:
    """
    LABEL: CIPHER_BACKEND_SELECTOR
    """

    @staticmethod
    def select() -> str:
        # Prefer ChaCha20-Poly1305 for portability and misuse resistance
        return "CHACHA20_POLY1305"


# ==========================================================
# SEED Key Store
# ==========================================================
class SeedKeyStore:
    """
    LABEL: SEED_KEYSTORE

    Encrypts and securely persists SEED private key material.
    """

    KDF_ITERATIONS = 390_000
    NONCE_SIZE = 12  # AEAD standard

    def __init__(self, storage_root: str):
        self.storage_root = storage_root
        self.storage_path = os.path.join(
            storage_root, "storage", "seed_identity.enc"
        )

        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)

    # ------------------------------------------------------
    # Device Entropy (non-identifying)
    # ------------------------------------------------------
    def _device_entropy(self) -> bytes:
        entropy_source = (
            platform.system()
            + platform.release()
            + platform.machine()
        )
        return hashlib.sha256(entropy_source.encode()).digest()

    # ------------------------------------------------------
    # Key Derivation
    # ------------------------------------------------------
    def _derive_key(self, passphrase: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=self.KDF_ITERATIONS,
            backend=default_backend(),
        )
        return kdf.derive(passphrase.encode())

    # ------------------------------------------------------
    # Encrypt & Store
    # ------------------------------------------------------
    def encrypt_and_store(self, private_key_bytes: bytes) -> dict:
        """
        Encrypts private key material and persists it securely.
        """

        # ---- Passphrase entry (verified) ----
        passphrase = getpass.getpass("Enter SEED passphrase: ")
        confirm = getpass.getpass("Confirm SEED passphrase: ")

        if passphrase != confirm:
            raise ValueError("Passphrases do not match")

        # ---- Cipher selection ----
        cipher_choice = CipherBackend.select()
        nonce = os.urandom(self.NONCE_SIZE)

        # ---- Salt derivation ----
        device_entropy = self._device_entropy()
        salt = hashlib.sha256(device_entropy + nonce).digest()

        # ---- Key derivation ----
        key = self._derive_key(passphrase, salt)

        # ---- Encrypt ----
        if cipher_choice == "CHACHA20_POLY1305":
            cipher = ChaCha20Poly1305(key)
            ciphertext = cipher.encrypt(nonce, private_key_bytes, None)

        elif cipher_choice == "AES_256_GCM":
            cipher = AESGCM(key)
            ciphertext = cipher.encrypt(nonce, private_key_bytes, None)

        else:
            raise ValueError("Unsupported cipher backend")

        # ---- Memory hygiene ----
        del passphrase
        del confirm
        del key

        # ---- Persist payload ----
        payload = {
            "label": "SEED_ENCRYPTED_IDENTITY",
            "version": "0.1.1",
            "cipher": cipher_choice,
            "kdf": "PBKDF2-HMAC-SHA256",
            "iterations": self.KDF_ITERATIONS,
            "nonce": nonce.hex(),
            "nonce_size": self.NONCE_SIZE,
            "salt": salt.hex(),
            "created_at": datetime.datetime.utcnow().isoformat() + "Z",
            "ciphertext": ciphertext.hex(),
        }

        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        return {
            "status": "stored",
            "path": self.storage_path,
            "cipher": cipher_choice,
            "version": payload["version"],
        }
