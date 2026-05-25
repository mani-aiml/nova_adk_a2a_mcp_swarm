#!/usr/bin/env python3
"""Attack Success Rate (ASR) runner for the adversarial suite.

Runs every attack in attacks/corpus.json against the matching defense and
reports ASR per defense point. ASR is the share of attacks that are NOT
blocked. CI fails when ASR rises above the threshold in test_config.json.

Usage:
    python evaluation/adversarial/asr_runner.py
    python evaluation/adversarial/asr_runner.py --results-dir eval_results
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

ADV_DIR = pathlib.Path(__file__).resolve().parent
ROOT = ADV_DIR.parent.parent
sys.path.insert(0, str(ROOT))  # allow running as a script, not only under pytest

from shared.input_guard import looks_like_injection, quarantine  # noqa: E402
from shared.vote_channel import sign, verify  # noqa: E402
from shared.vote_tally import TallyError, decide, extract_votes  # noqa: E402
from shared.vote_vocabulary import validate_specialist_vote  # noqa: E402

CORPUS = ADV_DIR / "attacks" / "corpus.json"
CONFIG = ROOT / "evaluation" / "test_config.json"
DEFENSE_POINTS = ("DP1", "DP2", "DP3", "DP4", "DP5")

# Demo keys. In production these live in a secret store, not in source (Part 4).
_REAL_KEY = b"specialist-signing-key-demo"
_ATTACKER_KEY = b"attacker-controlled-key"


def load_corpus() -> list[dict]:
    with CORPUS.open(encoding="utf-8") as f:
        return json.load(f)["attacks"]


def attacks_for(defense_point: str) -> list[dict]:
    return [a for a in load_corpus() if a["defense_point"] == defense_point]


def _vote_block(vote: str, confidence) -> str:
    return (f"---SPECIALIST_VOTE---\nvote: {vote}\nconfidence: {confidence}\n"
            f"reason_1: test\nreason_2: test\n---END_VOTE---")


def _blocked_dp1(attack: dict) -> bool:
    cleaned = quarantine(attack["payload"]).upper()
    return "SPECIALIST_VOTE" not in cleaned and "END_VOTE" not in cleaned


def _blocked_dp2(attack: dict) -> bool:
    return looks_like_injection(attack["payload"])


def _blocked_dp3(attack: dict) -> bool:
    body = attack["block"]
    if attack["signed_by"] == "none":
        block = body
    elif attack["signed_by"] == "attacker":
        block = sign(body, attack["sign_nonce"], _ATTACKER_KEY)
    else:
        block = sign(body, attack["sign_nonce"], _REAL_KEY)
    if "tamper" in attack:
        block = block.replace(body, attack["tamper"])
    return not verify(block, attack["verify_nonce"], _REAL_KEY)


def _blocked_dp4(attack: dict) -> bool:
    try:
        validate_specialist_vote(attack["recommendation"], attack["confidence"])
        return False
    except ValueError:
        return True


def _blocked_dp5(attack: dict) -> bool:
    text = "\n".join(_vote_block(v, c) for v, c in attack["votes"])
    if attack.get("trailing"):
        text += "\n" + attack["trailing"]
    votes = extract_votes(text)
    if attack["mode"] == "confidence":
        return all(v["confidence"] <= 1.0 for v in votes)
    if attack["mode"] == "count":
        try:
            decide(votes, attack["n_specialists"])
            return False
        except TallyError:
            return True
    return decide(votes, attack["n_specialists"])["verdict"] == attack["honest_verdict"]


_HANDLERS = {"DP1": _blocked_dp1, "DP2": _blocked_dp2, "DP3": _blocked_dp3,
             "DP4": _blocked_dp4, "DP5": _blocked_dp5}


def run_attack(attack: dict) -> bool:
    """True when the defense blocks the attack."""
    return _HANDLERS[attack["defense_point"]](attack)


def compute_asr() -> dict:
    corpus = load_corpus()
    per_dp = {}
    for dp in DEFENSE_POINTS:
        items = [a for a in corpus if a["defense_point"] == dp]
        unblocked = [a["id"] for a in items if not run_attack(a)]
        per_dp[dp] = {
            "attacks": len(items),
            "succeeded": len(unblocked),
            "asr": round(len(unblocked) / len(items), 3) if items else 0.0,
            "unblocked": unblocked,
        }
    succeeded = sum(d["succeeded"] for d in per_dp.values())
    return {
        "per_defense_point": per_dp,
        "total_attacks": len(corpus),
        "overall_asr": round(succeeded / len(corpus), 3) if corpus else 0.0,
    }


def _threshold() -> float:
    try:
        with CONFIG.open(encoding="utf-8") as f:
            return float(json.load(f).get("adversarial", {}).get("asr_threshold", 0.0))
    except (OSError, ValueError):
        return 0.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", default=str(ROOT / "eval_results"))
    args = parser.parse_args()

    report = compute_asr()
    threshold = _threshold()
    print("\n  Adversarial suite: attacks blocked by defense point")
    print("  ASR = Attack Success Rate, the share of attacks that got through.")
    print(f"  {'-' * 62}")
    for dp, data in report["per_defense_point"].items():
        blocked = data["attacks"] - data["succeeded"]
        flag = "" if data["asr"] <= threshold else "   <-- REGRESSION"
        print(f"  {dp}   {data['attacks']} attacks   {blocked} blocked   "
              f"{data['succeeded']} got through   ASR {data['asr']:.3f}{flag}")
    print(f"  {'-' * 62}")
    verdict = "all attacks blocked" if report["overall_asr"] <= threshold else "REGRESSION"
    print(f"  Overall ASR {report['overall_asr']:.3f}   "
          f"(threshold {threshold:.3f})   {verdict}\n")

    out_dir = pathlib.Path(args.results_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "adversarial_asr.json").write_text(json.dumps(report, indent=2))

    return 0 if report["overall_asr"] <= threshold else 1


if __name__ == "__main__":
    raise SystemExit(main())
