"""Embedding service for computing text similarity.

Provides a pluggable interface:
- TFIDFEmbeddingService: lightweight, no external deps (default for MVP)
- SentenceTransformerEmbeddingService: higher quality, requires sentence-transformers

Switch via config or by replacing the service instance.
"""

import math
from typing import Optional
import re
from abc import ABC, abstractmethod
from collections import Counter


class BaseEmbeddingService(ABC):
    @abstractmethod
    def compute_similarity(self, text_a: str, text_b: str) -> float:
        """Return cosine similarity between two texts, range [0, 1]."""
        ...


# ── TF-IDF Implementation ──────────────────────────────

class TFIDFEmbeddingService(BaseEmbeddingService):
    """Lightweight TF-IDF + cosine similarity. No external dependencies."""

    def compute_similarity(self, text_a: str, text_b: str) -> float:
        tokens_a = _tokenize(text_a)
        tokens_b = _tokenize(text_b)

        if not tokens_a or not tokens_b:
            return 0.0

        # Build term frequency vectors
        tf_a = Counter(tokens_a)
        tf_b = Counter(tokens_b)

        # Combined vocabulary
        vocab = set(tf_a.keys()) | set(tf_b.keys())

        # Compute cosine similarity
        dot_product = sum(tf_a.get(w, 0) * tf_b.get(w, 0) for w in vocab)
        norm_a = math.sqrt(sum(v ** 2 for v in tf_a.values()))
        norm_b = math.sqrt(sum(v ** 2 for v in tf_b.values()))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)


# ── Sentence Transformer Implementation ────────────────

class SentenceTransformerEmbeddingService(BaseEmbeddingService):
    """Higher quality embeddings using sentence-transformers.

    Requires: pip install sentence-transformers
    Model: configured via EMBEDDING_MODEL setting.
    """

    def __init__(self):
        import os
        from pathlib import Path
        from app.core.config import get_settings
        settings = get_settings()

        # Check if model is cached locally; if not, skip slow download
        # and fall back to TF-IDF immediately.
        cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
        model_dir_name = f"models--sentence-transformers--{settings.EMBEDDING_MODEL}"
        model_cache = cache_dir / model_dir_name
        blobs_dir = model_cache / "blobs"
        has_cached = blobs_dir.exists() and any(blobs_dir.iterdir()) if blobs_dir.exists() else False

        if not has_cached and os.environ.get("SKIP_MODEL_DOWNLOAD", "").lower() in ("1", "true", "yes"):
            raise ImportError("模型未缓存且 SKIP_MODEL_DOWNLOAD 已设置，使用 TF-IDF 降级方案")

        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(settings.EMBEDDING_MODEL)
        except Exception as exc:
            raise ImportError(
                f"无法加载 sentence-transformers 模型: {exc}"
            ) from exc

    def compute_similarity(self, text_a: str, text_b: str) -> float:
        embeddings = self._model.encode([text_a, text_b])
        # Cosine similarity
        dot = sum(a * b for a, b in zip(embeddings[0], embeddings[1]))
        norm_a = math.sqrt(sum(a * a for a in embeddings[0]))
        norm_b = math.sqrt(sum(b * b for b in embeddings[1]))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


# ── Factory ────────────────────────────────────────────

_embedding_service: Optional[BaseEmbeddingService] = None


def _is_model_cached(model_name: str) -> bool:
    """Check if the sentence-transformers model is fully cached locally."""
    from pathlib import Path
    cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
    model_dir = cache_dir / f"models--sentence-transformers--{model_name}"
    blobs_dir = model_dir / "blobs"
    if not blobs_dir.exists():
        return False
    # Model is cached if blobs directory has actual files (not just empty)
    return any(blobs_dir.iterdir())


def get_embedding_service() -> BaseEmbeddingService:
    """Get or create the embedding service singleton."""
    global _embedding_service
    if _embedding_service is None:
        from app.core.config import get_settings
        settings = get_settings()
        if _is_model_cached(settings.EMBEDDING_MODEL):
            try:
                _embedding_service = SentenceTransformerEmbeddingService()
            except Exception:
                _embedding_service = TFIDFEmbeddingService()
        else:
            print(f"[embedding] 模型 {settings.EMBEDDING_MODEL} 未缓存，使用 TF-IDF 降级方案")
            _embedding_service = TFIDFEmbeddingService()
    return _embedding_service


# ── Helpers ────────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    """Simple tokenizer: lowercase, split on non-alphanumeric + CJK char boundaries."""
    text = text.lower()
    # Split English words
    words = re.findall(r"[a-z][a-z0-9+#.]+", text)
    # Split Chinese characters as individual tokens
    chinese = re.findall(r"[一-鿿]", text)
    return words + chinese
