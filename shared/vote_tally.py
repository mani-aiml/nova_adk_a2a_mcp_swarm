"""DP5 defense: deterministic vote extraction and tally.

The aggregator must be code, not a language model that can be instructed. This
module finds vote blocks by structure and counts them. Extra or missing ballots
raise TallyError instead of silently changing the verdict.
"""

from __future__ import annotations

import math
import re

from shared.vote_vocabulary import normalize_specialist_vote

_BLOCK = re.compile(r"-{2,}SPECIALIST_VOTE-{2,}(.*?)-{2,}END_VOTE-{2,}", re.DOTALL | re.IGNORECASE)
_FIELD = re.compile(r"^\s*(\w+)\s*:\s*(.+?)\s*$", re.MULTILINE)


class TallyError(ValueError):
    """Raised when the vote set fails an integrity check."""


def _confidence(raw: str) -> float:
    try:
        return min(1.0, max(0.0, float(raw)))
    except (TypeError, ValueError):
        return 0.0


def extract_votes(text: str) -> list[dict]:
    """Parse every reserved vote block. Free text outside a block is ignored."""
    votes = []
    for body in _BLOCK.findall(text or ""):
        fields = {k.lower(): v for k, v in _FIELD.findall(body)}
        votes.append({
            "vote": normalize_specialist_vote(fields.get("vote", "")),
            "confidence": _confidence(fields.get("confidence", "0")),
        })
    return votes


def decide(votes: list[dict], n_specialists: int) -> dict:
    """Majority verdict. A tally without exactly N votes is rejected."""
    if len(votes) != n_specialists:
        raise TallyError(f"expected {n_specialists} votes, found {len(votes)}")
    counts: dict[str, int] = {}
    for vote in votes:
        counts[vote["vote"]] = counts.get(vote["vote"], 0) + 1
    leader = max(counts, key=counts.get)
    if counts[leader] >= math.ceil(n_specialists / 2):
        return {"verdict": leader, "counts": counts}
    best = max(v["confidence"] for v in votes)
    top = [v for v in votes if v["confidence"] == best]
    verdict = top[0]["vote"] if len(top) == 1 else "VERIFY_FURTHER"
    return {"verdict": verdict, "counts": counts}
