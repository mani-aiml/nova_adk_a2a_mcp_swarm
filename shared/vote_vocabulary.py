"""Canonical specialist and synthesis vote labels (single vocabulary for runtime + tests)."""

from __future__ import annotations

# Used by cast_vote (MCP), specialist prompts, synthesis tally, and evaluation asserts.
CANONICAL_VOTES: frozenset[str] = frozenset({"AUTHENTICATE", "VERIFY_FURTHER", "REJECT"})

# Legacy specialist prompts may still send these; they normalize to CANONICAL_VOTES.
LEGACY_VOTE_INPUTS: frozenset[str] = frozenset({"BUY", "HOLD"})

_LEGACY_ALIASES: dict[str, str] = {
    "BUY": "AUTHENTICATE",
    "HOLD": "VERIFY_FURTHER",
}


def normalize_specialist_vote(recommendation: str) -> str:
    """Return a member of CANONICAL_VOTES; unknown values become VERIFY_FURTHER."""
    raw = (recommendation or "").strip().upper()
    if raw in CANONICAL_VOTES:
        return raw
    if raw in _LEGACY_ALIASES:
        return _LEGACY_ALIASES[raw]
    return "VERIFY_FURTHER"


def validate_specialist_vote(recommendation: str, confidence: float) -> str:
    """Strict DP4 check: raise on invalid input instead of silently coercing.

    cast_vote calls this so a bad value surfaces as an error in telemetry
    rather than a quiet VERIFY_FURTHER nobody reviews.
    """
    raw = (recommendation or "").strip().upper()
    if raw not in CANONICAL_VOTES and raw not in LEGACY_VOTE_INPUTS:
        raise ValueError(f"invalid recommendation: {recommendation!r}")
    try:
        score = float(confidence)
    except (TypeError, ValueError):
        raise ValueError(f"confidence is not numeric: {confidence!r}")
    if not 0.0 <= score <= 1.0:
        raise ValueError(f"confidence out of range [0.0, 1.0]: {score}")
    return normalize_specialist_vote(raw)
