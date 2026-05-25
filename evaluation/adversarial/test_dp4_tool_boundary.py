"""DP4 tool boundary: cast_vote validation rejects bad input, no silent coercion.

An unknown verdict or an out of range confidence must raise, so a misbehaving
agent shows up as an error in telemetry rather than a quiet VERIFY_FURTHER.
"""

import pytest

from evaluation.adversarial.asr_runner import attacks_for, run_attack
from shared.vote_vocabulary import validate_specialist_vote

ATTACKS = attacks_for("DP4")


@pytest.mark.parametrize("attack", ATTACKS, ids=[a["id"] for a in ATTACKS])
def test_invalid_vote_raises(attack):
    assert run_attack(attack), f"{attack['id']} was coerced, not rejected: {attack['name']}"


def test_valid_vote_passes():
    assert validate_specialist_vote("AUTHENTICATE", 0.8) == "AUTHENTICATE"
    assert validate_specialist_vote("buy", 0.5) == "AUTHENTICATE"
