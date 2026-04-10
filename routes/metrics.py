from fastapi import APIRouter
from db.crud_metrics import get_metrics

router = APIRouter()

@router.get("/metrics")
def metrics():
    return get_metrics()