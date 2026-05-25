"""The ASR gate: no attack in the corpus may succeed against the hardened swarm."""

from evaluation.adversarial.asr_runner import compute_asr


def test_overall_asr_is_zero():
    report = compute_asr()
    assert report["overall_asr"] == 0.0, (
        f"Attack Success Rate regressed: {report['overall_asr']}. "
        f"A defense point was weakened. See per_defense_point for the failing point."
    )
