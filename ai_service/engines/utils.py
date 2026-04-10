"""
Utility helpers for the AI service engines.
"""
import logging
import time
import json

logger = logging.getLogger(__name__)


def log_latency(stage: str, start_time: float) -> None:
    """
    Log the duration of a pipeline stage in milliseconds using structured JSON output.

    Args:
        stage: Name of the pipeline stage (e.g. "stt", "extraction", "dedup").
        start_time: Start time from time.perf_counter().
    """
    duration_ms = (time.perf_counter() - start_time) * 1000
    record = {
        "stage": stage,
        "duration_ms": round(duration_ms, 2),
    }
    logger.info(json.dumps(record))
