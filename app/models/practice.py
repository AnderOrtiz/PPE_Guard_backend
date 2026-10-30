from datetime import datetime, timezone
from pydantic import BaseModel, Field
from app.models.common import PyObjectId


class PracticeCreate(BaseModel):
    """Lo que se envía para crear una práctica en el catálogo."""
    area: str = Field(description="`civil` o `medicina`.")
    nombre: str = Field(description="Nombre de la práctica en el catálogo.")
    ppe_requerido: list[str] = Field(description="Indumentaria exigida en esta área.")


class PracticeInDB(PracticeCreate):
    """Lo que realmente vive en Mongo (incluye el _id que Mongo genera)."""
    id: PyObjectId = Field(alias="_id", description="ObjectId del registro del catálogo.")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Fecha de creación (UTC).")

    model_config = {"populate_by_name": True}