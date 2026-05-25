"""DP1 and DP2 defenses: quarantine untrusted input and flag injection attempts.

quarantine() strips the swarm's reserved vote markers and wraps the text so an
agent reads it as data, not instructions. looks_like_injection() is the DP2
canary that flags an input which reads like a command before it fans out.
"""

from __future__ import annotations

import re

# Structural markers the swarm parses. A real artwork description never contains them.
_RESERVED = re.compile(r"-{2,}\s*(?:SPECIALIST_VOTE|END_VOTE)\s*-{2,}", re.IGNORECASE)

_INJECTION_SIGNS = (
    re.compile(r"ignore\s+(?:all\s+)?(?:previous|above|prior)\s+instruction", re.IGNORECASE),
    re.compile(r"(?:^|\n)\s*(?:system|assistant)\s*:", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\b", re.IGNORECASE),
    re.compile(r"\bvote\s*:\s*(?:AUTHENTICATE|VERIFY_FURTHER|REJECT|BUY|HOLD)\b", re.IGNORECASE),
    _RESERVED,
)


def quarantine(text: str) -> str:
    """Strip reserved markers and wrap the input so agents treat it as data only."""
    cleaned = _RESERVED.sub(" ", text or "").strip()
    return f"<artwork_description>\n{cleaned}\n</artwork_description>"


def looks_like_injection(text: str) -> bool:
    """DP2 canary: True when the input reads like an instruction, not a description."""
    return any(pattern.search(text or "") for pattern in _INJECTION_SIGNS)
