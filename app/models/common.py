from typing import Annotated
from pydantic import BaseModel, BeforeValidator, Field

# Mongo usa ObjectId internamente, pero eso no es serializable a JSON tal cual.
# Este tipo le dice a Pydantic: "conviértelo a string en cuanto lo veas".
PyObjectId = Annotated[str, BeforeValidator(str)]


class ErrorResponse(BaseModel):
    detail: str = Field(description="Mensaje del error.")


class ErrorValidacion(BaseModel):
    detail: str | list[dict] = Field(description="Mensaje del error, o la lista de campos que no pasaron la validación.")