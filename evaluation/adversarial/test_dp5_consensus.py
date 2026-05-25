"""DP5 aggregation and consensus: the deterministic tally cannot be bent.

Extra or missing ballots are rejected, an instruction aimed at the aggregator
is ignored, and an out of range confidence is clamped. An honest majority of
exactly N votes still produces the correct verdict.
"""

import pytest

from evaluation.adversarial.asr_runner import _vote_block, attacks_for, run_attack
from shared.vote_tally import decide, extract_votes

ATTACKS = attacks_for("DP5")


@pytest.mark.parametrize("attack", ATTACKS, ids=[a["id"] for a in ATTACKS])
def test_attack_does_not_bend_the_tally(attack):
    assert run_attack(attack), f"{attack['id']} bent the verdict: {attack['name']}"


def test_honest_majority_is_counted():
    text = "\n".join(_vote_block(v, c) for v, c in
                      [("AUTHENTICATE", 0.9), ("AUTHENTICATE", 0.8), ("REJECT", 0.7)])
    assert decide(extract_votes(text), 3)["verdict"] == "AUTHENTICATE"
