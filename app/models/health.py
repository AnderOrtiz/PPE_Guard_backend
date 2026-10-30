from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(description="`ok` si el servicio responde.")
    mongo: str = Field(description="`connected` si MongoDB responde.")