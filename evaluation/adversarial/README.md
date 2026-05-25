# Adversarial Suite (Part 3): Red Teaming the Swarm

Tier E of the [evaluation pyramid](../README.md). It red teams the swarm at the
five **defense points** that exist in any multi-agent system. The point is the
mental model: walk each defense point, ask what an adversary does there, and
write a test module for it. The art appraisal swarm is the worked example.

## The five defense points

| Module | Defense point | Threat | Defense exercised |
|--------|---------------|--------|-------------------|
| `test_dp1_input_boundary.py` | Input boundary | Prompt injection in the artwork description | `shared/input_guard.quarantine` |
| `test_dp2_shared_context.py` | Fan out / shared context | One injection reaches every specialist | `shared/input_guard.looks_like_injection` |
| `test_dp3_message_channel.py` | Inter-agent channel | Forged or replayed vote blocks | `shared/vote_channel` (HMAC) |
| `test_dp4_tool_boundary.py` | Tool boundary | Tool poisoning, silent coercion | `shared/vote_vocabulary.validate_specialist_vote` |
| `test_dp5_consensus.py` | Aggregation / consensus | Extra ballots, tiebreaker abuse, aggregator instructions | `shared/vote_tally` |

## Threat model

Scope is adversarial **behavior**, not access. The attacker has no credentials
they were not given; they submit an artwork description, the one input the
product hands them. Authentication, rate limiting, and network isolation are
Part 4. Untrusted surfaces: the artwork description, MCP tool results, and A2A
responses. Trusted: system prompts, `agents.yaml`, the voting rules.

## Attack Success Rate

`attacks/corpus.json` holds the attack corpus, grouped by defense point.
`asr_runner.py` runs every attack against its defense and reports **Attack
Success Rate (ASR)**, the share of attacks that are not blocked. CI fails when
ASR exceeds `adversarial.asr_threshold` in `../test_config.json` (default 0.0).

```bash
pytest evaluation/adversarial -v                  # one assertion per attack
python evaluation/adversarial/asr_runner.py        # ASR per defense point + gate
```

The suite is deterministic and needs no LLM, Docker, or API key. It exercises
the defense modules directly, so it runs on every pull request.

## Extending it for your own system

Keep the five test modules. Replace the payloads in `attacks/corpus.json` with
attacks shaped by your own architecture. Each attack is a data record with a
`defense_point` and a payload; `asr_runner.py` dispatches it to the matching
defense. New defense point in your system means a new module here.
