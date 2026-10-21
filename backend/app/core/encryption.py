import base64
import hashlib

from cryptography.fernet import Fernet

from app.config import settings


def _fernet() -> Fernet:
    """Derives a valid 32-byte Fernet key from settings.encryption_key — the config value
    itself just needs to be a long random secret, not literally Fernet-formatted already."""
    digest = hashlib.sha256(settings.encryption_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(value: str) -> str:
    """Reversible encryption for secrets the app must decrypt and reuse (e.g. Plaid's
    access_token) — never for secrets that only ever need verification, see hash_token."""
    return _fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    return _fernet().decrypt(value.encode()).decode()
