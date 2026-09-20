# ==========================================================
# FILE: auto_ssl_manager.py
# PATH: SEED_ROOT/seed/core/ssl/auto_ssl_manager.py
# PURPOSE: Self-healing SSL manager for SEED IPC
# ==========================================================

import os
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa
import datetime
import logging
import re

logger = logging.getLogger("AutoSSL")
logger.setLevel(logging.INFO)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
CERT_DIR = os.path.join(BASE_DIR, "certs")
IPC_SERVER_PATH = os.path.join(BASE_DIR, "seed", "ipc", "ipc_server.py")

SERVER_KEY_FILE = os.path.join(CERT_DIR, "server.key")
SERVER_CERT_FILE = os.path.join(CERT_DIR, "server.crt")
CLIENT_CA_KEY_FILE = os.path.join(CERT_DIR, "client_ca.key")
CLIENT_CA_CERT_FILE = os.path.join(CERT_DIR, "client_ca.crt")

os.makedirs(CERT_DIR, exist_ok=True)


# -------------------------
# Key / Cert helpers
# -------------------------
def generate_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def write_key(key, path):
    with open(path, "wb") as f:
        f.write(
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )


def generate_cert(key, common_name, is_ca=False):
    now = datetime.datetime.now(datetime.timezone.utc)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "CT"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "Bloomfield"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Central Connect LLC"),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ]
    )
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=3650))
    )

    if is_ca:
        builder = builder.add_extension(
            x509.BasicConstraints(ca=True, path_length=None), critical=True
        )
    else:
        builder = builder.add_extension(
            x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False
        )

    return builder.sign(key, hashes.SHA256())


# -------------------------
# Generate missing files
# -------------------------
def ensure_ssl_files():
    changed = False

    def valid_file(path):
        return os.path.isfile(path) and os.path.getsize(path) > 0

    if not valid_file(SERVER_KEY_FILE) or not valid_file(SERVER_CERT_FILE):
        logger.info("Generating server key + certificate...")
        server_key = generate_key()
        write_key(server_key, SERVER_KEY_FILE)
        server_cert = generate_cert(server_key, "localhost", is_ca=False)
        with open(SERVER_CERT_FILE, "wb") as f:
            f.write(server_cert.public_bytes(serialization.Encoding.PEM))
        changed = True

    if not valid_file(CLIENT_CA_KEY_FILE) or not valid_file(CLIENT_CA_CERT_FILE):
        logger.info("Generating client CA key + certificate...")
        ca_key = generate_key()
        write_key(ca_key, CLIENT_CA_KEY_FILE)
        ca_cert = generate_cert(ca_key, "SEED Client CA", is_ca=True)
        with open(CLIENT_CA_CERT_FILE, "wb") as f:
            f.write(ca_cert.public_bytes(serialization.Encoding.PEM))
        changed = True

    return changed


# -------------------------
# Update ipc_server.py paths (Windows-safe, UTF-8)
# -------------------------
def update_ipc_server_paths():
    if not os.path.exists(IPC_SERVER_PATH):
        logger.warning("ipc_server.py not found, skipping path update.")
        return

    # <-- force UTF-8 to avoid Windows decode errors
    with open(IPC_SERVER_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    def replace(var_name, file_path, text):
        # Safely replace a variable assignment with an absolute Windows path.
        pattern = rf"^\s*{re.escape(var_name)}\s*=.*$"
        safe_path = file_path.replace("\\", "\\\\")
        replacement = f'{var_name} = r"{safe_path}"'
        return re.sub(pattern, replacement, text, flags=re.MULTILINE)

    original = content
    content = replace("server.crt", SERVER_CERT_FILE, content)
    content = replace("server.key", SERVER_KEY_FILE, content)
    content = replace("client_ca.crt", CLIENT_CA_CERT_FILE, content)

    if content != original:
        with open(IPC_SERVER_PATH, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info("ipc_server.py SSL paths updated to absolute paths.")
    else:
        logger.debug("ipc_server.py already uses its current SSL configuration.")


# -------------------------
# Accessor functions for ipc_server
# -------------------------
def get_server_paths():
    return SERVER_CERT_FILE, SERVER_KEY_FILE


def get_client_ca_path():
    return CLIENT_CA_CERT_FILE


# -------------------------
# Auto-run
# -------------------------
def run():
    changed = ensure_ssl_files()
    update_ipc_server_paths()
    if changed:
        logger.info("SSL files generated or verified.")
    else:
        logger.info("SSL files already exist and are present.")


# -------------------------
# Allow running as script
# -------------------------
if __name__ == "__main__":
    run()
