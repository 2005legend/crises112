"""
POST /dedup — MiniLM semantic deduplication endpoint.
POST /dedup/batch-test — precision/recall evaluation endpoint.
"""
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional
from ai_service.engines.dedup_engine import DedupEngine

router = APIRouter()


class CandidateIncident(BaseModel):
    incident_id: str
    summary: str


class DedupRequest(BaseModel):
    summary: str
    candidates: list[CandidateIncident] = []


class DedupResponse(BaseModel):
    match: Optional[str] = None
    similarity_score: float
    merge_reason: str


class BatchTestPair(BaseModel):
    report_summary: str
    incident_summary: str
    expected_merge: bool


class BatchTestRequest(BaseModel):
    pairs: list[BatchTestPair]


class BatchTestResponse(BaseModel):
    total: int
    correct: int
    precision: float
    recall: float
    f1: float
    details: list[dict]


@router.post("", response_model=DedupResponse, summary="Find matching incident via semantic similarity")
async def dedup(request: Request, body: DedupRequest):
    """
    Compare a new report summary against candidate incidents using MiniLM cosine similarity.
    Returns the best matching incident_id if similarity > 0.75, otherwise null.
    """
    models = request.app.state.models
    if models.embedding_model is None:
        raise HTTPException(status_code=503, detail="Embedding model not loaded")

    engine = DedupEngine(models.embedding_model)
    result = engine.find_match(
        body.summary,
        [c.model_dump() for c in body.candidates],
    )
    return DedupResponse(**result)


@router.post("/batch-test", response_model=BatchTestResponse, summary="Evaluate dedup precision/recall")
async def batch_test(request: Request, body: BatchTestRequest):
    """
    Run dedup on a labeled test dataset and return precision, recall, and F1 scores.
    Each pair has a report_summary, incident_summary, and expected_merge boolean.
    """
    models = request.app.state.models
    if models.embedding_model is None:
        raise HTTPException(status_code=503, detail="Embedding model not loaded")

    engine = DedupEngine(models.embedding_model)
    tp = fp = fn = tn = 0
    details = []

    for pair in body.pairs:
        result = engine.find_match(
            pair.report_summary,
            [{"incident_id": "test-incident", "summary": pair.incident_summary}],
        )
        predicted_merge = result["match"] is not None
        correct = predicted_merge == pair.expected_merge

        if pair.expected_merge and predicted_merge:
            tp += 1
        elif not pair.expected_merge and predicted_merge:
            fp += 1
        elif pair.expected_merge and not predicted_merge:
            fn += 1
        else:
            tn += 1

        details.append({
            "report_summary": pair.report_summary[:80],
            "expected_merge": pair.expected_merge,
            "predicted_merge": predicted_merge,
            "similarity_score": result["similarity_score"],
            "correct": correct,
        })

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    correct_total = tp + tn

    return BatchTestResponse(
        total=len(body.pairs),
        correct=correct_total,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        details=details,
    )
