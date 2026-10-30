from datetime import datetime
from pydantic import BaseModel, Field


class FilaAsistencia(BaseModel):
    alumno_id: str = Field(description="ObjectId del alumno.")
    nombre: str = Field(description="Nombre del alumno.")
    codigo: str = Field(description="Código del alumno.")
    hora_identificacion: datetime | None = Field(description="Cuándo se confirmó su identificación; `null` si no asistió.")
    presente: bool = Field(description="Si tiene asistencia registrada en esta práctica.")
    cumplio_indumentaria: bool | None = Field(description="Si llevaba la indumentaria exigida; `null` si no asistió.")
    faltantes: list[str] = Field(description="Indumentaria que le faltó.")
    evidencia_url: str | None = Field(description="Ruta de la imagen del incumplimiento, si la hay.")


class ReportePractica(BaseModel):
    practica_id: str = Field(description="ObjectId de la práctica.")
    materia_nombre: str = Field(description="Nombre de la materia.")
    docente_nombre: str = Field(description="Nombre del docente; `—` si ya no existe.")
    fecha: datetime = Field(description="Fecha de la práctica (UTC).")
    hora_inicio: datetime = Field(description="Inicio de la práctica (UTC).")
    hora_fin: datetime | None = Field(description="Fin de la práctica (UTC); `null` si sigue activa.")
    total_matriculados: int = Field(description="Alumnos matriculados en la materia que siguen existiendo.")
    presentes: int = Field(description="Alumnos con asistencia registrada.")
    ausentes: int = Field(description="Alumnos sin asistencia registrada.")
    cumplieron: int = Field(description="Presentes con la indumentaria completa.")
    no_cumplieron: int = Field(description="Presentes con indumentaria faltante.")
    detalle: list[FilaAsistencia] = Field(description="Una fila por alumno matriculado.")