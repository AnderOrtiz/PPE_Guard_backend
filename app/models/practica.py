from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field
from app.models.common import PyObjectId


class PracticaInDB(BaseModel):
    id: PyObjectId = Field(alias="_id", description="ObjectId de la práctica.")
    materia_id: str = Field(description="ObjectId de la materia.")
    docente_id: str = Field(description="ObjectId del docente de la materia.")
    fecha: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Fecha de la práctica (UTC).")
    hora_inicio: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Inicio de la práctica (UTC).")
    hora_fin: datetime | None = Field(default=None, description="Fin de la práctica (UTC); `null` si sigue activa.")
    estado: Literal["activa", "finalizada"] = Field(default="activa", description="Estado de la práctica.")

    model_config = {"populate_by_name": True}

class PracticaCreate(BaseModel):
    materia_id: str = Field(description="ObjectId de la materia en la que se inicia la práctica.")


class ConfirmarRequest(BaseModel):
    alumno_id: str = Field(description="ObjectId del último alumno identificado (evento `estudiante_identificado`).")


class ConfirmarResponse(BaseModel):
    fase: Literal["indumentaria"] = Field(description="La fase en la que queda la práctica.")
    alumno_id: str = Field(description="ObjectId del alumno en revisión.")