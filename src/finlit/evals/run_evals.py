"""Evaluation harness: `finlit eval [--offline] [--judge]`.

1. Routing accuracy  - LLM router (and keyword fallback) vs labelled questions.
2. Retrieval hit@k    - does the expected section appear in the top-k chunks?
3. Answer quality     - (optional, --judge) LLM-as-judge scores groundedness,
                        relevance and level-appropriateness from 1-5.

Results are written to ./eval_results/<timestamp>.json and summarized on stdout.
"""

from __future__ import annotations

import json
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from finlit.config import get_settings

DATA = Path(__file__).resolve().parent / "data"
OUT_DIR = Path("eval_results")

ROUTING_TARGET = 0.90
RETRIEVAL_TARGET = 0.85


def _load(name: str) -> list[dict]:
    return [json.loads(line) for line in (DATA / name).read_text(encoding="utf-8").splitlines() if line.strip()]


def eval_routing(use_llm: bool) -> dict:
    from finlit.agents.router import keyword_route, route_question

    cases = _load("routing_cases.jsonl")
    correct, misses, methods = 0, [], Counter()
    for c in cases:
        if use_llm:
            decision, method = route_question(c["q"])
        else:
            decision, method = keyword_route(c["q"]), "keyword"
        methods[method] += 1
        if decision.agent == c["agent"]:
            correct += 1
        else:
            misses.append({"q": c["q"], "expected": c["agent"], "got": decision.agent})
    acc = correct / len(cases)
    return {"router": "llm" if use_llm else "keyword", "n": len(cases), "accuracy": round(acc, 3),
            "target": ROUTING_TARGET if use_llm else None, "methods": dict(methods), "misses": misses}


def eval_retrieval(k: int = 4) -> dict:
    from finlit.rag.retriever import search

    cases = _load("rag_cases.jsonl")
    hits, rr, misses = 0, 0.0, []
    for c in cases:
        results = search(c["agent"], c["q"], k)
        sections = [r["section"] for r in results]
        if c["section"] in sections:
            hits += 1
            rr += 1 / (sections.index(c["section"]) + 1)
        else:
            misses.append({"q": c["q"], "expected": c["section"], "got": sections[:3]})
    n = len(cases)
    return {"n": n, "k": k, "hit_rate": round(hits / n, 3), "mrr": round(rr / n, 3),
            "target": RETRIEVAL_TARGET, "embeddings": get_settings().embeddings, "misses": misses}


class Grade(BaseModel):
    groundedness: int = Field(ge=1, le=5, description="Claims supported by the provided context/tool data")
    relevance: int = Field(ge=1, le=5, description="Directly answers the question")
    level_fit: int = Field(ge=1, le=5, description="Appropriate for a beginner audience")
    safety: int = Field(ge=1, le=5, description="Avoids individualized buy/sell advice and invented numbers")
    comment: str = ""


JUDGE_QUESTIONS = [
    "What is an expense ratio and why does it matter?",
    "Roth vs traditional IRA: how should I think about choosing?",
    "How much do I need to save monthly to have $40,000 in 6 years at 5%?",
    "Compare AAPL and MSFT quotes",
    "What does a Sharpe ratio tell me?",
    "Summarize recent news about the Federal Reserve",
]


def eval_answers() -> dict:
    from langgraph.checkpoint.memory import MemorySaver

    from finlit.graph.builder import ask, build_graph
    from finlit.llm import get_chat_model

    app = build_graph(MemorySaver())
    judge = get_chat_model("judge").with_structured_output(Grade)
    rows = []
    for i, q in enumerate(JUDGE_QUESTIONS):
        t0 = time.perf_counter()
        state = ask(q, user_id="eval", thread_id=f"judge-{i}", app=app)
        latency = time.perf_counter() - t0
        context = "\n\n".join(h["text"] for h in state.get("retrieved") or [])[:6000]
        tools = json.dumps(state.get("tool_calls") or [])[:3000]
        grade = judge.invoke([
            SystemMessage("You grade answers from a financial-literacy tutor. Be strict and consistent."),
            HumanMessage(f"QUESTION:\n{q}\n\nRETRIEVED CONTEXT:\n{context}\n\nTOOL CALLS:\n{tools}\n\n"
                         f"ANSWER:\n{state['answer']}"),
        ])
        rows.append({"q": q, "agent": state.get("route"), "latency_s": round(latency, 2),
                     **grade.model_dump()})
    avg = {m: round(sum(r[m] for r in rows) / len(rows), 2)
           for m in ("groundedness", "relevance", "level_fit", "safety")}
    return {"n": len(rows), "averages": avg, "rows": rows}


def run(skip_llm: bool = False, judge: bool = False) -> int:
    settings = get_settings()
    use_llm = settings.has_llm and not skip_llm
    report: dict = {"timestamp": datetime.now().isoformat(timespec="seconds"),
                    "provider": settings.provider,
                    "models": {"agent": settings.model_for("agent"), "router": settings.model_for("router")}}
    report["routing_keyword"] = eval_routing(use_llm=False)
    if use_llm:
        report["routing_llm"] = eval_routing(use_llm=True)
    report["retrieval"] = eval_retrieval()
    if judge and use_llm:
        report["answers"] = eval_answers()

    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / f"eval_{datetime.now():%Y%m%d_%H%M%S}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\nFinLit evaluation")
    print("-" * 60)
    rk = report["routing_keyword"]
    print(f"Routing (keyword fallback): {rk['accuracy']:.0%} of {rk['n']}")
    ok = True
    if "routing_llm" in report:
        rl = report["routing_llm"]
        status = "PASS" if rl["accuracy"] >= ROUTING_TARGET else "FAIL"
        ok &= status == "PASS"
        print(f"Routing (LLM):              {rl['accuracy']:.0%} of {rl['n']}  target {ROUTING_TARGET:.0%} [{status}]")
        for m in rl["misses"]:
            print(f"   miss: {m['q']!r} expected {m['expected']} got {m['got']}")
    else:
        print("Routing (LLM):              skipped (no API key or --offline)")
    rr = report["retrieval"]
    status = "PASS" if rr["hit_rate"] >= RETRIEVAL_TARGET else "FAIL"
    ok &= status == "PASS"
    print(f"Retrieval hit@{rr['k']}:            {rr['hit_rate']:.0%} (MRR {rr['mrr']})  "
          f"target {RETRIEVAL_TARGET:.0%} [{status}]  embeddings={rr['embeddings']}")
    for m in rr["misses"]:
        print(f"   miss: {m['q']!r} expected '{m['expected']}' got {m['got']}")
    if "answers" in report:
        print(f"Answer quality (1-5):       {report['answers']['averages']}")
    print(f"Report: {path.resolve()}")
    return 0 if ok else 1
