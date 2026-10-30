from pydantic import BaseModel, EmailStr, Field, ConfigDict
from app.models.common import PyObjectId


class UsuarioLogin(BaseModel):
    codigo: str = Field(description="Código del usuario.")
    password: str = Field(description="Contraseña del usuario.")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "codigo": "COORD001",
                    "password": "tu_contraseña",
                }
            ]
        }
    )


class TokenResponse(BaseModel):
    access_token: str = Field(description="JWT para el botón **Authorize** o el header `Authorization: Bearer`.")
    token_type: str = Field(default="bearer", description="Siempre `bearer`.")
    rol: str = Field(description="`admin`, `coordinador`, `docente` o `alumno`.")
    nombre: str = Field(description="Nombre del usuario.")


class _UsuarioBaseCreate(BaseModel):
    codigo: str = Field(description="Código único del usuario; con él inicia sesión.")
    password: str = Field(description="Contraseña inicial.")
    nombre: str = Field(description="Nombre completo.")


class CoordinadorCreate(_UsuarioBaseCreate):
    pass


class DocenteCreate(_UsuarioBaseCreate):
    facultad: str = Field(description="Facultad del docente.")
    coordinador_id: str | None = Field(default=None, description="Coordinador a cargo. Solo lo manda el admin; un coordinador crea docentes a su cargo.")


class AlumnoCreate(_UsuarioBaseCreate):
    # El correo lo agrega el alumno después (PATCH /auth/me)
    carrera: str | None = Field(default=None, description="Carrera. Solo para coordinador o admin.")
    facultad: str | None = Field(default=None, description="Facultad. Solo para coordinador o admin.")
    materias_ids: list[str] = Field(default=[], description="Materias en las que queda matriculado al crearlo.")


class DatosAcademicosUpdate(BaseModel):
    """Los decide la coordinación: alumnos y docentes no pueden cambiárselos a sí mismos."""
    carrera: str | None = Field(default=None, description="Carrera.")
    facultad: str | None = Field(default=None, description="Facultad.")
    estatus_academico: str | None = Field(default=None, description="Estatus académico.")


class PerfilUpdate(DatosAcademicosUpdate):
    """Lo que cada usuario puede cambiar de sí mismo. El código y el rol no se tocan."""
    nombre: str | None = Field(default=None, min_length=1, description="Nombre completo.")
    correo: EmailStr | None = Field(default=None, description="Correo electrónico.")


class PasswordCambio(BaseModel):
    password_actual: str = Field(description="Contraseña vigente.")
    password_nueva: str = Field(min_length=1, description="Contraseña nueva.")


class PasswordReset(BaseModel):
    password_nueva: str = Field(min_length=1, description="Contraseña nueva.")


class UsuarioOut(BaseModel):
    """Lo que se expone hacia afuera: nunca password_hash ni face_embedding."""
    id: PyObjectId = Field(alias="_id", description="ObjectId del usuario.")
    codigo: str = Field(description="Código del usuario.")
    nombre: str = Field(description="Nombre completo.")
    rol: str = Field(description="`admin`, `coordinador`, `docente` o `alumno`.")
    correo: str | None = Field(default=None, description="Correo electrónico.")
    carrera: str | None = Field(default=None, description="Carrera.")
    estatus_academico: str | None = Field(default=None, description="Estatus académico.")
    facultad: str | None = Field(default=None, description="Facultad.")
    coordinador_id: str | None = Field(default=None, description="ObjectId del coordinador a cargo; solo en docentes.")

    model_config = {"populate_by_name": True}

class AlumnoEnMateriaOut(BaseModel):
    id: PyObjectId = Field(alias="_id", description="ObjectId del alumno.")
    codigo: str = Field(description="Código del alumno.")
    nombre: str = Field(description="Nombre completo.")
    carrera: str | None = Field(default=None, description="Carrera.")
    facultad: str | None = Field(default=None, description="Facultad.")

    model_config = {"populate_by_name": True}

"""
    {"codigo": "ADMIN001","password": "cambiar123"}

eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJBRE1JTjAwMSIsInVpZCI6IjZhYmFhYzgzZjFiMTYwMDc1MzhiNjdlNiIsInJvbCI6ImFkbWluIiwiZXhwIjoxNzkwNjQ3NzMxfQ.vg43hOjwI6ofG3cRUgJYsLy7RyQielXHKUmKFPNNV5Q

    {"codigo": "COORD001","password": "cambiar123"}

eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJDT09SRDAwMSIsInVpZCI6IjZhYmFhYzgyZjFiMTYwMDc1MzhiNjdlNSIsInJvbCI6ImNvb3JkaW5hZG9yIiwiZXhwIjoxNzkwNjQ4MDc2fQ.A5t7iPm9zHUBYB5Xpb9ChLdqcSdCvP-qOqMX6QkGNwo

    {"codigo": "DOC001","password": "cambiar123"}

eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJET0MwMDEiLCJ1aWQiOiI2YWJhYWM4M2YxYjE2MDA3NTM4YjY3ZTciLCJyb2wiOiJkb2NlbnRlIiwiZXhwIjoxNzkwNjQ4NDUxfQ.HrD6yp7LI7OWgJ87G4Pg8vh1Ij5ZfgUGGxGIwC0BFNY

"""
