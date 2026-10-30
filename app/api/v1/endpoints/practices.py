from fastapi import APIRouter

from app.core.database import get_database
from app.models.practice import PracticeInDB

router = APIRouter()


@router.get("/practices", response_model=list[PracticeInDB], summary="Listar el catálogo de indumentaria")
async def list_practices():
    """Indumentaria exigida en cada área. No requiere autenticación."""
    database = get_database()
    cursor = database["practices"].find()
    return [PracticeInDB(**doc) async for doc in cursor]