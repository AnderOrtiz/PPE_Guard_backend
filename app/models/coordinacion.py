from pydantic import BaseModel, Field


class ResumenCoordinacion(BaseModel):
    materias: int = Field(description="Materias a cargo.")
    materias_nuevas: int = Field(description="Materias creadas en los últimos 7 días.")
    materias_lab_activo: int = Field(description="Materias con alguna práctica en los últimos 7 días.")
    docentes: int = Field(description="Docentes a cargo.")
    docentes_activos_hoy: int = Field(description="Docentes que iniciaron una práctica hoy (día del servidor).")
    alumnos: int = Field(description="Alumnos distintos matriculados en esas materias; para el admin, todos los alumnos.")
