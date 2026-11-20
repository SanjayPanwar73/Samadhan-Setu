"""Attachment storage behind a small interface (local disk now, S3 later)."""

import hashlib
import os
import secrets

from app.core.config import settings
from app.core.errors import DomainError

# mime -> (extension, magic-byte prefixes)
ALLOWED = {
    "image/png": (".png", (b"\x89PNG\r\n\x1a\n",)),
    "image/jpeg": (".jpg", (b"\xff\xd8\xff",)),
    "image/webp": (".webp", (b"RIFF",)),
    "application/pdf": (".pdf", (b"%PDF-",)),
}


def sniff(content: bytes, claimed_mime: str) -> str:
    """Validate the declared type against the file's magic bytes; never trust the filename."""
    entry = ALLOWED.get((claimed_mime or "").lower())
    if entry is None:
        raise DomainError("unsupported_file", "Only PNG, JPEG, WebP images and PDFs are allowed", 415)
    if not any(content.startswith(m) for m in entry[1]):
        raise DomainError("unsupported_file", "File content does not match its declared type", 415)
    return claimed_mime.lower()


class LocalStorage:
    def __init__(self, root: str):
        self.root = os.path.abspath(root)

    def save(self, content: bytes, mime: str) -> tuple[str, str]:
        """Returns (storage_key, sha256). The key is random; user-supplied names are never used."""
        os.makedirs(self.root, exist_ok=True)
        key = secrets.token_hex(16) + ALLOWED[mime][0]
        with open(os.path.join(self.root, key), "wb") as fh:
            fh.write(content)
        return key, hashlib.sha256(content).hexdigest()

    def path(self, key: str) -> str:
        full = os.path.abspath(os.path.join(self.root, os.path.basename(key)))
        if not full.startswith(self.root + os.sep):
            raise DomainError("not_found", "File not found", 404)
        return full


def get_storage() -> LocalStorage:
    return LocalStorage(settings.UPLOAD_DIR)
