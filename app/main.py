import os
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import connect_to_mongo, close_mongo_connection
from app.core import async_bridge, apagado
from app.api.v1.docs import DESCRIPCION_API, TAGS
from app.api.v1.router import api_router
from app.api.v1.endpoints.evidencias import router as evidencias_router
from app.services.practica_lifecycle import recuperar_practica_activa
from app.services import practica_registry, vista_previa
from app.services.camera_service import camera_service
from app.websockets.router import router as ws_router

os.makedirs("static/evidence", exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    async_bridge.set_main_loop(asyncio.get_running_loop())
    apagado.vigilar_senales()
    await recuperar_practica_activa()
    yield
    # Se apaga la cámara, pero la práctica sigue "activa" en la base para reanudarla al volver.
    practica_registry.detener_todos()
    # Una vista previa de enrolamiento que quedó abierta no debe retener el dispositivo.
    vista_previa.detener()
    camera_service.liberar_todos()
    await close_mongo_connection()


app = FastAPI(
    title=settings.APP_NAME,
    description=DESCRIPCION_API,
    version="1.0.0",
    openapi_tags=TAGS,
    swagger_ui_parameters={"persistAuthorization": True},  # el token sobrevive a recargar /docs
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")
app.include_router(evidencias_router, tags=["evidencias"])  # /static/evidence/..., con token
app.include_router(ws_router)


@app.get("/", summary="Comprobar que el backend corre", tags=["health"])
def root():
    """Responde siempre que el proceso esté en marcha; no revisa MongoDB. Para eso, `GET /api/v1/health`."""
    return {"message": f"{settings.APP_NAME} backend corriendo"}