"""
Dedup Engine — MiniLM semantic deduplication with sha256-keyed embedding cache.
"""
import hashlib
import logging
import re
import time
from typing import Optional
import numpy as np
from engines.loader import get_embedding_model
from engines.utils import log_latency

logger = logging.getLogger(__name__)

# Module-level in-memory embedding cache: sha256(normalize(text)) → np.ndarray
_embedding_cache: dict[str, np.ndarray] = {}

SIMILARITY_THRESHOLD = 0.75


def normalize_text(text: str) -> str:
    """Lowercase and strip punctuation from text."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def get_embedding(text: str) -> np.ndarray:
    """
    Encode text with all-MiniLM-L6-v2.
    Uses sha256-keyed in-memory cache to avoid re-encoding identical texts.
    """
    start = time.perf_counter()
    normalized = normalize_text(text)
    cache_key = hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    if cache_key in _embedding_cache:
        logger.debug("Embedding cache hit for key %s", cache_key[:8])
        return _embedding_cache[cache_key]

    model = get_embedding_model()
    if model is None:
        raise RuntimeError("Embedding model not loaded.")

    embedding = model.encode(normalized, convert_to_numpy=True)
    _embedding_cache[cache_key] = embedding
    log_latency("embedding", start)
    return embedding


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def find_match(summary: str, candidates: list[dict]) -> dict:
    """
    Find the best-matching candidate incident for a given summary.

    Args:
        summary: The new report's summary text.
        candidates: List of dicts with keys "incident_id" and "summary".

    Returns:
        {
            "match": incident_id or None,
            "similarity_score": float,
            "merge_reason": str,
        }
    """
    start = time.perf_counter()

    if not candidates:
        log_latency("dedup", start)
        return {
            "match": None,
            "similarity_score": 0.0,
            "merge_reason": "No sufficiently similar incident found",
        }

    query_emb = get_embedding(summary)

    best_id = None
    best_score = 0.0
    best_summary = ""

    for candidate in candidates:
        cand_emb = get_embedding(candidate["summary"])
        score = cosine_similarity(query_emb, cand_emb)
        if score > best_score:
            best_score = score
            best_id = candidate["incident_id"]
            best_summary = candidate["summary"]

    log_latency("dedup", start)

    if best_score > SIMILARITY_THRESHOLD:
        # Build a shared content description from common words
        new_words = set(normalize_text(summary).split())
        cand_words = set(normalize_text(best_summary).split())
        shared = new_words & cand_words
        shared_desc = " ".join(sorted(shared)[:5]) if shared else "similar content"
        merge_reason = (
            f"Merged with incident #{best_id} (similarity {best_score:.2f}): "
            f"both describe {shared_desc}"
        )
        return {
            "match": best_id,
            "similarity_score": round(best_score, 4),
            "merge_reason": merge_reason,
        }

    return {
        "match": None,
        "similarity_score": round(best_score, 4),
        "merge_reason": "No sufficiently similar incident found",
    }
