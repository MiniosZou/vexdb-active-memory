from __future__ import annotations

import hashlib
import re

_SPACE_RE = re.compile(r"\s+")


def canonicalize(text: str) -> str:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("content must be a non-empty string")
    return _SPACE_RE.sub(" ", text.strip()).lower()


def content_hash(canonical_text: str) -> str:
    return hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()


def advisory_lock_key(*parts: str) -> int:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
    value = int.from_bytes(digest[:8], byteorder="big", signed=False)
    if value >= 2**63:
        value -= 2**64
    return value

