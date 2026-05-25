#!/usr/bin/env python3
"""Generate an HTML evaluation report from eval_results/.

Reads ADK eval result JSONs + JUnit XML files and produces a single
eval_report.html with drill-down links to individual result files.

Usage:
    python evaluation/generate_report.py                        # defaults
    python evaluation/generate_report.py --results-dir eval_results --out eval_results/eval_report.html
"""

import argparse
import json
import pathlib
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html import escape
from typing import Optional


# ── Status codes from ADK ────────────────────────────────────────────────────
_STATUS_LABELS = {1: "PASSED", 2: "FAILED", 3: "NOT_EVALUATED"}


@dataclass
class MetricResult:
    name: str
    threshold: Optional[float]
    score: Optional[float]
    status: str  # PASSED / FAILED / NOT_EVALUATED


@dataclass
class EvalCaseResult:
    eval_id: str
    status: str
    metrics: list[MetricResult] = field(default_factory=list)


@dataclass
class AgentEvalRun:
    agent: str
    eval_set_id: str
    file_path: str
    cases: list[EvalCaseResult] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for c in self.cases if c.status == "PASSED")

    @property
    def failed(self) -> int:
        return sum(1 for c in self.cases if c.status != "PASSED")


@dataclass
class PytestCase:
    name: str
    classname: str
    time: float
    status: str  # passed / failed / skipped / error
    message: str = ""


@dataclass
class PytestSuite:
    label: str
    file_path: str
    cases: list[PytestCase] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for c in self.cases if c.status == "passed")

    @property
    def failed(self) -> int:
        return sum(1 for c in self.cases if c.status == "failed")

    @property
    def skipped(self) -> int:
        return sum(1 for c in self.cases if c.status == "skipped")


# ── Parsing ──────────────────────────────────────────────────────────────────

def parse_adk_results(results_dir: pathlib.Path) -> list[AgentEvalRun]:
    adk_dir = results_dir / "adk_eval"
    if not adk_dir.exists():
        return []
    runs: list[AgentEvalRun] = []
    for agent_dir in sorted(adk_dir.iterdir()):
        if not agent_dir.is_dir():
            continue
        for fp in sorted(agent_dir.glob("*.json")):
            try:
                data = json.loads(fp.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            run = AgentEvalRun(
                agent=agent_dir.name,
                eval_set_id=data.get("eval_set_id", ""),
                file_path=str(fp.relative_to(results_dir)),
            )
            for case in data.get("eval_case_results", []):
                status = _STATUS_LABELS.get(case.get("final_eval_status", 3), "NOT_EVALUATED")
                metrics = []
                for m in case.get("overall_eval_metric_results") or []:
                    metrics.append(MetricResult(
                        name=m.get("metric_name", ""),
                        threshold=m.get("threshold"),
                        score=m.get("score"),
                        status=_STATUS_LABELS.get(m.get("eval_status", 3), "NOT_EVALUATED"),
                    ))
                run.cases.append(EvalCaseResult(
                    eval_id=case.get("eval_id", "unknown"),
                    status=status,
                    metrics=metrics,
                ))
            runs.append(run)
    return runs


def parse_junit_xml(xml_path: pathlib.Path, label: str) -> Optional[PytestSuite]:
    if not xml_path.exists():
        return None
    try:
        tree = ET.parse(xml_path)
    except ET.ParseError:
        return None
    suite = PytestSuite(label=label, file_path=str(xml_path.name))
    for tc in tree.iter("testcase"):
        status = "passed"
        message = ""
        if tc.find("failure") is not None:
            status = "failed"
            message = tc.find("failure").get("message", "")
        elif tc.find("error") is not None:
            status = "error"
            message = tc.find("error").get("message", "")
        elif tc.find("skipped") is not None:
            status = "skipped"
            message = tc.find("skipped").get("message", "")
        suite.cases.append(PytestCase(
            name=tc.get("name", ""),
            classname=tc.get("classname", ""),
            time=float(tc.get("time", 0)),
            status=status,
            message=message,
        ))
    return suite


# ── HTML generation ──────────────────────────────────────────────────────────

def _status_badge(status: str) -> str:
    cls = {
        "PASSED": "badge-pass", "passed": "badge-pass",
        "FAILED": "badge-fail", "failed": "badge-fail",
        "skipped": "badge-skip", "error": "badge-fail",
        "NOT_EVALUATED": "badge-skip",
    }.get(status, "badge-skip")
    return f'<span class="badge {cls}">{escape(status)}</span>'


def _score_cell(score: Optional[float], threshold: Optional[float]) -> str:
    if score is None:
        return '<td class="score">-</td>'
    passed = threshold is not None and score >= threshold
    cls = "score-pass" if passed else "score-fail"
    pct = f"{score:.1%}" if score <= 1.0 else f"{score:.2f}"
    thr = f"{threshold:.1%}" if threshold is not None and threshold <= 1.0 else (f"{threshold:.2f}" if threshold is not None else "-")
    return f'<td class="score {cls}">{pct} <span class="threshold">/ {thr}</span></td>'


def generate_html(
    adk_runs: list[AgentEvalRun],
    pytest_suites: list[PytestSuite],
) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    total_adk_cases = sum(len(r.cases) for r in adk_runs)
    total_adk_passed = sum(r.passed for r in adk_runs)
    total_pytest = sum(len(s.cases) for s in pytest_suites)
    total_pytest_passed = sum(s.passed for s in pytest_suites)
    total_pytest_failed = sum(s.failed for s in pytest_suites)
    total_pytest_skipped = sum(s.skipped for s in pytest_suites)

    agents: dict[str, list[AgentEvalRun]] = {}
    for r in adk_runs:
        agents.setdefault(r.agent, []).append(r)

    parts = [_HTML_HEAD.replace("{{TIMESTAMP}}", now)]

    # ── Summary dashboard ────────────────────────────────────────────────
    parts.append('<div class="summary-grid">')
    parts.append(_summary_card("ADK Eval Cases", total_adk_passed, total_adk_cases - total_adk_passed, 0))
    parts.append(_summary_card("Pytest Tests", total_pytest_passed, total_pytest_failed, total_pytest_skipped))
    parts.append(_summary_card("Agents Evaluated", len(agents), 0, 0, hide_pf=True))
    parts.append("</div>")

    # ── ADK eval per agent ───────────────────────────────────────────────
    parts.append('<h2>ADK Evaluation Results</h2>')
    if not agents:
        parts.append('<p class="muted">No ADK eval results found.</p>')
    for agent_name, runs in sorted(agents.items()):
        agent_passed = sum(r.passed for r in runs)
        agent_total = sum(len(r.cases) for r in runs)
        bar_pct = (agent_passed / agent_total * 100) if agent_total else 0
        parts.append(f'''
        <details class="agent-section">
          <summary>
            <span class="agent-name">{escape(agent_name)}</span>
            <span class="agent-stats">{agent_passed}/{agent_total} passed</span>
            <div class="mini-bar"><div class="mini-bar-fill" style="width:{bar_pct:.0f}%"></div></div>
          </summary>
          <div class="agent-body">''')

        for run in runs:
            rel = run.file_path
            parts.append(f'<div class="run-header">Eval set: <strong>{escape(run.eval_set_id)}</strong> &mdash; <a href="{escape(rel)}" target="_blank">raw JSON</a></div>')
            parts.append('<table class="eval-table"><thead><tr><th>Eval Case</th><th>Status</th><th>Metric</th><th>Score / Threshold</th><th>Metric Status</th></tr></thead><tbody>')
            for case in run.cases:
                if not case.metrics:
                    parts.append(f'<tr><td>{escape(case.eval_id)}</td><td>{_status_badge(case.status)}</td><td colspan="3" class="muted">No metrics</td></tr>')
                    continue
                first = True
                for m in case.metrics:
                    td_case = f'<td rowspan="{len(case.metrics)}">{escape(case.eval_id)}</td><td rowspan="{len(case.metrics)}">{_status_badge(case.status)}</td>' if first else ""
                    parts.append(f'<tr>{td_case}<td class="metric-name">{escape(m.name)}</td>{_score_cell(m.score, m.threshold)}<td>{_status_badge(m.status)}</td></tr>')
                    first = False
            parts.append("</tbody></table>")

        parts.append("</div></details>")

    # ── Pytest suites ────────────────────────────────────────────────────
    parts.append('<h2>Pytest Results</h2>')
    if not pytest_suites:
        parts.append('<p class="muted">No pytest results found.</p>')
    for suite in pytest_suites:
        s_passed = suite.passed
        s_total = len(suite.cases)
        bar_pct = (s_passed / s_total * 100) if s_total else 0
        parts.append(f'''
        <details class="agent-section">
          <summary>
            <span class="agent-name">{escape(suite.label)}</span>
            <span class="agent-stats">{s_passed}/{s_total} passed, {suite.skipped} skipped</span>
            <div class="mini-bar"><div class="mini-bar-fill" style="width:{bar_pct:.0f}%"></div></div>
          </summary>
          <div class="agent-body">
          <p class="run-header"><a href="{escape(suite.file_path)}" target="_blank">JUnit XML</a></p>
          <table class="eval-table"><thead><tr><th>Test</th><th>Class</th><th>Time</th><th>Status</th></tr></thead><tbody>''')
        for tc in suite.cases:
            parts.append(f'<tr><td>{escape(tc.name)}</td><td class="muted">{escape(tc.classname)}</td><td class="score">{tc.time:.3f}s</td><td>{_status_badge(tc.status)}</td></tr>')
        parts.append("</tbody></table></div></details>")

    parts.append("</div></body></html>")
    return "\n".join(parts)


def _summary_card(title: str, passed: int, failed: int, skipped: int, hide_pf: bool = False) -> str:
    total = passed + failed + skipped
    if hide_pf:
        body = f'<div class="card-number">{passed}</div>'
    else:
        body = f'''<div class="card-number">{total}</div>
        <div class="card-breakdown">
          <span class="card-pass">{passed} passed</span>
          <span class="card-fail">{failed} failed</span>
          {"<span class='card-skip'>" + str(skipped) + " skipped</span>" if skipped else ""}
        </div>'''
    return f'<div class="summary-card"><div class="card-title">{title}</div>{body}</div>'


_HTML_HEAD = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Swarm Agent Evaluation Report</title>
<style>
  :root {
    --coral: #E8735A;
    --beige: #F5F0E8;
    --beige-dark: #E8DFD0;
    --white: #FFFFFF;
    --text: #3D3029;
    --text-muted: #8C7E73;
    --green: #4CAF6A;
    --green-bg: #E8F5EC;
    --red: #D94F4F;
    --red-bg: #FDEDED;
    --skip-bg: #F5F0E8;
    --skip-text: #8C7E73;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    background: var(--beige);
    color: var(--text);
    line-height: 1.5;
  }
  .container {
    max-width: 1100px;
    margin: 0 auto;
    padding: 2rem 1.5rem 4rem;
  }
  header {
    background: var(--coral);
    color: var(--white);
    padding: 2rem 0;
    margin-bottom: 2rem;
  }
  header .container { padding-top: 0; padding-bottom: 0; }
  header h1 { font-size: 1.75rem; font-weight: 700; }
  header .timestamp { opacity: 0.85; font-size: 0.9rem; margin-top: 0.25rem; }

  /* Summary cards */
  .summary-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 1rem;
    margin-bottom: 2rem;
  }
  .summary-card {
    background: var(--white);
    border-radius: 10px;
    padding: 1.25rem 1.5rem;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  }
  .card-title { font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--text-muted); margin-bottom: 0.5rem; }
  .card-number { font-size: 2rem; font-weight: 700; color: var(--coral); }
  .card-breakdown { display: flex; gap: 0.75rem; margin-top: 0.35rem; font-size: 0.85rem; }
  .card-pass { color: var(--green); }
  .card-fail { color: var(--red); }
  .card-skip { color: var(--text-muted); }

  h2 { font-size: 1.25rem; margin: 2rem 0 1rem; color: var(--text); }

  /* Agent accordion */
  .agent-section {
    background: var(--white);
    border-radius: 10px;
    margin-bottom: 0.75rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    overflow: hidden;
  }
  .agent-section summary {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 1rem 1.25rem;
    cursor: pointer;
    user-select: none;
    list-style: none;
    font-size: 0.95rem;
  }
  .agent-section summary::-webkit-details-marker { display: none; }
  .agent-section summary::before {
    content: "▸";
    font-size: 0.85rem;
    color: var(--coral);
    transition: transform 0.2s;
  }
  .agent-section[open] summary::before { transform: rotate(90deg); }
  .agent-name { font-weight: 600; }
  .agent-stats { color: var(--text-muted); font-size: 0.85rem; }
  .mini-bar {
    flex: 1;
    max-width: 160px;
    height: 6px;
    background: var(--beige);
    border-radius: 3px;
    overflow: hidden;
  }
  .mini-bar-fill { height: 100%; background: var(--green); border-radius: 3px; }
  .agent-body { padding: 0 1.25rem 1.25rem; }
  .run-header { font-size: 0.85rem; color: var(--text-muted); margin-bottom: 0.75rem; }
  .run-header a { color: var(--coral); }

  /* Tables */
  .eval-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; margin-bottom: 1rem; }
  .eval-table th {
    text-align: left;
    padding: 0.5rem 0.75rem;
    background: var(--beige);
    color: var(--text-muted);
    font-weight: 600;
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    border-bottom: 2px solid var(--beige-dark);
  }
  .eval-table td {
    padding: 0.5rem 0.75rem;
    border-bottom: 1px solid var(--beige);
    vertical-align: middle;
  }
  .eval-table tr:last-child td { border-bottom: none; }
  .metric-name { font-family: "SF Mono", Monaco, Consolas, monospace; font-size: 0.8rem; }
  .score { font-family: "SF Mono", Monaco, Consolas, monospace; }
  .score-pass { color: var(--green); }
  .score-fail { color: var(--red); }
  .threshold { color: var(--text-muted); font-size: 0.8em; }
  .muted { color: var(--text-muted); }

  /* Badges */
  .badge {
    display: inline-block;
    padding: 0.15em 0.6em;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }
  .badge-pass { background: var(--green-bg); color: var(--green); }
  .badge-fail { background: var(--red-bg); color: var(--red); }
  .badge-skip { background: var(--skip-bg); color: var(--skip-text); }
</style>
</head>
<body>
<header>
  <div class="container">
    <h1>Swarm Agent Evaluation Report</h1>
    <div class="timestamp">Generated {{TIMESTAMP}}</div>
  </div>
</header>
<div class="container">
'''


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate HTML evaluation report.")
    parser.add_argument("--results-dir", default="eval_results", help="Path to eval_results directory")
    parser.add_argument("--out", default=None, help="Output HTML path (default: <results-dir>/eval_report.html)")
    args = parser.parse_args()

    results_dir = pathlib.Path(args.results_dir)
    out_path = pathlib.Path(args.out) if args.out else results_dir / "eval_report.html"

    adk_runs = parse_adk_results(results_dir)

    pytest_suites = []
    for xml_name, label in [
        ("unit_tests.xml", "Unit Tests"),
        ("integration_tests.xml", "Integration Tests"),
        ("adversarial_tests.xml", "Adversarial Tests"),
        ("trace_tests.xml", "Trace Quality Tests"),
    ]:
        suite = parse_junit_xml(results_dir / xml_name, label)
        if suite:
            pytest_suites.append(suite)

    html = generate_html(adk_runs, pytest_suites)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"Report written to {out_path}")


if __name__ == "__main__":
    main()
