"""Chroma vector store: one collection per specialist agent."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings

from finlit.agents.registry import AGENT_KEYS
from finlit.config import get_settings
from finlit.rag.embeddings import get_embedding_function

log = logging.getLogger(__name__)

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"


def collection_name(agent: str) -> str:
    return f"finlit_{agent}"


@lru_cache(maxsize=4)
def _client(path: str) -> chromadb.ClientAPI:
    return chromadb.PersistentClient(path=path, settings=ChromaSettings(anonymized_telemetry=False))


def get_client() -> chromadb.ClientAPI:
    settings = get_settings()
    settings.ensure_dirs()
    return _client(str(settings.chroma_dir.resolve()))


def get_collection(agent: str, create: bool = False):
    client = get_client()
    ef = get_embedding_function(get_settings().embeddings)
    if create:
        return client.get_or_create_collection(
            collection_name(agent), embedding_function=ef, metadata={"hnsw:space": "cosine"}
        )
    return client.get_collection(collection_name(agent), embedding_function=ef)


# ----------------------------------------------------------------- ingest
@dataclass
class Chunk:
    id: str
    text: str
    source: str
    section: str


def chunk_markdown(text: str, source: str, max_chars: int = 1500) -> list[Chunk]:
    """Split on `## ` headings; each chunk carries its document title and section heading."""
    title_match = re.search(r"^# (.+)$", text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else source
    parts = re.split(r"^## ", text, flags=re.MULTILINE)
    chunks: list[Chunk] = []
    preamble = re.sub(r"^# .+$", "", parts[0], flags=re.MULTILINE).strip()
    for i, part in enumerate(parts[1:], start=1):
        heading, _, body = part.partition("\n")
        body = body.strip()
        if not body:
            continue
        if preamble and i == 1:
            body = f"{preamble}\n\n{body}"
        for j in range(0, len(body), max_chars):
            piece = body[j:j + max_chars]
            chunks.append(Chunk(
                id=f"{source}:{i}:{j // max_chars}",
                text=f"{title} - {heading.strip()}\n{piece}",
                source=source,
                section=heading.strip(),
            ))
    return chunks


def ingest_agent(agent: str, knowledge_dir: Path = KNOWLEDGE_DIR) -> int:
    folder = knowledge_dir / agent
    files = sorted(folder.glob("*.md"))
    if not files:
        log.warning("No knowledge files for %s in %s", agent, folder)
    client = get_client()
    try:
        client.delete_collection(collection_name(agent))
    except Exception:  # noqa: BLE001 - collection may not exist yet
        pass
    col = get_collection(agent, create=True)
    chunks: list[Chunk] = []
    for f in files:
        chunks.extend(chunk_markdown(f.read_text(encoding="utf-8"), f"{agent}/{f.name}"))
    if chunks:
        col.add(
            ids=[c.id for c in chunks],
            documents=[c.text for c in chunks],
            metadatas=[{"source": c.source, "section": c.section, "agent": agent} for c in chunks],
        )
    log.info("Ingested %d chunks for %s", len(chunks), agent)
    return len(chunks)


def ingest_all(knowledge_dir: Path = KNOWLEDGE_DIR) -> dict[str, int]:
    return {a: ingest_agent(a, knowledge_dir) for a in AGENT_KEYS}


def collection_counts() -> dict[str, int]:
    out = {}
    for a in AGENT_KEYS:
        try:
            out[a] = get_collection(a).count()
        except Exception:  # noqa: BLE001
            out[a] = 0
    return out
