"""Per-agent retrieval, exposed both as plain functions and as a LangChain retriever."""

from __future__ import annotations

import logging

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from finlit.config import get_settings
from finlit.rag.store import get_collection

log = logging.getLogger(__name__)

# Below this cosine similarity a chunk is treated as irrelevant (ONNX embeddings only;
# the offline hash embeddings have a different score scale).
MIN_SCORE = {"onnx": 0.25, "hash": 0.0}


class KnowledgeBaseUnavailable(RuntimeError):
    pass


def search(agent: str, query: str, k: int | None = None) -> list[dict]:
    """Return [{text, source, section, score}] sorted by relevance."""
    settings = get_settings()
    k = k or settings.rag_top_k
    try:
        col = get_collection(agent)
    except Exception as exc:  # noqa: BLE001
        raise KnowledgeBaseUnavailable(
            f"Knowledge base for '{agent}' is missing. Run `finlit ingest`."
        ) from exc
    if col.count() == 0:
        return []
    res = col.query(query_texts=[query], n_results=min(k, col.count()))
    threshold = MIN_SCORE.get(settings.embeddings, 0.0)
    hits = []
    for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        score = 1.0 - float(dist)
        if score < threshold:
            continue
        hits.append({"text": doc, "source": meta.get("source"), "section": meta.get("section"),
                     "score": round(score, 3)})
    return hits


class AgentKnowledgeRetriever(BaseRetriever):
    """LangChain-compatible retriever bound to one agent's collection."""

    agent: str
    k: int = 4

    def _get_relevant_documents(self, query: str, *,
                                run_manager: CallbackManagerForRetrieverRun) -> list[Document]:
        return [
            Document(page_content=h["text"],
                     metadata={"source": h["source"], "section": h["section"], "score": h["score"]})
            for h in search(self.agent, query, self.k)
        ]
