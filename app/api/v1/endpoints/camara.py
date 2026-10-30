from fastapi import APIRouter, Depends, HTTPException, status

from app.api.v1.dependencies import require_role
from app.api.v1.docs import errores
from app.models.camara import VistaPreviaEstado
from app.services import vista_previa
from app.services.camera_service import camera_service

router = APIRouter()

# Los mismos roles que pueden enrolar un alumno (POST /usuarios/alumnos)
puede_enrolar = require_role("coordinador", "docente")


def _estado(user: dict) -> VistaPreviaEstado:
    return VistaPreviaEstado(
        activa=vista_previa.activa(user["user_id"]),
        camara_encendida=camera_service.encendida,
        gracia_segundos=vista_previa.GRACIA_SIN_LECTURA_SEGUNDOS,
    )


@router.post(
    "/camara/vista-previa",
    response_model=VistaPreviaEstado,
    summary="Encender la vista previa",
    responses=errores(401, 403, (503, "No se pudo abrir la cámara del servidor.")),
)
async def encender_vista_previa(user: dict = Depends(puede_enrolar)):
    """Enciende la cámara para ver `GET /stream` antes de enrolar a un alumno. Repetirlo solo reinicia el plazo.

    Se apaga sola tras `gracia_segundos` sin leer el stream. **Roles:** `docente`, `coordinador` o `admin`.
    """
    try:
        await vista_previa.encender(user["user_id"])
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo abrir la cámara del servidor. Verifica que esté conectada y que no la esté usando otra aplicación.",
        )
    return _estado(user)


@router.get(
    "/camara/vista-previa",
    response_model=VistaPreviaEstado,
    summary="Consultar la vista previa",
    responses=errores(401, 403),
)
async def estado_vista_previa(user: dict = Depends(puede_enrolar)):
    """Estado de la vista previa de quien pregunta y de la cámara. **Roles:** `docente`, `coordinador` o `admin`."""
    return _estado(user)


@router.delete(
    "/camara/vista-previa",
    response_model=VistaPreviaEstado,
    summary="Apagar la vista previa",
    responses=errores(401, 403),
)
async def apagar_vista_previa(user: dict = Depends(puede_enrolar)):
    """Apaga la vista previa de quien llama. La cámara sigue encendida si la usa una práctica u otra vista previa.

    **Roles:** `docente`, `coordinador` o `admin`.
    """
    await vista_previa.apagar(user["user_id"])
    return _estado(user)
