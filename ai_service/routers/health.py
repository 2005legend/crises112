"""
GET /ai/health — model health status with per-stage average latency.
"""
import time
from collections import defaultdict, deque
from fastapi import APIRouter, Request

router = APIRouter()

# Simple in-process latency tracker: stage → deque of last 50 ms values
_latency_store: dict[str, deque] = defaultdict(lambda: deque(maxlen=50))


def record_latency(stage: str, ms: float):
    _latency_store[stage].append(ms)


def avg_latency(stage: str) -> Optional[float]:
    vals = list(_latency_store[stage])
    return round(sum(vals) / len(vals)) if vals else None


from typing import Optional


@router.get("/ai/health", summary="Model health and per-stage latency")
async def health(request: Request):
    """
    Returns load status and average latency for each AI model component.
    Latency values update as requests are processed.
    """
    models = getattr(request.app.state, "models", None)
    if models is None:
        return {s: {"status": "not_loaded", "avg_latency_ms": None}
                for s in ("stt", "vision", "extraction", "embedding", "dedup")}

    return {
        "stt":        {"status": models.status.get("stt"),        "avg_latency_ms": avg_latency("stt")},
        "vision":     {"status": models.status.get("vision"),     "avg_latency_ms": avg_latency("vision")},
        "extraction": {"status": models.status.get("extraction"), "avg_latency_ms": avg_latency("extraction")},
        "embedding":  {"status": models.status.get("embedding"),  "avg_latency_ms": avg_latency("embedding")},
        "dedup":      {"status": models.status.get("embedding"),  "avg_latency_ms": avg_latency("dedup")},
    }
