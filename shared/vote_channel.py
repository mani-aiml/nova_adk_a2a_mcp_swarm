"""DP3 defense: sign specialist vote blocks so the channel cannot be forged.

A vote block is plain text, so the receiver must verify origin and not just
format. Each block carries an HMAC tag bound to a per-request nonce, which also
blocks a valid block being replayed into a later appraisal.
"""

from __future__ import annotations

import hmac
import re
from hashlib import sha256

_SIG = re.compile(r"\nsig:\s*([0-9a-f]{64})\s*$", re.IGNORECASE)


def _digest(body: str, nonce: str, key: bytes) -> str:
    return hmac.new(key, f"{nonce}\n{body}".encode(), sha256).hexdigest()


def sign(body: str, nonce: str, key: bytes) -> str:
    """Return the vote body with a sig line bound to this nonce and key."""
    clean = body.rstrip()
    return f"{clean}\nsig: {_digest(clean, nonce, key)}"


def verify(block: str, nonce: str, key: bytes) -> bool:
    """True only when the block carries a valid HMAC for this nonce and key."""
    match = _SIG.search(block or "")
    if not match:
        return False
    body = (block or "")[: match.start()].rstrip()
    return hmac.compare_digest(match.group(1).lower(), _digest(body, nonce, key))
