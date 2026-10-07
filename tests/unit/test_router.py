import json
from pathlib import Path

from finlit import llm
from finlit.agents.router import keyword_route, route_question
from tests.conftest import fake_model, route_msg

CASES = [json.loads(line) for line in
         (Path(__file__).resolve().parents[2] / "src/finlit/evals/data/routing_cases.jsonl")
         .read_text(encoding="utf-8").splitlines() if line.strip()]


class Boom:
    def with_structured_output(self, *_a, **_k):
        raise RuntimeError("network down")


def test_llm_route_used_when_available():
    llm.set_model_override("router", fake_model(route_msg("tax_education", 0.95)))
    decision, method = route_question("Roth vs traditional?")
    assert (decision.agent, method) == ("tax_education", "llm")


def test_falls_back_to_keywords_on_llm_failure():
    llm.set_model_override("router", Boom())
    decision, method = route_question("What is the latest news on Tesla?")
    assert method == "keyword" and decision.agent == "news_synthesis"


def test_low_confidence_llm_defers_to_keywords():
    llm.set_model_override("router", fake_model(route_msg("goal_planning", 0.1)))
    decision, method = route_question("What is the 401(k) contribution limit?")
    assert decision.agent == "tax_education" and method == "keyword"


def test_keyword_router_baseline_accuracy():
    """The fallback router should be useful on its own (the LLM router is evaluated by `finlit eval`)."""
    correct = sum(keyword_route(c["q"]).agent == c["agent"] for c in CASES)
    assert correct / len(CASES) >= 0.75, f"{correct}/{len(CASES)}"


def test_unknown_question_defaults_to_literacy():
    assert keyword_route("hello there").agent == "financial_literacy"
