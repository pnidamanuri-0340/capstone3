"""`finlit` command-line entry point."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from finlit.config import get_settings
from finlit.logging_setup import setup_logging


def cmd_ingest(_: argparse.Namespace) -> int:
    from finlit.rag.store import ingest_all

    counts = ingest_all()
    for agent, n in counts.items():
        print(f"  {agent:<20} {n:>3} chunks")
    print(f"Knowledge base ready at {get_settings().chroma_dir.resolve()}")
    return 0


def cmd_ui(args: argparse.Namespace) -> int:
    app = Path(__file__).resolve().parent / "ui" / "app.py"
    cmd = [sys.executable, "-m", "streamlit", "run", str(app), "--server.port", str(args.port),
           "--browser.gatherUsageStats", "false"]
    return subprocess.call(cmd)


def cmd_mcp(_: argparse.Namespace) -> int:
    from finlit.mcp_server.server import main

    main()
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    from finlit.graph.builder import ask

    state = ask(" ".join(args.question), user_id=args.user, thread_id=args.thread)
    meta = state["messages"][-1].additional_kwargs.get("finlit", {})
    print(f"[{meta.get('agent_name')} | confidence {meta.get('confidence', 0):.2f}]\n")
    print(state["answer"])
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    from finlit.evals.run_evals import run

    return run(skip_llm=args.offline, judge=args.judge)


def cmd_smoke(_: argparse.Namespace) -> int:
    from finlit.smoke import run_smoke

    return run_smoke()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="finlit", description="FinLit multi-agent financial literacy app")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("ingest", help="Build the per-agent vector stores from the knowledge base").set_defaults(func=cmd_ingest)

    p = sub.add_parser("ui", help="Launch the Streamlit web app")
    p.add_argument("--port", type=int, default=8501)
    p.set_defaults(func=cmd_ui)

    sub.add_parser("mcp", help="Run the MCP server (stdio)").set_defaults(func=cmd_mcp)

    p = sub.add_parser("ask", help="Ask one question from the terminal")
    p.add_argument("question", nargs="+")
    p.add_argument("--user", default="cli")
    p.add_argument("--thread", default="cli")
    p.set_defaults(func=cmd_ask)

    p = sub.add_parser("eval", help="Run routing / retrieval / answer-quality evaluations")
    p.add_argument("--offline", action="store_true", help="Only run evals that need no API key")
    p.add_argument("--judge", action="store_true", help="Also run LLM-as-judge answer grading (slower)")
    p.set_defaults(func=cmd_eval)

    sub.add_parser("smoke", help="Quick installation health check").set_defaults(func=cmd_smoke)

    args = parser.parse_args(argv)
    # The MCP server must keep stdout clean, so it configures its own logging.
    if args.command != "mcp":
        setup_logging(get_settings().log_level)
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
