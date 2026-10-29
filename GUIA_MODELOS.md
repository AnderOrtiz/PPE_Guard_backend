# Guía para entrenar los modelos de PPE Guard

Requisitos que debe cumplir un archivo de pesos (`.pt`) para que el backend lo pueda usar, por qué `best.pt` no funciona hoy, y qué necesita el modelo de medicina (`medicina.pt`).

---

## 1. Cómo usa el backend el modelo

Saber esto explica todos los requisitos de abajo:

1. Se carga con `YOLO(path)` y se usa con `model.track(...)` (ByteTrack), con `conf=0.50` e `iou=0.45`.
2. Se leen las detecciones de **`result.boxes`** (cajas normales, rectas). Cada detección se convierte en su **nombre de clase** (`result.names`).
3. En cada frame se busca la clase **`Person`** y se toma a la persona más grande (la más cercana a la cámara). Si en el frame no hay ningún `Person`, **ese frame no cuenta**.
4. Solo cuentan las prendas cuyo **centro cae dentro de la caja de esa persona** (con un 10 % de holgura, porque el casco o el gorro suelen salir por arriba).
5. Cada prenda requerida se compara **por nombre exacto** con la lista `ppe_requerido` del área:
   - Si aparece `X` → la prenda se ve puesta.
   - Si aparece `NO-X` → se ve la parte del cuerpo **sin** la prenda (cuenta como violación).
6. La revisión dura unos 6 segundos (unos 12 a 20 frames). Para dar una prenda por puesta, tiene que verse en **al menos 3 frames** y en más frames que su `NO-X`.

Prendas requeridas por área (catálogo en Mongo, `scripts/seed_inicializar.py`):

| Área | `ppe_requerido` | Archivo |
|---|---|---|
| `civil` | `Hardhat`, `Safety Vest` | `weights/civil.pt` |
| `medicina` | `Mask`, `Gloves`, `Gorro` | `weights/medicina.pt` |

---

## 2. Requisitos obligatorios para cualquier modelo

- [ ] **Tarea `detect`**, no `obb` ni `segment`. Partir de `yolo11n.pt`, `yolo11s.pt`, `yolov8s.pt`, etc., **no** de `yolo11n-obb.pt`.
- [ ] Incluir la clase **`Person`**, escrita así (con P mayúscula). Sin ella el backend descarta todos los frames.
- [ ] Los nombres de las prendas deben ser **idénticos** a los de `ppe_requerido`, con mayúsculas, espacios y guiones iguales. `casco` ≠ `Hardhat`, `Safety vest` ≠ `Safety Vest`.
- [ ] **Recomendado:** una clase `NO-<prenda>` para cada prenda (por ejemplo `NO-Hardhat`), con el prefijo exacto `NO-`. No es obligatoria, pero sin ella el sistema no distingue "no lleva la prenda" de "no se alcanza a ver".
- [ ] Entrenar con una versión de **ultralytics igual o anterior a la del backend (`8.4.53`)**, o avisar para actualizar el backend. Un `.pt` guardado con una versión más nueva puede no cargar.
- [ ] `imgsz=640`, que es lo que usa el backend.
- [ ] Etiquetar a **todas** las personas de cada imagen con `Person`, no solo a la que lleva el equipo.

---

## 3. Por qué `best.pt` no funciona y `civil.pt` sí

| | `civil.pt` (funciona) | `best.pt` (no funciona) |
|---|---|---|
| Arquitectura | YOLOv8s (11.1 M parámetros) | YOLO11n (2.7 M parámetros) |
| Tarea | `detect` | **`obb`** (cajas rotadas) |
| Clases | `Hardhat`, `Mask`, `NO-Hardhat`, `NO-Mask`, `NO-Safety Vest`, `Person`, `Safety Cone`, `Safety Vest`, `machinery`, `vehicle` | **`casco`, `chaleco`** |
| ultralytics | 8.3.214 | 8.4.190 (más nueva que la del backend) |

Problemas de `best.pt`, del más grave al menos grave:

1. **No tiene `Person`.** El backend no encuentra a nadie y descarta todos los frames, así que el alumno siempre sale con todo faltante.
2. **Es OBB.** Ultralytics deja las detecciones de un modelo OBB en `result.obb` y `result.boxes` queda vacío. El backend no recibe ninguna detección.
3. **Nombres en español.** `casco` y `chaleco` nunca coinciden con `Hardhat` y `Safety Vest`.
4. **No tiene clases `NO-`.** No se pueden contar violaciones.
5. **Versión de ultralytics más nueva** que la instalada en el backend.

> El mAP50 de 0.99 de `best.pt` es sobre solo 2 clases, así que no se puede comparar directamente con el 0.86 de `civil.pt` (10 clases).

### Para que un nuevo modelo de civil reemplace a `civil.pt`

Reentrenar con `task=detect` y al menos estas clases:

```
Person, Hardhat, NO-Hardhat, Safety Vest, NO-Safety Vest
```

> **No hace falta `Mask` ni `NO-Mask` en el modelo de civil.** El área de civil solo exige casco y chaleco. Esas clases aparecen en la tabla de arriba porque el `civil.pt` actual se entrenó con un dataset que ya las traía, pero el backend no las usa. La mascarilla solo se pide en el modelo de medicina (sección 4).

---

## 4. Modelo de medicina (`medicina.pt`)

Hoy **no existe**. Si se inicia una práctica de medicina, el hilo de detección falla con el primer alumno.

### Clases que debe tener

Mínimo obligatorio:

```
Person, Mask, Gloves, Gorro
```

Recomendado (agregar las negativas):

```
Person, Mask, NO-Mask, Gloves, NO-Gloves, Gorro, NO-Gorro
```

Atención a los nombres: `Mask`, `Gloves` y `Gorro` deben ir **exactamente así**, aunque mezclen inglés y español. Si prefieren otros nombres (por ejemplo `Cap` en vez de `Gorro`), avisen al backend para cambiar el catálogo. Lo importante es que el modelo y el catálogo usen el mismo nombre.

### Qué tomar en cuenta en el dataset

- **Guantes (`Gloves`):** es la prenda más difícil. Las manos son pequeñas y muchas veces quedan fuera de cuadro o detrás del cuerpo.
  - Incluir fotos con las manos a la vista, a la altura del pecho, que es como se le pedirá al alumno que se ponga frente a la cámara.
  - Etiquetar cada mano enguantada por separado.
  - Incluir guantes de varios colores (látex blanco, nitrilo azul o morado, negro) para que no aprenda solo un color.
  - Para `NO-Gloves`, etiquetar las manos descubiertas.
- **Cubrebocas (`Mask`):** incluir cubrebocas quirúrgicos, KN95 y de tela, en varios colores. Un cubrebocas puesto debajo de la nariz o en la barbilla debe etiquetarse como `NO-Mask`, no como `Mask`.
- **Gorro (`Gorro`):** gorro quirúrgico desechable y de tela. No confundirlo con gorras, capuchas ni cabello recogido, que deben ir como `NO-Gorro` si se usa esa clase. La caja puede salir un poco por arriba de la persona, y eso está bien: el backend da un 10 % de holgura.
- **Bata:** no está en `ppe_requerido`, así que no hace falta. Si se quiere agregar, avisar para incluirla en el catálogo.
- **Cada prenda debe quedar dentro de la caja `Person`.** Etiquetar a la persona de cuerpo completo o al menos de la cintura hacia arriba, de modo que la cabeza y las manos queden dentro de su caja.
- **Condiciones parecidas a las reales:** la cámara estará fija en un laboratorio, con el alumno a 1–2 m. Incluir fondos de laboratorio, luz de lámparas blancas y personas de frente y ligeramente de lado.
- **Balance:** un número parecido de ejemplos por clase, y suficientes imágenes de personas **sin** cada prenda.
- **Tamaño orientativo:** unas 300–500 instancias etiquetadas por clase como mínimo, con más para `Gloves`.

### Entrenamiento sugerido

```bash
yolo detect train model=yolo11s.pt data=dataset_medicina/data.yaml epochs=100 imgsz=640 batch=16
```

Ejemplo de `data.yaml`:

```yaml
path: dataset_medicina
train: images/train
val: images/val
names:
  0: Person
  1: Mask
  2: NO-Mask
  3: Gloves
  4: NO-Gloves
  5: Gorro
  6: NO-Gorro
```

Recomendación de tamaño: `s` (small) en vez de `n` (nano). Las prendas de medicina son pequeñas (manos, gorro), y en esos casos el modelo nano pierde muchas detecciones. El orden de los IDs da igual, porque el backend usa los nombres.

---

## 5. Antes de entregar un `.pt`: cómo comprobarlo

Correr esto y revisar la salida:

```python
from ultralytics import YOLO
m = YOLO("weights/medicina.pt")
print(m.task)    # debe imprimir: detect
print(m.names)   # debe incluir 'Person' y los nombres exactos de ppe_requerido

r = m("foto_de_prueba.jpg")[0]
print(r.boxes)   # no debe ser None ni estar vacío en una foto con una persona equipada
```

Checklist de entrega:

- [ ] `m.task == "detect"`
- [ ] `Person` está en `m.names`
- [ ] Todos los nombres de `ppe_requerido` del área están en `m.names`, escritos igual
- [ ] Las clases `NO-...` usan el prefijo exacto `NO-`
- [ ] Con una persona de prueba, cada prenda sale con confianza ≥ 0.50
- [ ] El archivo se llama `civil.pt` o `medicina.pt` y va en `weights/`
- [ ] Indicar la versión de ultralytics con la que se entrenó
