# Integrar el modelo de medicina y ajustar los parámetros

Qué hacer cuando llegue `medicina.pt`, cómo se integra al backend sin tocar código, y la tabla completa de parámetros ajustables (modelo, cámara, revisión de indumentaria, reconocimiento facial y autenticación) con su ruta exacta en el repo.

> Para **entrenar** el modelo (clases requeridas, dataset, `data.yaml`) la referencia es [`GUIA_MODELOS.md`](GUIA_MODELOS.md). Este documento empieza donde ese termina: ya tienes el `.pt` en la mano.

---

## Índice

1. [Resumen: los tres pasos](#1-resumen-los-tres-pasos)
2. [Estado actual del repo](#2-estado-actual-del-repo)
3. [Integrar `medicina.pt` paso a paso](#3-integrar-medicinapt-paso-a-paso)
4. [Probar el modelo antes de usarlo en una práctica](#4-probar-el-modelo-antes-de-usarlo-en-una-práctica)
5. [Checklist de integración](#5-checklist-de-integración)
6. [Tabla de parámetros](#6-tabla-de-parámetros)
7. [Cómo se ajusta cada tipo de parámetro](#7-cómo-se-ajusta-cada-tipo-de-parámetro)
8. [Recetas de ajuste por síntoma](#8-recetas-de-ajuste-por-síntoma)
9. [Diagnóstico de fallos comunes](#9-diagnóstico-de-fallos-comunes)
10. [Agregar un área nueva (referencia)](#10-agregar-un-área-nueva-referencia)

---

## 1. Resumen: los tres pasos

```
1. Copiar el archivo a  weights/medicina.pt
2. Reiniciar el backend
3. Verificar que las clases del modelo coincidan con ppe_requerido de Mongo
```

No hay que tocar código. `weights/medicina.pt` **ya está declarado** en `app/core/config.py:20`:

```python
MODEL_PATHS: dict[str, str] = {
    "civil": "weights/civil.pt",
    "medicina": "weights/medicina.pt",   # ← el archivo es lo único que falta
}
```

El nombre del archivo, la ruta y la clave `"medicina"` ya existen; lo único ausente es el `.pt`.

---

## 2. Estado actual del repo

| Pieza | Estado | Dónde |
|---|---|---|
| Ruta del modelo `medicina` | ✅ declarada | `app/core/config.py:20-23` |
| Archivo `weights/medicina.pt` | ❌ **no existe** | `weights/` |
| Catálogo de prendas del área | ✅ en Mongo (`Mask`, `Gloves`, `Gorro`) | colección `practices`, sembrado por `scripts/seed_inicializar.py:16-19` |
| Área `medicina` en materias | ✅ aceptada | `app/models/materia.py` (`Literal["civil", "medicina"]`) |
| Carga y caché del modelo | ✅ genérica por área | `app/services/yolo_service.py:11-29` |

Consecuencia mientras el archivo no exista: la práctica **sí se crea**, la cámara **sí enciende**, la identificación facial **sí funciona**, pero al confirmar al primer alumno el hilo de detección muere con `FileNotFoundError` y la práctica queda muda (ver [fallos comunes](#9-diagnóstico-de-fallos-comunes)).

---

## 3. Integrar `medicina.pt` paso a paso

### 3.1 Copiar el archivo

```bash
cd /Users/ander-ortiz/Desktop/PPE_Guard_backend
cp ~/Descargas/medicina.pt weights/medicina.pt
ls -lh weights/
```

Debe quedar junto a `civil.pt`:

```
weights/
├── best.pt       # OBB, no usable (ver GUIA_MODELOS.md §3)
├── civil.pt
└── medicina.pt
```

La ruta es **relativa al directorio de trabajo** del proceso (los `path` de `MODEL_PATHS` no son absolutos). El backend se levanta desde la raíz del repo, así que `weights/medicina.pt` funciona. Si lo levantas desde otra carpeta, falla con `No se encontró el archivo de pesos`.

### 3.2 Confirmar que el área tiene el catálogo correcto

El backend exige que los nombres de clase del modelo coincidan **exactamente** con `ppe_requerido` del área en Mongo. Consulta lo que hay:

```bash
mongosh "mongodb://<usuario>:<password>@localhost:27017/<db>?authSource=admin" \
  --quiet --eval 'db.practices.find({}, {area:1, ppe_requerido:1, _id:0}).toArray()'
```

Esperado para medicina:

```json
{ "area": "medicina", "ppe_requerido": ["Mask", "Gloves", "Gorro"] }
```

Si tu modelo usa otros nombres (`Cap` en vez de `Gorro`, `FaceMask` en vez de `Mask`), hay dos caminos:

**Opción A — renombrar el modelo** (recomendado): en el `data.yaml` usa los nombres que ya espera el backend y reentrena/reexporta.

**Opción B — cambiar el catálogo en Mongo.** No hay endpoint para esto y `scripts/seed_inicializar.py` **no sobrescribe** si la colección ya tiene documentos (`scripts/seed_inicializar.py:44-48`). Se hace directo:

```bash
mongosh "mongodb://<usuario>:<password>@localhost:27017/<db>?authSource=admin" --quiet --eval '
  db.practices.updateOne(
    { area: "medicina" },
    { $set: { ppe_requerido: ["Mask", "Gloves", "Cap"] } }
  )'
```

> Los nombres `NO-<prenda>` **no van** en `ppe_requerido`. El backend los deriva solo: si la lista pide `Mask`, busca `Mask` y `NO-Mask` en las detecciones (`app/services/compliance_engine.py:56`).

### 3.3 Reiniciar el backend

**Obligatorio.** Los modelos se cargan una sola vez y se guardan en un caché de proceso (`app/services/yolo_service.py:8`):

```python
_loaded_models: dict[str, YOLO] = {}   # un modelo cargado por área, nunca se recarga desde disco
```

Reemplazar `weights/medicina.pt` con el servidor corriendo **no tiene efecto** hasta reiniciar el proceso.

```bash
# como se levanta según el readme
uvicorn app.main:app --reload
```

Ojo con `--reload`: como vigila el directorio de trabajo, copiar el `.pt` puede disparar un reload **a mitad de la copia**, y el modelo se cargaría truncado. Copia primero, y luego reinicia a mano (`Ctrl+C` y volver a levantar) para tener un estado limpio.

### 3.4 Probar el flujo completo

1. Login como docente (`POST /api/v1/auth/login`).
2. Verifica que exista una materia con `area: "medicina"` y alumnos matriculados **con rostro enrolado**.
3. `POST /api/v1/practicas` con el `materia_id` → enciende cámara y empieza a identificar.
4. En el front, cuando aparezca el alumno identificado, confirmar (`POST /api/v1/practicas/{id}/confirmar`).
5. Durante 6 segundos llegan eventos `detecciones_frame` por WebSocket; al final, `asistencia_registrada` con `faltantes` y `cumplio_indumentaria`.
6. `POST /api/v1/practicas/{id}/end` para cerrar.

---

## 4. Probar el modelo antes de usarlo en una práctica

Dos verificaciones: sin cámara (barata) y con cámara (la que importa).

### 4.1 Verificar el archivo

```bash
python - <<'PY'
from ultralytics import YOLO
m = YOLO("weights/medicina.pt")
print("task:", m.task)          # debe ser: detect
print("names:", m.names)        # debe incluir Person, Mask, Gloves, Gorro
PY
```

Si `task` no es `detect`, el backend no recibe nada: `yolo_service` lee `result.boxes`, y un modelo `obb`/`segment` deja eso vacío o distinto.

### 4.2 Probar contra la cámara real, sin levantar una práctica

Este script usa exactamente el mismo código que producción (`CameraService` + `detect`), así que si aquí se ve bien, en la práctica se verá igual:

```bash
cd /Users/ander-ortiz/Desktop/PPE_Guard_backend
python - <<'PY'
import time
from app.services.camera_service import camera_service
from app.services.yolo_service import detect

camera_service.adquirir("prueba")
try:
    time.sleep(1)  # deja que el hilo de captura entregue un frame
    for i in range(5):
        frame = camera_service.get_latest_frame()
        print(f"--- frame {i} ---")
        for d in detect(frame, area="medicina"):
            print(f"  {d['class_name']:<14} conf={d['confidence']:.2f} track={d['track_id']}")
        time.sleep(1)
finally:
    camera_service.liberar("prueba")
PY
```

Qué observar:

- Aparece `Person` → el modelo sirve como base.
- Aparecen `Mask`, `Gloves`, `Gorro` con `conf ≥ 0.50` → el umbral actual los deja pasar.
- Aparecen `NO-Mask`, etc. → las clases negativas están bien nombradas.
- **Nada de `Person`** → el backend descartará todos los frames y todos los alumnos saldrán con todo faltante.

> Alternativa sin cámara: pasar un `numpy.ndarray` con `cv2.imread("foto.jpg")` a `detect(frame, area="medicina")`. Sirve para validar nombres y confianzas con una foto fija.

---

## 5. Checklist de integración

Antes de decir "medicina ya funciona":

- [ ] `weights/medicina.pt` existe y pesa lo esperado (no es un `.pt` de 0 bytes ni un LFS pointer)
- [ ] `m.task == "detect"`
- [ ] `Person` está en `m.names`, con mayúscula
- [ ] Cada nombre de `ppe_requerido` de medicina está en `m.names`, **escrito igual** (mayúsculas, espacios, guiones)
- [ ] Las clases negativas usan el prefijo exacto `NO-`
- [ ] El modelo se entrenó con `ultralytics <= 8.4.53` (la del `requirements.txt`)
- [ ] Reiniciaste el backend después de copiar el archivo
- [ ] Una práctica de medicina identifica, confirma y registra asistencia sin que el WebSocket se quede mudo
- [ ] Si el alumno lleva todo, `faltantes` sale `[]`; si le falta algo, se genera evidencia en `static/evidence/<fecha>/`

---

## 6. Tabla de parámetros

Cuatro bloques: **modelo**, **cámara y stream**, **revisión de indumentaria**, **reconocimiento facial y sesión**.

Leyenda de la columna *Cómo se ajusta*:

- **`.env`** → variable de entorno; el valor por defecto está en `app/core/config.py`. Formato `.env`, en mayúsculas, sin el prefijo de clase.
- **Código** → constante en un archivo `.py`; requiere editar y reiniciar.
- **Mongo** → documento en base de datos; se cambia con `mongosh`, sin reiniciar.

### 6.1 Modelo de detección

| Parámetro | Qué hace | Valor actual | Cómo se ajusta | Ruta / ubicación |
|---|---|---|---|---|
| `MODEL_PATHS` | Mapa área → archivo de pesos. Define qué `.pt` se carga para cada área. Si el área no está, `get_model` lanza `ValueError`. | `{"civil": "weights/civil.pt", "medicina": "weights/medicina.pt"}` | `.env` (JSON) o código | `app/core/config.py:20-23` |
| `CONFIDENCE_THRESHOLD` | Confianza mínima para aceptar una detección (`conf` de `model.track`). Bajar = más detecciones y más falsos positivos. | `0.50` | `.env` | `app/core/config.py:24`, usado en `app/services/yolo_service.py:40` |
| `IOU_THRESHOLD` | Umbral de IoU del NMS: cuánto pueden solaparse dos cajas antes de descartar una. Bajar = menos cajas duplicadas y más supresiones. | `0.45` | `.env` | `app/core/config.py:25`, usado en `app/services/yolo_service.py:41` |
| `imgsz` | Resolución a la que se redimensiona cada frame antes de inferir. **No se pasa explícitamente**, así que rige el default de Ultralytics: `640`. | `640` (implícito) | Código (agregar argumento) | `app/services/yolo_service.py:36-43` |
| `tracker` | Algoritmo de seguimiento que asigna `track_id` a cada objeto entre frames. | `"bytetrack.yaml"` | Código | `app/services/yolo_service.py:39` |
| `persist` | Mantiene el estado del tracker entre llamadas. Si se pone en `False`, cada frame reinicia los IDs de seguimiento. | `True` | Código | `app/services/yolo_service.py:38` |
| Frame de calentamiento | Inferencia inicial con un frame negro de 640×640 para pagar el costo del primer `predict` al cargar, no en el primer frame real. | `np.zeros((640,640,3), uint8)` | Código (o quitar) | `app/services/yolo_service.py:22-25` |
| Caché de modelos | Diccionario en memoria que impide recargar un `.pt` ya cargado. Es la razón por la que hay que **reiniciar** al cambiar pesos. | `_loaded_models = {}` | Código | `app/services/yolo_service.py:8` |
| `ultralytics` | Versión del runtime de inferencia. Un `.pt` guardado con una versión más nueva puede no cargar. | `8.4.53` | `requirements.txt` | `requirements.txt` |

### 6.2 Cámara y video

| Parámetro | Qué hace | Valor actual | Cómo se ajusta | Ruta / ubicación |
|---|---|---|---|---|
| `camera_index` | Índice del dispositivo que abre OpenCV. `0` es la cámara integrada o la primera USB; `1`, `2`… para otras. | `0` | Código (instancia global) | `app/services/camera_service.py:7` y `:129` |
| `target_fps` | Frecuencia a la que el hilo de captura toma frames y duerme lo que sobra. Bajarlo alivia CPU pero reduce detecciones por revisión. | `8` | Código | `app/services/camera_service.py:7` |
| `resize_width` | Ancho al que se reescala cada frame (mantiene proporción). Define la resolución que ve el modelo y el stream. | `640` | Código | `app/services/camera_service.py:7`, aplicado en `:103-109` |
| `warmup_frames` | Frames que se descartan al abrir la cámara, mientras ajusta exposición. | `10` | Código | `app/services/camera_service.py:67`, `:132` |
| `STREAM_INTERVAL_SECONDS` | Intervalo entre frames del stream MJPEG. Está fijado a `1/8` para calcar `target_fps`; si cambias uno, cambia el otro. | `0.125` (8 fps) | Código | `app/api/v1/endpoints/stream.py:16` |
| `SIN_FRAMES_MAX_SEGUNDOS` | Tiempo sin recibir imagen antes de cortar el stream (cámara encendida pero sin entregar). | `5` | Código | `app/api/v1/endpoints/stream.py:17` |
| `GRACIA_SIN_LECTURA_SEGUNDOS` | Segundos que una vista previa aguanta sin que el navegador lea frames antes de apagarse sola y liberar la cámara. | `10` | Código | `app/services/vista_previa.py:8` |
| `VIGILANCIA_INTERVALO_SEGUNDOS` | Cada cuánto el vigilante revisa vistas previas huérfanas. | `1` | Código | `app/services/vista_previa.py:9` |

### 6.3 Revisión de indumentaria (el "cerebro" de la evaluación)

| Parámetro | Qué hace | Valor actual | Cómo se ajusta | Ruta / ubicación |
|---|---|---|---|---|
| `REVIEW_DURATION_SECONDS` | Duración de la ventana de evaluación tras confirmar al alumno. Es fija: no depende de si el alumno se mueve. | `6` | Código | `app/services/practica_orchestrator.py:16` |
| `INDUMENTARIA_INTERVAL_SECONDS` | Cada cuánto se corre una detección durante la revisión. Con 6 s y 0.3 s salen ~20 evaluaciones por alumno. | `0.3` | Código | `app/services/practica_orchestrator.py:15` |
| `IDENTIFICATION_INTERVAL_SECONDS` | Cada cuánto se busca un rostro en fase de identificación. Subirlo reduce CPU; bajarlo acelera la identificación. | `1.0` | Código | `app/services/practica_orchestrator.py:14` |
| `REVIEW_CONFIRM_FRAMES` | En cuántos frames debe verse una prenda para darla por puesta. Subir = más estricto y más lento de confirmar. | `3` | Código | `app/services/compliance_engine.py:2`, usado en `:62` |
| `REVIEW_PERSON_MARGIN` | Holgura alrededor de la caja de la persona donde aún se aceptan prendas, como fracción de su tamaño. Existe porque el casco y el gorro asoman por arriba. | `0.10` (10 %) | Código | `app/services/compliance_engine.py:3`, aplicado en `:51` |
| Clase de persona | Nombre exacto de la clase que el backend usa como referencia. Todas las prendas se miden contra su caja. | `"Person"` | Código | `app/services/compliance_engine.py:46` |
| Prefijo de violación | Prefijo que marca "se ve la parte del cuerpo sin la prenda". | `"NO-"` | Código | `app/services/compliance_engine.py:56`, `app/services/practica_orchestrator.py:144` |
| `ppe_requerido` | Lista de prendas exigidas por área; se compara por nombre exacto contra el modelo. | civil: `Hardhat`, `Safety Vest` · medicina: `Mask`, `Gloves`, `Gorro` | Mongo (`practices`) | `scripts/seed_inicializar.py:16-19` |
| `EVIDENCE_DIR` | Carpeta donde se guarda la captura del incumplimiento, con recuadro y texto de faltantes. | `static/evidence` | Código | `app/services/evidence_service.py:7`, creada en `app/main.py:19` |

**Cómo decide una prenda** (`app/services/compliance_engine.py:45-63`):

1. Toma la persona más grande del frame (la más cercana a la cámara).
2. Expande su caja un `REVIEW_PERSON_MARGIN`.
3. Solo cuenta detecciones cuyo **centro** caiga dentro de esa zona.
4. Cuenta `X` como "puesta" si aparece en `≥ REVIEW_CONFIRM_FRAMES` frames.
5. `missing()` devuelve la prenda si tiene menos frames de los requeridos **o** si los frames con `NO-X` son iguales o más que los de `X`.

### 6.4 Reconocimiento facial y sesión

| Parámetro | Qué hace | Valor actual | Cómo se ajusta | Ruta / ubicación |
|---|---|---|---|---|
| `FACE_MODEL_NAME` | Modelo de embeddings faciales de DeepFace. Cambiarlo invalida **todos** los rostros ya enrolados. | `"Facenet"` (128 dimensiones) | Código | `app/services/face_service.py:7` |
| `FACE_DETECTOR_BACKEND` | Detector de rostros usado al calcular el embedding. | `"opencv"` | Código | `app/services/face_service.py:8` |
| `SIMILARITY_THRESHOLD` | Similitud de coseno mínima para aceptar una identificación. Subir = menos falsos positivos y más alumnos sin identificar. | `0.60` | Código | `app/services/face_service.py:34`, usado en `:57` |
| `PRACTICA_RECUPERABLE_HORAS` | Al arrancar, una práctica que quedó `activa` solo se reanuda si empezó hace menos de estas horas; si no, se cierra. | `8` | `.env` | `app/core/config.py:29`, usado en `app/services/practica_lifecycle.py:45` |
| `JWT_EXPIRE_MINUTES` | Vigencia del token de sesión. | `480` (8 h) | `.env` | `app/core/config.py:34`, usado en `app/core/security.py:18` |
| `JWT_ALGORITHM` | Algoritmo de firma del token. | `"HS256"` | `.env` | `app/core/config.py:33` |
| `FACE_EMBEDDING_KEY` | Clave Fernet que cifra los rostros en Mongo. **Si se pierde o cambia, hay que reenrolar a todos los alumnos.** | — (obligatoria, sin default) | `.env` | `app/core/config.py:38` |
| `DEBUG` | Modo de depuración de FastAPI. | `False` | `.env` | `app/core/config.py:7` |
| `ALLOWED_ORIGINS` | Orígenes permitidos por CORS. Si el front corre en otro puerto, la API falla desde el navegador. | `["http://localhost:5173", "http://localhost:3000"]` | `.env` (JSON) o código | `app/core/config.py:9-12` |

---

## 7. Cómo se ajusta cada tipo de parámetro

### 7.1 Vía `.env` (sin tocar código)

`app/core/config.py:4` declara `env_file=".env"`, así que cualquier campo de `Settings` se puede sobrescribir desde el `.env` de la **raíz del repo** (y desde variables de entorno reales del proceso, que tienen prioridad).

```dotenv
# Umbrales del modelo: más permisivo
CONFIDENCE_THRESHOLD=0.40
IOU_THRESHOLD=0.50

# Recuperación de prácticas tras un reinicio
PRACTICA_RECUPERABLE_HORAS=4

# Sesión más corta
JWT_EXPIRE_MINUTES=240
```

Los campos de tipo `dict` / `list` van como **JSON en una línea**:

```dotenv
# Apuntar medicina a otro archivo, o cambiar el orden del mapa
MODEL_PATHS={"civil": "weights/civil.pt", "medicina": "weights/medicina_v2.pt"}

# Un solo origen (front en 5173)
ALLOWED_ORIGINS=["http://localhost:5173"]
```

Notas:

- Los nombres van **en mayúsculas** y sin el prefijo de la clase `Settings`.
- `extra="ignore"` (`app/core/config.py:4`): una variable mal escrita **no da error**, simplemente se ignora. Si un cambio "no hace nada", revisa el nombre.
- Los campos sin valor por defecto (`MONGO_*`, `JWT_SECRET_KEY`, `FACE_EMBEDDING_KEY`) son obligatorios: si falta uno, el backend no arranca.
- **Requiere reinicio**: `Settings` se instancia una sola vez en `app/core/config.py:41`.

### 7.2 Vía código (constantes)

Las constantes de `camera_service.py`, `stream.py`, `vista_previa.py`, `practica_orchestrator.py`, `compliance_engine.py` y `face_service.py` no leen del `.env`. Se editan en el archivo y se reinicia el servidor.

Si vas a iterar mucho sobre umbrales, la mejora natural es moverlos a `Settings` y agregarlos al `.env` (mismo patrón que `CONFIDENCE_THRESHOLD`), para no tocar código en cada prueba.

### 7.3 Vía Mongo (catálogo de prendas)

`ppe_requerido` vive en la colección `practices` y se lee en cada arranque de práctica (`app/api/v1/endpoints/practicas.py:53-56`). Los cambios aplican **sin reiniciar** y sin tocar el código: en la siguiente práctica ya rigen.

Requiere que el nombre coincida con el del modelo. Ver [§3.2](#32-confirmar-que-el-área-tiene-el-catálogo-correcto).

---

## 8. Recetas de ajuste por síntoma

| Síntoma | Qué mover | Dirección | Riesgo |
|---|---|---|---|
| Un alumno **con** la prenda sale como faltante | `CONFIDENCE_THRESHOLD` → bajar a `0.40` | ↓ | Más falsos positivos: aparece la prenda donde no está |
| Se detectan prendas de **otra persona** o del fondo | `REVIEW_PERSON_MARGIN` → bajar a `0.05` | ↓ | Se rechazan cascos y gorros que asoman por arriba |
| Detecciones intermitentes: a veces sí, a veces no | `REVIEW_CONFIRM_FRAMES` → bajar a `2`, o `REVIEW_DURATION_SECONDS` → subir a `8` | ↓ / ↑ | Más permisivo; confirma prendas que solo pasaron un instante |
| Alguien **sin** la prenda pasa como cumplido | `REVIEW_CONFIRM_FRAMES` → subir a `4`-`5` | ↑ | Alumnos con la prenda puesta también empiezan a fallar |
| Dos cajas para el mismo objeto | `IOU_THRESHOLD` → bajar a `0.35` | ↓ | Suprime objetos realmente distintos y cercanos |
| El cuello de botella es CPU | `target_fps` → `5`, `INDUMENTARIA_INTERVAL_SECONDS` → `0.5` | ↓ / ↑ | Menos evaluaciones por alumno; revisión más débil |
| Se identifica a la persona equivocada | `SIMILARITY_THRESHOLD` → `0.68` | ↑ | Alumnos legítimos dejan de identificarse |
| No identifica a un alumno concreto | `SIMILARITY_THRESHOLD` → `0.55` | ↓ | Riesgo de confundir alumnos parecidos |
| El stream se ve con retraso | Verificar `resize_width` y `target_fps`; no subir `STREAM_INTERVAL_SECONDS` sin bajar `target_fps` | — | Desincroniza stream y detección |

> Regla general: **cambia un parámetro a la vez** y valida con varias personas y condiciones de luz distintas. Los umbrales de un modelo no se ajustan con una sola prueba.

---

## 9. Diagnóstico de fallos comunes

### `No se encontró el archivo de pesos: weights/medicina.pt`

`get_model` valida `Path(path).exists()` (`app/services/yolo_service.py:17-18`). Causas:

- El archivo no está, o está con otro nombre (`medicina (1).pt`, `medicina_v2.pt`).
- El backend se levantó desde otra carpeta y la ruta relativa no resuelve.
- `MODEL_PATHS` en el `.env` apunta a otra ruta que la real.

### `No hay modelo configurado para el área 'medicina'`

`settings.MODEL_PATHS.get(area)` devolvió `None` (`app/services/yolo_service.py:14-16`). Casi siempre es un `MODEL_PATHS` mal escrito en el `.env` que **reemplazó** el mapa completo en lugar de agregar una clave.

### La práctica queda muda después de confirmar

Síntoma: la identificación funciona, confirmas al alumno, y no llegan más eventos `detecciones_frame`; tampoco `asistencia_registrada`.

Causa: `detect()` lanzó una excepción dentro del hilo del orquestador (`_tick_indumentaria` → `get_model`) y el hilo murió **sin apagar la práctica**. El traceback aparece en la consola del servidor, pero al cliente no le llega nada. La cámara queda tomada y la práctica sigue `activa` en Mongo.

Qué hacer:

1. `POST /api/v1/practicas/{id}/end` para liberar cámara y cerrar la práctica.
2. Corregir la causa (archivo faltante, modelo ilegible).
3. Reiniciar el backend si reemplazaste pesos (por el caché).

### Carga el modelo pero todos salen con todo faltante

- No hay clase `Person` en el modelo → `compliance_engine` descarta **todos** los frames (`:46-48`).
- El modelo es `obb`/`segment` → `result.boxes` viene vacío.
- Los nombres no coinciden exactamente con `ppe_requerido`.

Diagnóstico rápido: el script de [§4.2](#42-probar-contra-la-cámara-real-sin-levantar-una-práctica).

### `Error` al cargar un `.pt` recién entrenado

Versión de `ultralytics` del modelo más nueva que `8.4.53`. O reexportas con una versión compatible, o subes la del `requirements.txt` (y validas que `civil.pt` siga cargando).

---

## 10. Agregar un área nueva (referencia)

Por si algún día es `quimica` y no solo medicina. Cuatro puntos, todos obligatorios:

| # | Archivo | Qué agregar |
|---|---|---|
| 1 | `app/core/config.py:20-23` | `"quimica": "weights/quimica.pt"` en `MODEL_PATHS` |
| 2 | `app/models/materia.py` | `"quimica"` en el `Literal` de `area` (aparece en `MateriaCreate`, `MateriaInDB` y `MateriaAlumnoOut`) |
| 3 | `scripts/seed_inicializar.py:16-19` | Entrada en `CATALOGO_PPE` con su `ppe_requerido` |
| 4 | Mongo (`practices`) | Insertar el documento si la base ya estaba sembrada (el seed no sobrescribe) |

Extra opcional: `app/models/practice.py` documenta `area` como "`civil` o `medicina`" en la descripción del campo; conviene actualizar el texto.

---

## Referencias cruzadas

- [`GUIA_MODELOS.md`](GUIA_MODELOS.md) — requisitos del `.pt`, construcción del dataset, `data.yaml`, checklist de entrega del modelo.
- [`DOCUMENTACION_TECNICA.md`](DOCUMENTACION_TECNICA.md) — por qué el sistema funciona así (detección, revisión, umbrales).
- [`ARQUITECTURA_BACKEND.md`](ARQUITECTURA_BACKEND.md) — capas, flujos y máquina de estados del orquestador.
