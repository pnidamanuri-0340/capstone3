"""Headless Streamlit check: the app renders without exceptions and handles a chat turn."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from finlit import llm
from tests.conftest import fake_model, route_msg

APP = str(Path(__file__).resolve().parents[2] / "src/finlit/ui/app.py")


def test_app_renders(kb):
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert "FinLit" in at.title[0].value
    assert len(at.tabs) == 4


def test_chat_turn_renders_agent_answer(kb):
    llm.set_model_override("router", fake_model(route_msg("financial_literacy")))
    llm.set_model_override("agent", fake_model("An index fund tracks a market index [1]."))
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.chat_input[0].set_value("What is an index fund?").run()
    assert not at.exception
    rendered = " ".join(m.value for m in at.markdown)
    assert "An index fund tracks a market index" in rendered
