"""DP1 input boundary: an injected description must not smuggle a ballot.

Each attack embeds the swarm's reserved markers in the artwork description.
quarantine() must strip them so a downstream parser cannot read a forged vote.
"""

import pytest

from evaluation.adversarial.asr_runner import attacks_for, run_attack
from shared.input_guard import quarantine

ATTACKS = attacks_for("DP1")


@pytest.mark.parametrize("attack", ATTACKS, ids=[a["id"] for a in ATTACKS])
def test_attack_is_blocked(attack):
    assert run_attack(attack), f"{attack['id']} not blocked: {attack['name']}"


def test_clean_description_survives_quarantine():
    text = "Monet Water Lilies, oil on canvas, 1906, good condition."
    assert "Water Lilies" in quarantine(text)
