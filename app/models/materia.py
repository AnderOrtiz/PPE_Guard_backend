from typing import Literal
from pydantic import BaseModel, Field, ConfigDict
from app.models.common import PyObjectId


class MateriaCreate(BaseModel):
    nombre: str = Field(description="Nombre de la materia.")
    area: Literal["civil", "medicina"] = Field(description="Área; define la indumentaria exigida y el modelo de detección.")
    carrera: str = Field(description="Carrera a la que pertenece.")
    facultad: str = Field(description="Facultad a la que pertenece.")
    aula: str = Field(description="Aula o laboratorio.")
    docente_id: str = Field(description="ObjectId del docente que la imparte.")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "nombre": "Cálculo II",
                    "area": "civil",
                    "carrera": "Ingeniería Civil",
                    "facultad": "Ingenieria",
                    "aula": "Edificio B - Aula 204",
                    "docente_id": "6abaaf8708ac6806607fb904",
                }
            ]
        }
    )


class MateriaInDB(BaseModel):
    id: PyObjectId = Field(alias="_id", description="ObjectId de la materia.")
    nombre: str = Field(description="Nombre de la materia.")
    area: Literal["civil", "medicina"] = Field(description="Área; define la indumentaria exigida y el modelo de detección.")
    carrera: str = Field(description="Carrera a la que pertenece.")
    facultad: str = Field(description="Facultad a la que pertenece.")
    aula: str = Field(description="Aula o laboratorio.")
    docente_id: str = Field(description="ObjectId del docente que la imparte.")
    coordinador_id: str = Field(description="ObjectId del coordinador a cargo; es el coordinador del docente.")
    alumnos_ids: list[str] = Field(default=[], description="ObjectId de los alumnos matriculados.")

    model_config = {"populate_by_name": True}

class MateriaAlumnoOut(BaseModel):
    """Lo que ve un alumno de una materia en la que está matriculado."""
    id: PyObjectId = Field(alias="_id", description="ObjectId de la materia.")
    nombre: str = Field(description="Nombre de la materia.")
    area: Literal["civil", "medicina"] = Field(description="Área de la materia.")
    carrera: str = Field(description="Carrera a la que pertenece.")
    facultad: str = Field(description="Facultad a la que pertenece.")
    aula: str = Field(description="Aula o laboratorio.")
    docente_nombre: str | None = Field(default=None, description="Nombre del docente.")

    model_config = {"populate_by_name": True}


class AlumnoEnrollRequest(BaseModel):
    codigo: str = Field(description="Código del alumno que se matricula.")


class MateriaUpdate(BaseModel):
    nombre: str | None = Field(default=None, description="Nombre de la materia.")
    carrera: str | None = Field(default=None, description="Carrera a la que pertenece.")
    facultad: str | None = Field(default=None, description="Facultad a la que pertenece.")
    aula: str | None = Field(default=None, description="Aula o laboratorio.")
