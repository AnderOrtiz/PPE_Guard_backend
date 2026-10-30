from datetime import datetime, timezone
from pydantic import BaseModel, Field
from app.models.common import PyObjectId


class AsistenciaInDB(BaseModel):
    id: PyObjectId = Field(alias="_id", description="ObjectId de la asistencia.")
    practica_id: str = Field(description="ObjectId de la práctica.")
    alumno_id: str = Field(description="ObjectId del alumno.")
    hora_identificacion: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Cuándo se confirmó su identificación (UTC).")
    cumplio_indumentaria: bool = Field(description="Si llevaba toda la indumentaria exigida.")
    faltantes: list[str] = Field(default=[], description="Indumentaria que le faltó.")
    evidencia_url: str | None = Field(default=None, description="Ruta de la imagen del incumplimiento; se abre con `GET /static/evidence/...`.")

    model_config = {"populate_by_name": True}


class AsistenciaAlumnoOut(AsistenciaInDB):
    """La asistencia tal como la ve el alumno: con el contexto que él no puede consultar por su cuenta."""
    materia_id: str | None = Field(default=None, description="ObjectId de la materia de la práctica.")
    materia_nombre: str | None = Field(default=None, description="Nombre de la materia.")
    docente_nombre: str | None = Field(default=None, description="Nombre del docente.")
