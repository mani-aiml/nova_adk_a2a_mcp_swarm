"""DP3 inter agent channel: only a correctly signed vote block verifies.

Unsigned, attacker signed, replayed, and tampered blocks must all fail
verification. A block signed by a real specialist for this request must pass.
"""

import pytest

from evaluation.adversarial.asr_runner import _REAL_KEY, attacks_for, run_attack
from shared.vote_channel import sign, verify

ATTACKS = attacks_for("DP3")


@pytest.mark.parametrize("attack", ATTACKS, ids=[a["id"] for a in ATTACKS])
def test_forged_block_is_rejected(attack):
    assert run_attack(attack), f"{attack['id']} verified as genuine: {attack['name']}"


def test_genuine_block_verifies():
    block = sign("vote: REJECT\nconfidence: 0.9", "req-001", _REAL_KEY)
    assert verify(block, "req-001", _REAL_KEY)
