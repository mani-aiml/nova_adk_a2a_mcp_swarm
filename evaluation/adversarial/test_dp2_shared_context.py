"""DP2 fan out and shared context: the canary must flag instruction-like input.

One poisoned description reaches every specialist at once. The canary flags it
before it fans out, so a real description must not trip a false positive.
"""

import pytest

from evaluation.adversarial.asr_runner import attacks_for, run_attack
from shared.input_guard import looks_like_injection

ATTACKS = attacks_for("DP2")


@pytest.mark.parametrize("attack", ATTACKS, ids=[a["id"] for a in ATTACKS])
def test_attack_is_flagged(attack):
    assert run_attack(attack), f"{attack['id']} slipped past the canary: {attack['name']}"


def test_genuine_description_not_flagged():
    assert not looks_like_injection("Appraise a Monet, oil on canvas, painted in 1906.")
