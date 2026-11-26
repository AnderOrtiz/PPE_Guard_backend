## Pasos para obtener los resultados
**Paso 0: borrar los datos de prueba**

```bash
rm -rf datos/piloto2
```

**Paso 1: con casco y chaleco puestos**

```bash
python -m scripts.piloto_indumentaria capturar --condicion completo --n 20
```

**Paso 2: sin casco, con chaleco**

```bash
python -m scripts.piloto_indumentaria capturar --condicion sin_casco --faltan Hardhat --n 15
```

**Paso 3: con casco, sin chaleco**

```bash
python -m scripts.piloto_indumentaria capturar --condicion sin_chaleco --faltan "Safety Vest" --n 15
```

**Paso 4: resultados**

```bash
python -m scripts.piloto_indumentaria analizar
```

**Paso 5: tabla completa de revisiones**

```bash
cat datos/piloto2/revisiones.csv
```

---
# `piloto_indumentaria.py` —  Medición del veredicto de indumentaria
Script para obtener datos de las **pruebas piloto 2 y 3** (`PROPUESTAS_PRUEBAS_PILOTO.md`) usando solo la cámara y el modelo YOLO, **sin levantar el backend completo** (sin FastAPI, Mongo ni DeepFace).

Ubicación: `scripts/piloto_indumentaria.py`

---
## 1. Qué hace

El sistema decide si un alumno cumple con la indumentaria de seguridad. Este script comprueba **qué tan bien decide**, comparando su veredicto con lo que el observador sabe que la persona lleva puesto.

Por cada revisión:

1. **El observador declara la verdad de terreno antes de empezar** (qué prenda falta realmente).
2. Se abre la cámara y se descartan los primeros 10 frames para que ajuste la exposición.
3. Durante **6 segundos** se analiza un frame cada **0.3 s** con `detect(frame, area="civil")`, la misma función YOLO del backend, midiendo cuánto tarda cada inferencia.
4. Se **emula el veredicto del backend** con estas reglas (de `GUIA_MODELOS.md`, sección 1):
   - Se toma la `Person` más grande del frame. Si no hay ninguna, **ese frame no cuenta**.
   - Solo cuentan las prendas cuyo **centro cae dentro de la caja de esa persona**, con un 10 % de holgura.
   - Una prenda se da por puesta si se ve en **al menos 3 frames** y en **más frames que su `NO-X`**.
   - Lo que no se confirma queda como **faltante** (en caso de duda se reprueba).
5. Se guarda todo en `datos/piloto2/` y se imprime un resumen de la revisión.

El área evaluada es `civil`, con las prendas requeridas `Hardhat` y `Safety Vest`.

---

## 2. Requisitos

- Ejecutar **desde la raíz del repo** (`PPE_Guard_backend/`), con el entorno virtual activado.
- Que existan `weights/civil.pt` y `app/services/yolo_service.py`.
- Cámara disponible. En macOS, la terminal necesita permiso de cámara (Ajustes del Sistema → Privacidad y seguridad → Cámara).
- Cierra cualquier otro programa que use la cámara (por ejemplo, el backend con una práctica activa).
- Opcional: `psutil` para registrar CPU y memoria. Normalmente ya viene con ultralytics.

---

## 3. Uso

El script tiene dos subcomandos: `capturar` y `analizar`.

> **Ojo con zsh:** al pegar comandos en la terminal, **no incluyas líneas que empiecen con `#`**. En el zsh interactivo de macOS el `#` no cuenta como comentario y puede dar `parse error`. Pega los comandos de uno en uno.

### 3.1 Capturar

```bash
python -m scripts.piloto_indumentaria capturar --condicion completo --n 10
python -m scripts.piloto_indumentaria capturar --condicion sin_casco --faltan Hardhat --n 10
python -m scripts.piloto_indumentaria capturar --condicion sin_chaleco --faltan "Safety Vest" --n 10
python -m scripts.piloto_indumentaria capturar --condicion nada --faltan "Hardhat,Safety Vest" --n 5
```

Antes de cada revisión el script muestra qué condición declaraste y espera un **Enter**. Colócate frente a la cámara con el atuendo correcto, pulsa Enter y espera unos 8 segundos.

| Opción | Obligatoria | Descripción |
|---|:-:|---|
| `--condicion` | Sí | Etiqueta del escenario (por ejemplo `completo`, `sin_casco`). Se usa para agrupar resultados. |
| `--faltan` | No | Prendas que **realmente** faltan, separadas por coma. Solo admite `Hardhat` y `Safety Vest`. **Vacío = lleva todo**. |
| `--n` | No | Número de revisiones seguidas (por defecto 1). |
| `--camara` | No | Índice de la cámara (por defecto 0). |
| `--espera` | No | Segundos entre el Enter y el inicio (por defecto 2). |
| `--fotos` | No | Guarda el último frame de cada revisión en `datos/piloto2/fotos/`. Contiene rostros. |

Cada revisión imprime una línea como:

```
✔ R004: sistema=no (faltan ['Hardhat']) | real=no | frames=14 útiles=14 | lat media=212.4 ms
```

`✔` significa que el sistema coincidió con la verdad de terreno y `✘` que no. La primera revisión de la sesión lo indica con *(incluye carga del modelo)*.

### 3.2 Analizar

```bash
python -m scripts.piloto_indumentaria analizar
```

Para probar otros parámetros **sin volver a capturar**:

```bash
python -m scripts.piloto_indumentaria analizar --confirm-frames 2 --margen 0.2
```

| Opción | Por defecto | Descripción |
|---|---|---|
| `--confirm-frames` | 3 | Frames mínimos para dar una prenda por puesta. |
| `--margen` | 0.10 | Holgura de la caja `Person`. |

El análisis recalcula el veredicto desde `frames.jsonl` con los parámetros indicados y los compara con la verdad de terreno guardada.

---

## 4. Archivos que genera

Todo queda en `datos/piloto2/` y se acumula entre ejecuciones:

| Archivo | Contenido |
|---|---|
| `revisiones.csv` | Una fila por revisión: id (`R001`, `R002`…), fecha UTC, condición, verdad de terreno, veredicto del sistema, acierto, frames, frames útiles, conteo de frames por prenda (`pos_*` / `neg_*`), duración, fps, latencia media y máxima, CPU, memoria y si fue la primera de la sesión. |
| `frames.jsonl` | Detecciones crudas de cada frame (clase, confianza, `track_id`, caja) y su latencia. Permite recalibrar sin recapturar. |
| `fotos/` | Solo con `--fotos`. Último frame de cada revisión, sin anotar. |

> **Privacidad:** las fotos contienen rostros. Úsalas solo con consentimiento y revisa la sección de ética de `PROPUESTAS_PRUEBAS_PILOTO.md` antes de conservarlas o compartirlas.

---

## 5. Qué mide

### Piloto 2 — acierto del veredicto

La verdad de terreno es lo que declaras con `--faltan`. Positivo = "cumple".

| Métrica | Qué significa |
|---|---|
| **Matriz de confusión** | Cruce de `cumple_real` × `cumple_sistema`. |
| **Exactitud del veredicto** | Revisiones donde sistema y observador coinciden, entre el total. |
| **Falso aprobado (FAR)** | El sistema dice "cumple" y en realidad **no** cumple, entre las revisiones donde el observador dice "no". **Es el error grave**: deja pasar a alguien sin equipo. |
| **Falso reprobado (FRR)** | El sistema dice "no cumple" y en realidad sí cumple, entre las revisiones donde el observador dice "sí". |
| **Lista de faltantes exacta** | Porcentaje de revisiones donde los faltantes del sistema son idénticos a los reales. |
| **Exactitud por prenda** | Para `Hardhat` y `Safety Vest`, cuántas veces el sistema acertó si faltaba o no. |
| **Tabla por escenario** | Exactitud, FAR, FRR y frames útiles (media y mínimo) por cada `--condicion`. |

**Frames útiles** son los frames donde se detectó al menos una `Person`. Si son pocos, el veredicto sale como "faltante" por falta de evidencia, no porque la prenda no esté.

Reporta el FAR y el FRR por separado: un solo número de exactitud esconde cuál de los dos errores ocurrió.

### Piloto 3 — latencia y capacidad (solo inferencia YOLO)

| Métrica | Qué significa |
|---|---|
| **Latencia por frame (caliente)** | p50, p90 y máximo en ms, con el modelo ya cargado. |
| **Primera inferencia de la sesión** | Incluye la carga del modelo. Se reporta aparte para no sesgar la media. |
| **Frames analizados por revisión** | Teórico máximo: 6 s / 0.3 s = 20. Menos si cada inferencia tarda. |
| **Frames por segundo analizados** | Frames analizados entre la duración real de la revisión. |
| **Duración real de la revisión** | Puede pasar de 6 s si una inferencia se alarga. |
| **CPU y memoria** | CPU media durante la revisión (puede superar 100 % con varios núcleos) y RSS del proceso. |

---

## 6. Flujo recomendado

1. Haz una prueba corta para confirmar que todo funciona:
   ```bash
   python -m scripts.piloto_indumentaria capturar --condicion completo --n 1
   python -m scripts.piloto_indumentaria analizar
   ```
2. Captura las tandas, cambiando de atuendo entre un comando y otro. Tamaño orientativo según `PROPUESTAS_PRUEBAS_PILOTO.md`:

   | Escenario | `--condicion` | `--faltan` | Revisiones |
   |---|---|---|---:|
   | Casco y chaleco puestos | `completo` | (vacío) | 20 |
   | Falta solo el casco | `sin_casco` | `Hardhat` | 15 |
   | Falta solo el chaleco | `sin_chaleco` | `"Safety Vest"` | 15 |

   Si el piloto lo pide, añade escenarios difíciles (casco en la mano, compañero en cuadro, contraluz) con su propia `--condicion`.
3. Ejecuta `analizar` y guarda la salida para el informe.
4. Para calibrar, cambia `--confirm-frames` y `--margen` **una variable a la vez**. Según el documento, calibra con el 60 % de las muestras y evalúa la configuración ganadora con el 40 % restante.

---

## 7. Limitaciones

- **El veredicto es una réplica.** Reimplementa la lógica descrita en la documentación, no ejecuta el código real de `PpeReview`. Antes de citar cifras en el informe, compara algunas revisiones con el backend real. En particular, se asumió que el 10 % de holgura se aplica por cada lado de la caja.
- **La latencia es solo de YOLO.** El backend real también corre DeepFace y el hilo del orquestador, así que sus tiempos serán mayores. Estas cifras son un mínimo, no la latencia de extremo a extremo.
- **`CONFIDENCE_THRESHOLD` no se recalibra aquí.** Vive dentro de `yolo_service`. Para probar otro valor hay que editarlo y volver a capturar.
- **No cubre el Piloto 1** (reconocimiento facial) ni el flujo de confirmación del docente. Eso requiere el backend completo y el capturador de eventos descrito en la documentación de pilotos.
- **Área `medicina` no soportada**, porque `weights/medicina.pt` no existe.
- **El script mide un solo alumno a la vez**, el que ocupa la caja `Person` más grande.

---

## 8. Problemas comunes

| Síntoma | Causa y solución |
|---|---|
| `ModuleNotFoundError: No module named 'app'` | Se ejecutó fuera de la raíz del repo o sin `-m`. Usa `python -m scripts.piloto_indumentaria ...` desde la raíz. |
| `zsh: parse error near ')'` | Se pegaron líneas con `#`. Pega solo los comandos. |
| `error: the following arguments are required: cmd` | Falta el subcomando (`capturar` o `analizar`). |
| `No hay datos. Corre primero el comando 'capturar'.` | Aún no hay `datos/piloto2/`. Ejecuta primero `capturar`. |
| `No se analizó ningún frame` | La cámara está ocupada o sin permiso. Cierra otros programas y revisa los permisos de la terminal. |
| `--faltan solo admite [...]` | Nombre de prenda mal escrito. Usa exactamente `Hardhat` y `Safety Vest`. |
| Todos los veredictos salen como "faltante" | Probablemente no se ve a la persona (pocos frames útiles). Aléjate un poco para que cuerpo y cabeza queden en cuadro y revisa la columna `frames_utiles`. |
| Quieres empezar de cero | Borra la carpeta `datos/piloto2/`. |
