"""Embedding functions for Chroma.

* `onnx`: Chroma's bundled all-MiniLM-L6-v2 ONNX model (no PyTorch needed).
* `hash`: deterministic hashed bag-of-words, fully offline; used by tests.
"""

from __future__ import annotations

import hashlib
import math
import re

from chromadb import Documents, EmbeddingFunction, Embeddings

_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = {"the", "a", "an", "of", "to", "and", "or", "in", "is", "it", "for", "on", "what",
         "how", "my", "i", "do", "be", "are", "with", "as", "by", "can", "you", "your"}


class HashEmbeddingFunction(EmbeddingFunction[Documents]):
    """Lexical embedding: words and bigrams hashed into a fixed-size normalized vector."""

    DIM = 384

    def __init__(self) -> None:  # explicit for chroma's config machinery
        pass

    def __call__(self, input: Documents) -> Embeddings:
        return [self._embed(t) for t in input]

    def _embed(self, text: str) -> list[float]:
        vec = [0.0] * self.DIM
        words = [w for w in _TOKEN.findall(text.lower()) if w not in _STOP]
        grams = words + [f"{a}_{b}" for a, b in zip(words, words[1:])]
        for g in grams:
            h = int(hashlib.md5(g.encode()).hexdigest(), 16)
            vec[h % self.DIM] += 1.0 if (h >> 9) & 1 else -1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    @staticmethod
    def name() -> str:
        return "finlit-hash"

    def get_config(self) -> dict:
        return {}

    @staticmethod
    def build_from_config(config: dict) -> "HashEmbeddingFunction":
        return HashEmbeddingFunction()


def get_embedding_function(kind: str):
    if kind == "hash":
        return HashEmbeddingFunction()
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

    return DefaultEmbeddingFunction()
