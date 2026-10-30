from pydantic import BaseModel, Field


class VistaPreviaEstado(BaseModel):
    activa: bool = Field(description="Si está encendida la vista previa de quien pregunta.")
    camara_encendida: bool = Field(description="Si la cámara está encendida; puede seguir en `true` con la vista previa apagada (práctica en curso).")
    gracia_segundos: int = Field(description="Segundos sin lecturas de `/stream` antes de que la vista previa se apague sola.")
