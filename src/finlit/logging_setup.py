"""Central logging configuration."""

from __future__ import annotations

import logging

_CONFIGURED = False


def setup_logging(level: str = "INFO") -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    # Quiet chatty third-party loggers.
    for noisy in ("httpx", "chromadb", "urllib3", "anthropic"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    # google-genai warns on every tool-calling request about an SDK usage pattern LangChain controls.
    logging.getLogger("google_genai.models").setLevel(logging.ERROR)
    _CONFIGURED = True
