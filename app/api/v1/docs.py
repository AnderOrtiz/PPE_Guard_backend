"""Textos y ayudas para la documentación de Swagger UI (/docs)."""
from typing import Annotated

from fastapi import Path

from app.models.common import ErrorResponse, ErrorValidacion

DESCRIPCION_API = """
Backend de **PPE Guard**: pasa lista por reconocimiento facial y verifica con visión
por computadora que cada alumno lleve la indumentaria (EPP) exigida en su práctica.

## Cómo autenticarse

1. Llama a `POST /api/v1/auth/login` con tu código y contraseña.
2. Copia el `access_token` de la respuesta.
3. Pulsa **Authorize**, pégalo (sin escribir `Bearer`) y confirma.

El token dura 8 horas por defecto y se renueva con `POST /api/v1/auth/refresh`.

`GET /api/v1/stream` y `GET /static/evidence/...` también aceptan el token como `?token=`,
porque un `<img>` del navegador no puede mandar headers.

## Roles

| Rol | Alcance |
|---|---|
| `admin` | Todo lo de `coordinador` y `docente`, sin limitarse a un cargo. No accede a los endpoints de `alumno`. |
| `coordinador` | Docentes, materias y alumnos a su cargo. |
| `docente` | Las materias que imparte y sus prácticas. |
| `alumno` | Sus propias materias, asistencias y evidencias. |

## Errores

Los errores responden `{"detail": "mensaje"}`. En un `422`, `detail` es el mensaje o, si falló
la validación del cuerpo o de los parámetros, la lista de campos con error.

## Flujo de una práctica

1. `POST /api/v1/practicas` enciende la cámara y la detección. Solo puede haber una práctica activa.
2. Cuando se reconoce a un alumno, el WebSocket emite `estudiante_identificado`.
3. `POST /api/v1/practicas/{practica_id}/confirmar` inicia su revisión de indumentaria, de 6 segundos.
4. Al terminar, se guarda la asistencia y se emite `asistencia_registrada`. La práctica vuelve a identificar.
5. `POST /api/v1/practicas/{practica_id}/end` finaliza la práctica y apaga la cámara si nadie más la usa.

## WebSocket de detecciones

Swagger UI no puede probar WebSockets, así que este canal se documenta aquí:

```
ws://127.0.0.1:8000/ws/detections?token=<access_token>
```

Requiere rol `docente`, `coordinador` o `admin`; si no, se cierra con el código `1008`.
El servidor solo emite: lo que mande el cliente se ignora. Todos los mensajes son JSON
e incluyen `evento` y `timestamp`.

| `evento` | Cuándo | Campos |
|---|---|---|
| `estado_inicial` | Al conectarse | `practica_id`, `fase`, `identificado`, `alumno_id`, `segundos_restantes` |
| `estudiante_identificado` | Se reconoce a un alumno | `practica_id`, `alumno_id`, `nombre`, `codigo`, `confianza` |
| `fase_cambiada` | Cambia la fase | `practica_id`, `fase` (`identificacion` o `indumentaria`) y, en `indumentaria`, `alumno_id` |
| `detecciones_frame` | Cada análisis durante la revisión | `frame_width`, `frame_height`, `items` |
| `asistencia_registrada` | Termina la revisión | `practica_id`, `alumno_id`, `cumplio_indumentaria`, `faltantes`, `evidencia_url` |

Cada elemento de `items` trae `class_name`, `confidence`, `track_id`, `is_violation` y `bbox_norm`:
`[x1, y1, x2, y2]` en proporción del frame, de 0 a 1.

Sin práctica activa, los campos de `estado_inicial` llegan en `null`.
"""

TAGS = [
    {"name": "health", "description": "Estado del servicio."},
    {"name": "auth", "description": "Inicio de sesión y perfil del usuario autenticado."},
    {"name": "usuarios", "description": "Alta y administración de coordinadores, docentes y alumnos."},
    {"name": "materias", "description": "Materias y matrícula de sus alumnos."},
    {"name": "practices", "description": "Catálogo de indumentaria exigida por área. No confundir con `practicas`."},
    {"name": "practicas", "description": "Sesiones de laboratorio: iniciar, confirmar identificaciones y finalizar."},
    {"name": "asistencias", "description": "Asistencias registradas y reporte por práctica."},
    {"name": "alumno", "description": "Lo que un alumno consulta de sí mismo."},
    {"name": "coordinacion", "description": "Indicadores del panel de coordinación."},
    {"name": "camara", "description": "Vista previa de la cámara para enrolar alumnos."},
    {"name": "stream", "description": "Video en vivo de la cámara del servidor."},
    {"name": "evidencias", "description": "Imágenes de los incumplimientos de indumentaria."},
]

MateriaId = Annotated[str, Path(description="ObjectId de la materia.")]
PracticaId = Annotated[str, Path(description="ObjectId de la práctica.")]
UsuarioId = Annotated[str, Path(description="ObjectId del usuario.")]
AlumnoId = Annotated[str, Path(description="ObjectId del alumno.")]

_ERRORES = {
    400: "No se envió ningún campo para actualizar.",
    401: "Falta el token, es inválido o expiró.",
    403: "Tu rol o tu cargo no te permiten esta acción.",
    404: "El recurso indicado no existe.",
    409: "La operación entra en conflicto con el estado actual.",
    422: "Algún dato o id tiene un formato inválido.",
}


def errores(*codigos: int | tuple[int, str]) -> dict:
    """Arma `responses` de un endpoint. Cada código usa su descripción genérica,
    o la propia si se pasa como (codigo, descripcion)."""
    respuestas = {}
    for item in codigos:
        codigo, descripcion = item if isinstance(item, tuple) else (item, _ERRORES[item])
        modelo = ErrorValidacion if codigo == 422 else ErrorResponse
        respuestas[codigo] = {"model": modelo, "description": descripcion}
    return respuestas
