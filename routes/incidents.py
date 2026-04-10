from fastapi import APIRouter
from db.crud_incidents import get_all_incidents
from services.utils import serialize_mongo

router = APIRouter()

@router.get("/incidents")
def get_all():
    data = get_all_incidents()
    return serialize_mongo(data)

