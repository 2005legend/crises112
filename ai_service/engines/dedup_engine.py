"""
Dedup Engine — 4-signal weighted fusion dedup for emergency incident matching.

Signals:
  1. Semantic similarity  (MiniLM on extracted summaries)  weight=0.45
  2. Geo score            (exponential decay on distance)   weight=0.25
  3. Keyword overlap      (Jaccard on emergency keywords)   weight=0.15
  4. Temporal score       (recency within 30-min window)    weight=0.15

Plus: entity boost (+0.15 max) for shared location tokens.
Dynamic threshold per incident type.
Embedding cache keyed by sha256(normalize(text)).
"""
import hashlib
import logging
import math
import re
import time
from datetime import datetime, timezone
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ── Weights ───────────────────────────────────────────────────────────────────
W_SEMANTIC  = 0.45
W_GEO       = 0.25
W_KEYWORD   = 0.15
W_TEMPORAL  = 0.15

# ── Dynamic thresholds per incident type ─────────────────────────────────────
MERGE_THRESHOLDS = {
    "fire":          0.60,   # fire reports vary wildly — be aggressive
    "road_accident": 0.65,
    "medical":       0.65,
    "flood":         0.62,
    "violence":      0.75,   # conservative — two weapon incidents nearby ≠ same
    "crime":         0.75,
    "unknown":       0.70,
    "default":       0.65,
}

# ── Emergency keyword vocabulary for Jaccard overlap ─────────────────────────
EMERGENCY_KEYWORDS = {
    "fire", "flames", "smoke", "burning",
    "accident", "crash", "collision", "hit",
    "injured", "blood", "unconscious", "dead", "bleeding",
    "flood", "water", "trapped", "drowning",
    "weapon", "gun", "knife", "shooting", "stabbing",
    "ambulance", "police", "hospital",
    "explosion", "blast", "bomb",
    "child", "children", "minor",
    "highway", "expressway", "flyover",
}

# Location stop-words excluded from entity boost
LOCATION_STOPWORDS = {"near", "at", "the", "in", "on", "a", "an", "and", "or", "of", "nagar", "road", "street", "area"}


def get_threshold(incident_type: Optional[str]) -> float:
    if not incident_type:
        return MERGE_THRESHOLDS["default"]
    return MERGE_THRESHOLDS.get(incident_type.lower(), MERGE_THRESHOLDS["default"])


# ── Text utilities ────────────────────────────────────────────────────────────

def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def text_hash(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode()).hexdigest()


def get_encode_text(summary: Optional[str], raw_text: Optional[str]) -> str:
    """
    Prefer extracted summary (normalized, noise-free) over raw text.
    Falls back to first 200 chars of cleaned raw text.
    """
    if summary and summary.strip():
        return summary.strip()
    if raw_text:
        return normalize_text(raw_text)[:200]
    return ""


# ── Signal functions ──────────────────────────────────────────────────────────

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def geo_score(distance_m: Optional[float]) -> float:
    """
    Exponential decay: rewards genuinely close reports much more than borderline ones.
    0m → 1.0,  100m → 0.61,  200m → 0.37,  500m → 0.08
    Returns 0.5 (neutral) when no coordinates available.
    """
    if distance_m is None:
        return 0.5
    return math.exp(-distance_m / 200.0)


def keyword_overlap(text_a: str, text_b: str) -> float:
    """
    Jaccard similarity on emergency keyword vocabulary.
    Returns 0.5 neutral if neither text contains any keywords.
    """
    words_a = set(text_a.lower().split()) & EMERGENCY_KEYWORDS
    words_b = set(text_b.lower().split()) & EMERGENCY_KEYWORDS
    if not words_a and not words_b:
        return 0.5   # neutral — no keywords in either
    if not words_a or not words_b:
        return 0.2   # penalize if one side has no keywords
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


def temporal_score(report_time: Optional[datetime], candidate_time: Optional[datetime]) -> float:
    """
    Linear decay within 30-minute window.
    0 min apart → 1.0,  15 min → 0.5,  30 min → 0.0
    Returns 0.5 neutral when timestamps unavailable.
    """
    if report_time is None or candidate_time is None:
        return 0.5
    try:
        age_minutes = abs((report_time - candidate_time).total_seconds() / 60)
        if age_minutes > 30:
            return 0.0
        return 1.0 - (age_minutes / 30.0)
    except Exception:
        return 0.5


def entity_boost(location_a: Optional[str], location_b: Optional[str]) -> float:
    """
    Additive boost (max +0.15) when two reports share location tokens.
    """
    if not location_a or not location_b:
        return 0.0
    tokens_a = set(location_a.lower().split()) - LOCATION_STOPWORDS
    tokens_b = set(location_b.lower().split()) - LOCATION_STOPWORDS
    shared = tokens_a & tokens_b
    return min(0.15, len(shared) * 0.05)


def build_merge_reason(
    incident_id: str,
    final: float,
    semantic: float,
    geo: float,
    keyword: float,
    temporal: float,
    boost: float,
    threshold: float,
    shared_keywords: list[str],
) -> str:
    parts = [
        f"Merged with incident {incident_id}",
        f"combined score {final:.2f} > threshold {threshold:.2f}",
        f"semantic {semantic:.2f}",
        f"geo {geo:.2f}",
        f"keyword {keyword:.2f}",
        f"temporal {temporal:.2f}",
    ]
    if boost > 0:
        parts.append(f"entity boost +{boost:.2f}")
    if shared_keywords:
        parts.append(f"shared keywords: {shared_keywords}")
    return " | ".join(parts)


# ── Main engine ───────────────────────────────────────────────────────────────

class DedupEngine:
    def __init__(self, embedding_model):
        self.model = embedding_model
        self._cache: dict[str, np.ndarray] = {}

    def _encode(self, text: str) -> np.ndarray:
        key = text_hash(text)
        if key in self._cache:
            logger.debug(f"Embedding cache hit {key[:8]}")
            return self._cache[key]
        vector = self.model.encode(text, convert_to_numpy=True)
        self._cache[key] = vector
        return vector

    def find_match(
        self,
        summary: Optional[str],
        candidates: list[dict],
        incident_type: Optional[str] = None,
        raw_text: Optional[str] = None,
        report_time: Optional[datetime] = None,
        location_string: Optional[str] = None,
    ) -> dict:
        """
        4-signal weighted fusion dedup.

        candidates: [{
            "incident_id": str,
            "summary": str,
            "distance_m": float (optional),
            "updated_at": ISO str or datetime (optional),
            "location_string": str (optional),
        }]

        Returns: {
            "match": str|None,
            "similarity_score": float,
            "combined_score": float,
            "merge_reason": str,
            "threshold_used": float,
            "signal_breakdown": {...}
        }
        """
        start = time.time()
        threshold = get_threshold(incident_type)
        encode_text = get_encode_text(summary, raw_text)

        if not candidates:
            return {
                "match": None,
                "similarity_score": 0.0,
                "combined_score": 0.0,
                "merge_reason": "No candidate incidents provided",
                "threshold_used": threshold,
                "signal_breakdown": {},
            }

        if not encode_text:
            return {
                "match": None,
                "similarity_score": 0.0,
                "combined_score": 0.0,
                "merge_reason": "No text available for encoding",
                "threshold_used": threshold,
                "signal_breakdown": {},
            }

        query_vec = self._encode(encode_text)

        best_final = 0.0
        best_id = None
        best_breakdown = {}
        best_cand_summary = ""
        best_cand_location = None

        for candidate in candidates:
            cand_id = candidate.get("incident_id", "")
            cand_summary = candidate.get("summary", "")
            if not cand_summary and not candidate.get("raw_text"):
                continue

            cand_encode = get_encode_text(cand_summary, candidate.get("raw_text"))
            if not cand_encode:
                continue

            # Signal 1: semantic
            cand_vec = self._encode(cand_encode)
            sem = cosine_similarity(query_vec, cand_vec)

            # Signal 2: geo
            distance_m = candidate.get("distance_m")
            geo = geo_score(distance_m)

            # Signal 3: keyword overlap
            kw = keyword_overlap(encode_text, cand_encode)

            # Signal 4: temporal
            cand_time = candidate.get("updated_at")
            if isinstance(cand_time, str):
                try:
                    cand_time = datetime.fromisoformat(cand_time.replace("Z", "+00:00"))
                except Exception:
                    cand_time = None
            temp = temporal_score(report_time, cand_time)

            # Weighted fusion
            final = W_SEMANTIC * sem + W_GEO * geo + W_KEYWORD * kw + W_TEMPORAL * temp

            # Entity boost
            cand_location = candidate.get("location_string")
            boost = entity_boost(location_string, cand_location)
            final = min(1.0, final + boost)

            if final > best_final:
                best_final = final
                best_id = cand_id
                best_cand_summary = cand_summary
                best_cand_location = cand_location
                best_breakdown = {
                    "semantic": round(sem, 4),
                    "geo": round(geo, 4),
                    "keyword": round(kw, 4),
                    "temporal": round(temp, 4),
                    "entity_boost": round(boost, 4),
                    "distance_m": distance_m,
                }

        elapsed = round((time.time() - start) * 1000)
        logger.info(
            f"Dedup: best_combined={best_final:.3f}, threshold={threshold}, "
            f"type={incident_type}, candidates={len(candidates)}, elapsed={elapsed}ms"
        )

        if best_final > threshold:
            shared = list(
                (set(normalize_text(encode_text).split()) &
                 set(normalize_text(best_cand_summary).split())) &
                EMERGENCY_KEYWORDS
            )[:5]
            reason = build_merge_reason(
                best_id, best_final,
                best_breakdown.get("semantic", 0),
                best_breakdown.get("geo", 0),
                best_breakdown.get("keyword", 0),
                best_breakdown.get("temporal", 0),
                best_breakdown.get("entity_boost", 0),
                threshold,
                shared,
            )
            return {
                "match": best_id,
                "similarity_score": best_breakdown.get("semantic", 0),
                "combined_score": round(best_final, 4),
                "merge_reason": reason,
                "threshold_used": threshold,
                "signal_breakdown": best_breakdown,
            }

        return {
            "match": None,
            "similarity_score": best_breakdown.get("semantic", 0) if best_breakdown else 0.0,
            "combined_score": round(best_final, 4),
            "merge_reason": f"Best combined score {best_final:.2f} below threshold {threshold:.2f}",
            "threshold_used": threshold,
            "signal_breakdown": best_breakdown,
        }
