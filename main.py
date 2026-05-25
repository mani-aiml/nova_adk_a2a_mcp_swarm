import asyncio
import logging
import os
import sys
import time

os.environ.setdefault("OTEL_SERVICE_NAME", "art-appraisal-cli")

from shared.config import bootstrap
bootstrap()

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from opentelemetry import trace

from orchestrator.agent import art_appraisal_pipeline
from otel_setup import setup_otel_logging, otel_log, OTEL_LOG_PATH
from shared.registry import SPECIALISTS, SPECIALIST_NAMES, SYNTHESIS
from shared.input_guard import quarantine
from display import (
    C, agent_label, colored_label, banner, ruler,
    print_agent_start, print_handoff, print_intermediate,
    print_parallel_start, print_parallel_agent_active, print_parallel_complete,
)

tracer = trace.get_tracer(__name__)
otel_logger = setup_otel_logging(
    service_name=os.environ.get("OTEL_SERVICE_NAME", "art-appraisal-cli"),
)

APP_NAME = "art_appraisal_swarm"
USER_ID = "learner_001"
session_service = InMemorySessionService()


def extract_parts(event):
    texts, calls, responses = [], [], []
    if not (event.content and event.content.parts):
        return texts, calls, responses
    for part in event.content.parts:
        if getattr(part, "function_call", None):
            calls.append(part.function_call)
        elif getattr(part, "function_response", None):
            responses.append(part.function_response)
        elif getattr(part, "text", None):
            texts.append(part.text)
    return texts, calls, responses


def _process_event(
    event,
    author: str,
    state: dict,
) -> None:
    prev = state["prev_author"]
    texts, fn_calls, fn_responses = extract_parts(event)

    if state.get("ttft_ms") is None and texts and any(t.strip() for t in texts):
        ttft_ms = (time.perf_counter() - state["t_request_start"]) * 1000.0
        state["ttft_ms"] = ttft_ms
        span = trace.get_current_span()
        if span.is_recording():
            span.set_attribute("app.ttft_ms", round(ttft_ms, 2))
            span.add_event("first_model_text", {"ttft_ms": round(ttft_ms, 2)})

    if author != prev and prev in SPECIALIST_NAMES:
        if prev not in state["specialist_texts"]:
            buffered = "\n".join(state["specialist_buffers"].get(prev, []))
            if buffered:
                state["specialist_texts"][prev] = buffered
                otel_log(otel_logger, logging.INFO, "Specialist report (transition)",
                         agent=prev, session_id=state["session_id"], length=len(buffered))

    if author in SPECIALIST_NAMES and not state["in_parallel"]:
        state["in_parallel"] = True
        if not state["parallel_banner_shown"]:
            print_parallel_start()
            state["parallel_banner_shown"] = True
            otel_log(otel_logger, logging.INFO, "Parallel stage started",
                     session_id=state["session_id"])

    if author == SYNTHESIS.name and state["in_parallel"]:
        state["in_parallel"] = False
        print_parallel_complete(state["specialist_texts"])
        print_handoff("parallel_evaluation", SYNTHESIS.name)
        otel_log(otel_logger, logging.INFO, "Parallel stage complete",
                 specialists_completed=len(state["specialist_texts"]),
                 session_id=state["session_id"])
        state["prev_author"] = author

    if author != prev:
        if prev is None:
            if author not in SPECIALIST_NAMES:
                print_agent_start(author)
            otel_log(otel_logger, logging.INFO, "Agent start",
                     agent=author, session_id=state["session_id"])
        elif state["in_parallel"]:
            print_parallel_agent_active(author)
            otel_log(otel_logger, logging.INFO, "Parallel agent active",
                     agent=author, session_id=state["session_id"])
        elif author != SYNTHESIS.name:
            print_handoff(prev, author)
            otel_log(otel_logger, logging.INFO, "Handoff",
                     agent_from=prev, agent_to=author, session_id=state["session_id"])
        state["prev_author"] = author

    for fc in fn_calls:
        otel_log(otel_logger, logging.DEBUG, "Tool call",
                 agent=author, tool=fc.name, session_id=state["session_id"])
    for fr in fn_responses:
        otel_log(otel_logger, logging.DEBUG, "Tool result",
                 agent=author, tool=fr.name, session_id=state["session_id"])

    if author in SPECIALIST_NAMES and texts:
        state["specialist_buffers"].setdefault(author, []).extend(texts)

    if author == SYNTHESIS.name:
        _render_synthesis(event, author, texts, state)
    elif author in SPECIALIST_NAMES:
        _render_specialist(event, author, texts, state)
    else:
        for t in texts:
            if t.strip():
                print_intermediate(author, t)

    state["event_count"] += 1


def _render_synthesis(event, author: str, texts: list[str], state: dict) -> None:
    if texts:
        if not state["synthesis_header_shown"]:
            state["synthesis_header_shown"] = True
            banner(
                f"MAJORITY VOTE + FINAL APPRAISAL  --  {agent_label(SYNTHESIS.name)}",
                SYNTHESIS.name,
            )
        for t in texts:
            if t.strip():
                print(C(SYNTHESIS.name, f"  {t}"), flush=True)
    if event.is_final_response() and state["synthesis_header_shown"]:
        banner("END OF APPRAISAL", SYNTHESIS.name)
        otel_log(otel_logger, logging.INFO, "Synthesis complete",
                 agent=author, session_id=state["session_id"],
                 total_events=state["event_count"])


def _render_specialist(event, author: str, texts: list[str], state: dict) -> None:
    for t in texts:
        if t.strip():
            print_intermediate(author, t)
    if event.is_final_response() and author not in state["specialist_texts"]:
        report = "\n".join(texts) or "\n".join(state["specialist_buffers"].get(author, []))
        if report:
            state["specialist_texts"][author] = report
            otel_log(otel_logger, logging.INFO, "Specialist report ready",
                     agent=author, session_id=state["session_id"], length=len(report))


async def run_appraisal_chat() -> None:
    session = await session_service.create_session(app_name=APP_NAME, user_id=USER_ID)
    otel_log(otel_logger, logging.INFO, "Session created",
             session_id=session.id, user_id=USER_ID)

    runner = Runner(
        agent=art_appraisal_pipeline,
        app_name=APP_NAME,
        session_service=session_service,
    )

    banner("Art Appraisal Swarm  --  Google ADK + A2A Protocol")
    print(f"\n  Pipeline architecture (bias-free swarm voting):")
    print(f"    {colored_label('art_appraisal_pipeline')}")
    print(f"      +-- {colored_label('parallel_evaluation')} (Stage 1)")
    for s in SPECIALISTS:
        print(f"      |     +-- {colored_label(s.name)}")
    print(f"      +-- {colored_label(SYNTHESIS.name)} (Stage 2)")
    print()
    print(f"  OTEL file log -> {OTEL_LOG_PATH}   (tail -f otel.log)")
    if os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT") or os.environ.get(
        "OTEL_EXPORTER_OTLP_ENDPOINT"
    ):
        print("  OTLP tracing enabled — open Jaeger: http://localhost:16686")
    print()
    print("  Try: 'Appraise a Monet Water Lilies, oil on canvas, 80x100cm,")
    print("        painted in 1906. Acquired via Christie's London 1989 (Lot 42).")
    print("        Condition good, minor craquelure. Country of origin: France.'")
    print("\n  Type 'quit' to exit.")
    ruler()

    while True:
        user_input = input("\nYou: ").strip()
        if not user_input or user_input.lower() in ("quit", "exit", "q"):
            print("\nGoodbye!")
            break

        message = types.Content(role="user", parts=[types.Part(text=quarantine(user_input))])
        otel_log(otel_logger, logging.INFO, "User message",
                 session_id=session.id, preview=user_input[:120])

        banner("NEW REQUEST  -->  PIPELINE START")

        state = {
            "prev_author": None,
            "event_count": 0,
            "in_parallel": False,
            "parallel_banner_shown": False,
            "synthesis_header_shown": False,
            "specialist_texts": {},
            "specialist_buffers": {},
            "session_id": session.id,
            "t_request_start": time.perf_counter(),
            "ttft_ms": None,
        }

        with tracer.start_as_current_span(
            "appraisal_request",
            attributes={"session.id": session.id, "query.preview": user_input[:200]},
        ) as root_span:
            async for event in runner.run_async(
                session_id=session.id,
                user_id=USER_ID,
                new_message=message,
            ):
                author = getattr(event, "author", None) or "unknown"
                _process_event(event, author, state)
            root_span.set_attribute("response.events", state["event_count"])


if __name__ == "__main__":
    if not os.environ.get("NOVA_API_KEY"):
        print("ERROR: Set NOVA_API_KEY in your .env file (copy .env.example)")
        sys.exit(1)
    asyncio.run(run_appraisal_chat())
