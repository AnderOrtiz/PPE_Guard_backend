from app.models.usuario import AlumnoEnMateriaOut
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.database import get_database
from app.api.v1.dependencies import require_role, get_current_user
from app.api.v1.docs import AlumnoId, MateriaId, errores
from app.models.materia import MateriaCreate, MateriaInDB, MateriaUpdate, AlumnoEnrollRequest

router = APIRouter()


@router.post(
    "/materias",
    response_model=MateriaInDB,
    dependencies=[Depends(require_role("coordinador"))],
    summary="Crear una materia",
    responses=errores(
        401,
        (403, "Tu rol no lo permite, o el docente está fuera de tu cargo."),
        (404, "El docente indicado no existe."),
        422,
    ),
)
async def crear_materia(data: MateriaCreate, user: dict = Depends(get_current_user)):
    """La materia queda a cargo del coordinador del docente y sin alumnos.

    **Roles:** `coordinador` (solo para sus docentes) o `admin`.
    """
    if not ObjectId.is_valid(data.docente_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="docente_id inválido")

    database = get_database()
    docente = await database["usuarios"].find_one({"_id": ObjectId(data.docente_id), "rol": "docente"})
    if docente is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="El docente indicado no existe")

    # La materia queda a cargo del coordinador del docente: un coordinador solo
    # puede crearla para sus propios docentes. El admin, para cualquiera.
    if user["rol"] == "coordinador" and docente["coordinador_id"] != user["user_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="No puedes crear una materia para un docente fuera de tu cargo")

    doc = data.model_dump()
    doc["coordinador_id"] = docente["coordinador_id"]
    doc["alumnos_ids"] = []

    result = await database["materias"].insert_one(doc)
    creada = await database["materias"].find_one({"_id": result.inserted_id})
    return MateriaInDB(**creada)


@router.get("/materias",
            response_model=list[MateriaInDB],
            dependencies=[Depends(require_role("coordinador", "docente"))],
            summary="Listar materias",
            responses=errores(401, 403))
async def listar_materias(
    docente_id: str | None = Query(default=None, description="Solo las de este docente. Aplica a `coordinador` y `admin`."),
    user: dict = Depends(get_current_user),
):
    """Un `docente` ve las que imparte; un `coordinador`, las de su cargo; el `admin`, todas."""
    database = get_database()

    if user["rol"] == "docente":
        filtro = {"docente_id": user["user_id"]}
    elif user["rol"] == "coordinador":
        filtro = {"coordinador_id": user["user_id"]}
        if docente_id is not None:
            filtro["docente_id"] = docente_id
    else:  # admin
        filtro = {}
        if docente_id is not None:
            filtro["docente_id"] = docente_id

    cursor = database["materias"].find(filtro)
    return [MateriaInDB(**doc) async for doc in cursor]


@router.get(
    "/materias/{materia_id}",
    response_model=MateriaInDB,
    dependencies=[Depends(require_role("coordinador", "docente"))],
    summary="Obtener una materia",
    responses=errores(401, 403, (404, "La materia indicada no existe."), 422),
)
async def obtener_materia(materia_id: MateriaId, user: dict = Depends(get_current_user)):
    """**Roles:** `docente` de la materia, `coordinador` a cargo o `admin`."""
    if not ObjectId.is_valid(materia_id):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="materia_id inválido")

    database = get_database()
    materia = await database["materias"].find_one({"_id": ObjectId(materia_id)})
    if materia is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="La materia indicada no existe")

    if user["rol"] == "docente" and materia["docente_id"] != user["user_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No puedes ver una materia que no impartes")
    if user["rol"] == "coordinador" and materia["coordinador_id"] != user["user_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No puedes ver una materia fuera de tu cargo")

    return MateriaInDB(**materia)


@router.patch(
    "/materias/{materia_id}",
    response_model=MateriaInDB,
    dependencies=[Depends(require_role("coordinador"))],
    summary="Actualizar una materia",
    responses=errores(400, 401, 403, (404, "La materia indicada no existe."), 422),
)
async def actualizar_materia(materia_id: MateriaId, data: MateriaUpdate, user: dict = Depends(get_current_user)):
    """Cambia solo los campos enviados. El área y el docente no se pueden cambiar.

    **Roles:** `coordinador` a cargo o `admin`.
    """
    if not ObjectId.is_valid(materia_id):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="materia_id inválido")

    database = get_database()
    materia = await database["materias"].find_one({"_id": ObjectId(materia_id)})
    if materia is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="La materia indicada no existe")

    if user["rol"] == "coordinador" and materia["coordinador_id"] != user["user_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No puedes modificar una materia fuera de tu cargo")

    cambios = data.model_dump(exclude_none=True)
    if not cambios:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se envió ningún campo para actualizar")

    await database["materias"].update_one({"_id": ObjectId(materia_id)}, {"$set": cambios})

    actualizada = await database["materias"].find_one({"_id": ObjectId(materia_id)})
    return MateriaInDB(**actualizada)


@router.post(
    "/materias/{materia_id}/alumnos",
    response_model=MateriaInDB,
    dependencies=[Depends(require_role("coordinador", "docente"))],
    summary="Matricular a un alumno",
    responses=errores(
        401,
        403,
        (404, "La materia no existe, o no hay un alumno con ese código."),
        (409, "El alumno ya está matriculado en esta materia."),
        422,
    ),
)
async def matricular_alumno_en_materia(
    materia_id: MateriaId,
    data: AlumnoEnrollRequest,
    user: dict = Depends(get_current_user),
):
    """Matricula a un alumno existente por su código. **Roles:** `docente` de la materia, `coordinador` a cargo o `admin`."""
    if not ObjectId.is_valid(materia_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="materia_id inválido")

    database = get_database()
    materia = await database["materias"].find_one({"_id": ObjectId(materia_id)})
    if materia is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="La materia indicada no existe")

    # Verifica autoridad sobre ESTA materia específica. El admin no entra en
    # ninguna de estas dos condiciones (su rol nunca es "docente" ni "coordinador"
    # literalmente), así que pasa sin restricción adicional.
    if user["rol"] == "docente" and materia["docente_id"] != user["user_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="No puedes matricular alumnos en una materia que no impartes")
    if user["rol"] == "coordinador" and materia["coordinador_id"] != user["user_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="No puedes matricular alumnos en una materia fuera de tu cargo")

    alumno = await database["usuarios"].find_one({"codigo": data.codigo, "rol": "alumno"})
    if alumno is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="No existe un alumno con ese código")

    alumno_id = str(alumno["_id"])
    if alumno_id in materia["alumnos_ids"]:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="El alumno ya está matriculado en esta materia")

    await database["materias"].update_one(
        {"_id": ObjectId(materia_id)},
        {"$push": {"alumnos_ids": alumno_id}},
    )

    actualizada = await database["materias"].find_one({"_id": ObjectId(materia_id)})
    return MateriaInDB(**actualizada)


@router.get(
    "/materias/{materia_id}/alumnos",
    response_model=list[AlumnoEnMateriaOut],
    dependencies=[Depends(require_role("coordinador", "docente"))],
    summary="Listar los alumnos de una materia",
    responses=errores(401, 403, (404, "La materia indicada no existe."), 422),
)
async def listar_alumnos_en_materia(materia_id: MateriaId):
    """**Roles:** `docente`, `coordinador` o `admin`. A diferencia del resto de `materias`, no exige que la materia sea del usuario."""
    if not ObjectId.is_valid(materia_id):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="materia_id inválido")

    database = get_database()

    materia = await database["materias"].find_one({"_id": ObjectId(materia_id)})

    if materia is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="La materia indicada no existe")

    alumnos_ids = materia["alumnos_ids"]

    cursor = database["usuarios"].find(
        {"_id": {"$in": [ObjectId(aid) for aid in alumnos_ids]}})
    return [AlumnoEnMateriaOut(**doc) async for doc in cursor]


@router.delete(
    "/materias/{materia_id}/alumnos/{alumno_id}",
    response_model=MateriaInDB,
    dependencies=[Depends(require_role("coordinador", "docente"))],
    summary="Quitar a un alumno de una materia",
    responses=errores(401, 403, (404, "La materia no existe, o el alumno no está matriculado en ella."), 422),
)

async def eliminar_alumno_de_materia(
    materia_id: MateriaId,
    alumno_id: AlumnoId,
    user: dict = Depends(get_current_user),
):
    """Le quita la matrícula; el usuario sigue existiendo. **Roles:** `docente` de la materia, `coordinador` a cargo o `admin`."""
    if not ObjectId.is_valid(materia_id):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="materia_id inválido")

    database = get_database()

    materia = await database["materias"].find_one({"_id": ObjectId(materia_id)})

    if materia is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="La materia indicada no existe")

    if user["rol"] == "docente" and materia["docente_id"] != user["user_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No puedes modificar una materia que no impartes")
    if user["rol"] == "coordinador" and materia["coordinador_id"] != user["user_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No puedes modificar una materia fuera de tu cargo")

    if alumno_id not in materia["alumnos_ids"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ese alumno no está matriculado en esta materia")

    await database["materias"].update_one(
        {"_id": ObjectId(materia_id)},
        {"$pull": {"alumnos_ids": alumno_id}},
    )

    actualizada = await database["materias"].find_one({"_id": ObjectId(materia_id)})
    return MateriaInDB(**actualizada)
