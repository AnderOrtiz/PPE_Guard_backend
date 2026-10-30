from fastapi import APIRouter, HTTPException

from app.api.v1.docs import errores
from app.core.database import get_database
from app.models.health import HealthResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Revisar el servicio y MongoDB",
    responses=errores((503, "MongoDB no responde.")),
)
async def health_check():
    """Hace ping a MongoDB. No requiere autenticación."""
    try:
        database = get_database()
        await database.command("ping")
        return HealthResponse(status="ok", mongo="connected")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Mongo no disponible: {e}")