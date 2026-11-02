# PPE Guard: arquitectura y funcionamiento del backend

Descripción técnica del backend de PPE Guard: de qué piezas se compone, cómo se conectan y qué ocurre en cada operación del sistema. Está escrita para servir de base a una investigación.

Describe el código en el commit `d1942f4` (30 de octubre de 2026). Los valores numéricos y los nombres de módulos salen del código fuente; las versiones, del entorno `yolo` donde se ejecuta. Si algo contradice al código, vale el código.

**Documentos relacionados:** `DOCUMENTACION_TECNICA.md` (decisiones de diseño y todos los parámetros ajustables), `FRONTEND.md` (contrato de la API), `GUIA_MODELOS.md` (requisitos de los modelos YOLO) y `readme.md` (instalación).

## Índice

1. [Resumen](#1-resumen)
2. [Tecnologías](#2-tecnologías)
3. [Arquitectura general](#3-arquitectura-general)
4. [Arranque y apagado](#4-arranque-y-apagado)
5. [Modelo de datos](#5-modelo-de-datos)
6. [Autenticación y autorización](#6-autenticación-y-autorización)
7. [Captura de video](#7-captura-de-video)
8. [Reconocimiento facial](#8-reconocimiento-facial)
9. [Detección de indumentaria](#9-detección-de-indumentaria)
10. [Flujos completos](#10-flujos-completos)
11. [Concurrencia](#11-concurrencia)
12. [Comunicación con el cliente](#12-comunicación-con-el-cliente)
13. [Seguridad y privacidad](#13-seguridad-y-privacidad)
14. [Limitaciones](#14-limitaciones)
15. [Alcance de la evidencia](#15-alcance-de-la-evidencia)
16. [Anexo: API REST](#16-anexo-api-rest)

---

## 1. Resumen

PPE Guard registra la asistencia a prácticas de laboratorio y verifica que cada alumno lleve el equipo de protección personal (EPP, o *PPE* en inglés) que exige su área. Combina dos modelos de visión por computadora:

| Pregunta | Técnica | Modelo |
|---|---|---|
| ¿Quién es el alumno? | Reconocimiento facial por comparación de vectores | Facenet, mediante DeepFace |
| ¿Qué prendas lleva? | Detección de objetos en imágenes | YOLO, mediante Ultralytics |

El proceso combina automatización y supervisión humana:

1. El docente inicia una práctica y el servidor enciende su cámara.
2. El sistema reconoce el rostro del alumno frente a la cámara, comparándolo solo con los matriculados en esa materia.
3. El docente confirma la identificación. **Sin esta confirmación no se registra nada.**
4. Durante 6 segundos, el sistema analiza varios frames y decide qué prendas lleva el alumno.
5. Se guarda una asistencia con el resultado y, si falta alguna prenda, una imagen de evidencia.

**La cámara es la del servidor.** El navegador nunca captura ni envía imágenes: solo recibe el video y los resultados. Por eso el backend y la cámara deben estar en el mismo equipo.

---

## 2. Tecnologías

| Función | Tecnología | Versión instalada |
|---|---|---|
| Lenguaje | Python | 3.11.16 |
| API REST y WebSocket | FastAPI, sobre el servidor ASGI Uvicorn | 0.136.3 |
| Validación de datos | Pydantic | 2.13.5 |
| Base de datos | MongoDB, con el cliente asíncrono de PyMongo | Mongo 8, PyMongo 4.17.0 |
| Captura y procesamiento de imagen | OpenCV | 4.11.0.86 |
| Reconocimiento facial | DeepFace con Facenet, sobre TensorFlow | DeepFace 0.0.101, TensorFlow 2.21.0 |
| Detección de objetos | Ultralytics YOLO, sobre PyTorch | Ultralytics 8.4.53, PyTorch 2.3.1 |
| Seguimiento de objetos | ByteTrack, incluido en Ultralytics | — |
| Contraseñas | bcrypt | 5.0.0 |
| Tokens de sesión | PyJWT, con HS256 | 2.14.0 |
| Cifrado de rostros | Fernet, de `cryptography` | 50.0.2 |
| Contenedores | Docker Compose: MongoDB y Mongo Express | — |

Docker Compose solo levanta la base de datos y su panel de administración. El backend corre directamente en el equipo, donde tiene acceso a la cámara.

El cliente es una aplicación web en React que vive fuera de este repositorio.

---

## 3. Arquitectura general

### Vista de componentes

```
 Navegador (React)                 Servidor (un solo proceso)
┌───────────────┐      ┌──────────────────────────────────────────────────────┐
│               │ REST │  Endpoints FastAPI ───────────────────────┐          │
│  Pantallas    │◄────►│  (dependencies.py: token y roles)         │          │
│               │      │        │                                  ▼          │
│               │  WS  │        │ inicia/detiene           ┌──────────────┐    │
│  Eventos      │◄─────│  ConnectionManager                │   MongoDB    │    │
│               │      │        ▲                          │  (Docker)    │    │
│               │      │        │ eventos                  └──────────────┘    │
│               │      │        │                                  ▲          │
│               │      │  PracticaOrchestrator ── asistencias ─────┘          │
│               │      │  (hilo propio)                                       │
│               │      │    │      │      │                                   │
│               │      │    ▼      ▼      ▼                                   │
│               │      │ Facenet  YOLO  PpeReview ──► evidencias (disco)      │
│               │      │    ▲      ▲                                          │
│               │      │    └──┬───┘                                          │
│               │ MJPEG│       │ último frame                                 │
│  <img> video  │◄─────│  /stream ◄── CameraService (hilo propio) ◄── cámara  │
└───────────────┘      └──────────────────────────────────────────────────────┘
```

### Capas

El código se organiza en cuatro capas:

| Capa | Carpeta | Responsabilidad |
|---|---|---|
| Entrada | `app/api/v1/endpoints/`, `app/websockets/` | Recibir peticiones, comprobar permisos, consultar la base y responder |
| Contratos | `app/models/` | Definir con Pydantic qué entra y qué sale de la API |
| Lógica | `app/services/` | Cámara, modelos de visión, reglas de cumplimiento y ciclo de la práctica |
| Infraestructura | `app/core/` | Configuración, base de datos, seguridad, cifrado, puente entre hilos y apagado |

La separación no es estricta en dos puntos:

- Los endpoints consultan MongoDB directamente. La única función de repositorio es `asistencia_repository.py`, con la que el orquestador guarda resultados.
- El orquestador, de la capa de lógica, emite sus eventos usando `websockets/manager.py`, de la capa de entrada.

### Conexiones entre módulos

| Módulo | Qué hace | Usa | Lo usan |
|---|---|---|---|
| `main.py` | Crea la app, registra rutas y controla arranque y apagado | Routers, `database`, `practica_lifecycle` | Uvicorn |
| `endpoints/practicas.py` | Inicia, confirma y finaliza prácticas | `practica_lifecycle`, `practica_registry` | Cliente |
| `practica_lifecycle.py` | Arranca orquestadores y recupera prácticas tras un reinicio | `face_service`, `practica_orchestrator`, `practica_registry` | `practicas.py`, `main.py` |
| `practica_registry.py` | Guarda en memoria los orquestadores activos | — | Endpoints, WebSocket, `main.py` |
| `practica_orchestrator.py` | Ejecuta el ciclo de identificación y revisión | Todos los servicios de visión, `manager`, `async_bridge` | `practica_lifecycle.py` |
| `camera_service.py` | Es dueño de la cámara y entrega el último frame | OpenCV | Orquestador, `stream.py`, `vista_previa.py`, `usuarios.py` |
| `face_service.py` | Calcula y compara embeddings faciales | DeepFace, `cifrado` | Orquestador, `usuarios.py` |
| `yolo_service.py` | Carga modelos y detecta objetos | Ultralytics | Orquestador |
| `compliance_engine.py` | Decide qué prendas faltan (`PpeReview`) | — | Orquestador |
| `evidence_service.py` | Dibuja y guarda la imagen de evidencia | OpenCV | Orquestador |
| `vista_previa.py` | Enciende la cámara durante el enrolamiento | `camera_service` | `camara.py`, `stream.py` |
| `websockets/manager.py` | Envía eventos a todos los clientes conectados | `async_bridge` | Orquestador, `websockets/router.py` |
| `core/async_bridge.py` | Permite a un hilo ejecutar tareas en el bucle asíncrono | asyncio | `manager`, orquestador |

---

## 4. Arranque y apagado

### Antes de arrancar

`scripts/seed_inicializar.py` prepara una base vacía con lo que la API no permite crear: el primer administrador y el catálogo de indumentaria por área.

### Arranque

La función `lifespan` de `main.py` ejecuta, en orden:

1. Se conecta a MongoDB, hace un `ping` y crea los índices. Si falla, el servidor no arranca.
2. Registra el bucle asíncrono principal, que después usan los hilos para comunicarse con él.
3. Empieza a vigilar las señales de apagado (`SIGINT` y `SIGTERM`).
4. Busca prácticas que quedaron activas y decide si reanudarlas o cerrarlas.

Además, `settings` exige las variables obligatorias de `.env` al importarse, y `cifrado.py` construye el objeto Fernet. Sin `JWT_SECRET_KEY`, `FACE_EMBEDDING_KEY` o los datos de MongoDB, el proceso no inicia.

Los modelos de visión **no** se cargan al arrancar, sino la primera vez que se usan.

### Recuperación tras un reinicio

Una práctica existe en dos lugares: su registro en MongoDB, que es duradero, y su orquestador en memoria, que se pierde al reiniciar. Al arrancar, `recuperar_practica_activa()` reconcilia ambos:

| Situación | Acción |
|---|---|
| Es la más reciente, tiene menos de 8 horas y se puede reanudar | Se reanuda en fase de identificación |
| Tiene más de 8 horas | Se marca como finalizada |
| No se puede reanudar (sin materia, sin catálogo o sin cámara) | Se marca como finalizada |
| Hay otra activa más reciente | Se marca como finalizada |

Una revisión de indumentaria que estuviera en curso se pierde.

### Apagado

1. Se detienen los orquestadores. Las prácticas siguen "activas" en MongoDB para poder reanudarlas.
2. Se olvidan las vistas previas y se libera la cámara.
3. Se cierra la conexión con MongoDB.

Uvicorn espera a que terminen las conexiones antes de ejecutar estos pasos, y un stream de video no termina por sí solo. Por eso `core/apagado.py` anota la señal de apagado y `/stream` se corta al verla.

---

## 5. Modelo de datos

MongoDB guarda cinco colecciones. Las relaciones se guardan como el texto del `ObjectId` y la aplicación las resuelve con consultas adicionales: no se usan `$lookup` ni integridad referencial.

```
usuarios.coordinador_id   ──►  usuarios (coordinador)    solo en docentes
materias.docente_id       ──►  usuarios (docente)
materias.coordinador_id   ──►  usuarios (coordinador)
materias.alumnos_ids[]    ──►  usuarios (alumno)
materias.area             ──►  practices.area
practicas.materia_id      ──►  materias
practicas.docente_id      ──►  usuarios (docente)
asistencias.practica_id   ──►  practicas
asistencias.alumno_id     ──►  usuarios (alumno)
```

| Colección | Contenido | Campos principales | Índices |
|---|---|---|---|
| `usuarios` | Los cuatro roles, en una sola colección | `codigo`, `password_hash`, `rol`, `nombre`, `correo`, `carrera`, `facultad`, `estatus_academico`, `coordinador_id` (docentes), `face_embedding` (alumnos) | `codigo` (único) |
| `materias` | Asignaturas y su matrícula | `nombre`, `area`, `carrera`, `facultad`, `aula`, `docente_id`, `coordinador_id`, `alumnos_ids` | `docente_id`, `coordinador_id` |
| `practices` | Catálogo: qué se exige en cada área | `area`, `nombre`, `ppe_requerido` | — |
| `practicas` | Cada sesión de laboratorio | `materia_id`, `docente_id`, `fecha`, `hora_inicio`, `hora_fin`, `estado` | `materia_id` |
| `asistencias` | Resultado de cada alumno revisado | `practica_id`, `alumno_id`, `hora_identificacion`, `cumplio_indumentaria`, `faltantes`, `evidencia_url` | `practica_id`, `alumno_id` |

### Catálogo inicial

| Área | Prendas exigidas |
|---|---|
| `civil` | `Hardhat`, `Safety Vest` |
| `medicina` | `Mask`, `Gloves`, `Gorro` |

### Decisiones relevantes

- **La ausencia no se guarda.** Solo hay un documento en `asistencias` si el alumno fue confirmado. Los ausentes se calculan en el reporte, comparando la matrícula con las asistencias.
- **`hora_identificacion` es el momento de la confirmación del docente**, no el del reconocimiento.
- **La matrícula es una lista dentro de la materia**, lo que permite cargar rápidamente los candidatos de una práctica.
- **El coordinador de una materia se copia del docente** al crearla, en vez de resolverse en cada consulta.
- **Las imágenes de evidencia están en disco.** MongoDB guarda solo su ruta, con la forma `/static/evidence/<fecha UTC>/<practica_id>-<alumno_id>.jpg`.

---

## 6. Autenticación y autorización

### Autenticación

1. `POST /auth/login` busca al usuario por `codigo` y verifica su contraseña con bcrypt.
2. Devuelve un JWT firmado con HS256, válido por 8 horas (`JWT_EXPIRE_MINUTES = 480`), con el código (`sub`), el id (`uid`), el rol (`rol`) y la expiración (`exp`).
3. Cada petición lo envía en el header `Authorization: Bearer`. El video y las evidencias también lo aceptan como `?token=`, y el WebSocket solo de esa forma, porque el navegador no permite enviar headers en esos casos.

El servidor no guarda sesiones: valida cada token con su firma y su fecha, sin consultar la base. Por eso un token no se puede revocar, y un cambio de rol no se aplica hasta que se renueva o expira.

### Autorización

Se aplica en dos niveles:

**Por rol.** `require_role(...)` es una dependencia de FastAPI que rechaza la petición con `403` si el rol no está permitido. El `admin` hereda los permisos de `coordinador` y `docente`, pero no los de `alumno`.

**Por pertenencia.** Dentro del endpoint se comprueba que el recurso sea del usuario:

| Rol | Alcance |
|---|---|
| `admin` | Todo el sistema |
| `coordinador` | Materias con su `coordinador_id`, sus docentes y los alumnos de esas materias |
| `docente` | Materias con su `docente_id`, sus prácticas y los alumnos matriculados en ellas |
| `alumno` | Sus propias materias, asistencias y evidencias |

Existe una excepción: `GET /materias/{id}/alumnos` comprueba el rol pero no la pertenencia (ver sección 14).

---

## 7. Captura de video

`CameraService` es una instancia única que administra el dispositivo físico. Su diseño responde a dos problemas.

### Evitar el retraso acumulado

Un hilo lee la cámara a 8 frames por segundo, reduce cada frame a 640 píxeles de ancho y **sobrescribe el anterior**. No hay cola. Quien pide un frame recibe una copia del más reciente.

Si el análisis es más lento que la cámara, se saltan frames y no se acumula retraso: el sistema siempre analiza el presente. Un `Lock` protege el frame compartido entre el hilo que escribe y los que leen.

### Compartir un único dispositivo

La cámara puede ser necesaria para una práctica y para una vista previa de enrolamiento a la vez. Cada una se registra como consumidor con un nombre (`practica:<id>`, `vista_previa:<user_id>`):

- `adquirir(nombre)` abre el dispositivo si es el primer consumidor.
- `liberar(nombre)` lo cierra si era el último.

Al abrir, se descartan 10 frames mientras la cámara ajusta la exposición.

### Consumidores

| Consumidor | Qué hace | ¿Mantiene encendida la cámara? |
|---|---|---|
| Orquestador | Analiza frames durante la práctica | Sí |
| Vista previa | Permite encuadrar al alumno al enrolarlo | Sí, mientras el usuario lea el video |
| `GET /stream` | Envía el video al navegador | No |
| `POST /usuarios/alumnos` | Toma una sola foto | No; si está apagada, la abre y la cierra |

Si el navegador se cierra sin avisar, una tarea vigilante apaga la vista previa tras 10 segundos sin que su dueño reciba frames.

---

## 8. Reconocimiento facial

### Principio

Facenet convierte un rostro en un *embedding*: un vector de **128 números** en el que las fotos de una misma persona producen vectores cercanos. Comparar rostros equivale a medir la cercanía entre vectores. El sistema no guarda fotos de los rostros, solo este vector cifrado.

### Enrolamiento

Ocurre al crear al alumno, con una sola captura:

```
frame ──► detector OpenCV ──► recorte y alineación ──► Facenet ──► vector de 128 valores
                                                                          │
              Si no hay exactamente un rostro: 422 ◄── comprobación ◄─────┘
                                                            │
                                                            ▼
                               Fernet (AES-128-CBC + HMAC-SHA256) ──► usuarios.face_embedding
```

El vector se cifra y no se reduce a un hash porque el reconocimiento necesita medir parecido: un hash destruiría esa información.

### Identificación

Al iniciar una práctica se descifran en memoria los vectores de los alumnos matriculados en esa materia. Luego, aproximadamente cada segundo (`IDENTIFICATION_INTERVAL_SECONDS = 1.0` más el tiempo de cálculo):

1. Se calcula el vector del último frame.
2. Se calcula la similitud del coseno contra cada candidato:

   ```
   similitud(a, b) = (a · b) / (|a| × |b|)
   ```

3. Se toma al candidato más parecido. Se acepta si su similitud es de al menos **0.60**.
4. Si es una persona distinta a la anterior, se emite el evento `estudiante_identificado`, con su similitud como `confianza`.

El umbral de 0.60 equivale a la distancia coseno máxima de 0.40 que DeepFace define para Facenet (`deepface/config/threshold.py`). No se calibró con datos propios del proyecto.

Restringir la comparación a los matriculados reduce el número de candidatos y, con él, las oportunidades de confundir a un alumno con otro.

### Comportamiento en casos límite

| Situación en el frame | Resultado |
|---|---|
| Un rostro de un candidato | Identificación, si supera el umbral |
| Más de un rostro | No se identifica a nadie |
| Un rostro que no supera el umbral | No se identifica a nadie |
| Ningún rostro detectado | DeepFace procesa la imagen completa como si fuera un rostro, porque aquí se llama con `enforce_detection=False`. El resultado también pasa por el umbral |
| Foto de un rostro | Se trata como un rostro real: no hay detección de vida |

Cuando deja de reconocerse a la persona, el servidor olvida la identificación y ya no se puede confirmar. Este olvido no genera ningún evento hacia el cliente.

### Diferencia de resolución al enrolar

Con la cámara ya encendida, el enrolamiento usa el frame reducido a 640 píxeles. Con la cámara apagada, usa la captura a resolución original. La identificación siempre trabaja con frames reducidos.

---

## 9. Detección de indumentaria

### El modelo

YOLO recibe una imagen y devuelve cajas delimitadoras, cada una con una clase y una confianza. Se carga un archivo de pesos por área, y solo una vez:

| Archivo | Estado | Tarea | Parámetros | Clases |
|---|---|---|---|---|
| `weights/civil.pt` | En uso | `detect` | 11.1 millones | `Hardhat`, `Mask`, `NO-Hardhat`, `NO-Mask`, `NO-Safety Vest`, `Person`, `Safety Cone`, `Safety Vest`, `machinery`, `vehicle` |
| `weights/medicina.pt` | **No existe** | — | — | — |
| `weights/best.pt` | Sin uso | `obb` | 2.7 millones | `casco`, `chaleco` |

La detección usa una confianza mínima de 0.50 y un umbral IoU de 0.45. Se ejecuta con el seguidor ByteTrack, que asigna un `track_id` a cada objeto; ese identificador se envía al cliente, pero **no interviene en la decisión**.

`GUIA_MODELOS.md` reporta un mAP50 de 0.86 para `civil.pt`. Ese dato no se volvió a medir para este documento y no describe el desempeño del sistema en un aula real.

### El algoritmo de decisión

Un único frame no basta: el modelo puede fallar en cualquiera de ellos. `PpeReview` acumula evidencia durante 6 segundos, con una pausa de 0.3 s entre análisis. Eso da un máximo de 20 frames, y menos según lo que tarde cada inferencia.

**En cada frame:**

```
1. Tomar las detecciones de clase Person.
   Si no hay ninguna, el frame no cuenta y se pasa al siguiente.
2. Elegir la persona con la caja de mayor área (la más cercana a la cámara).
3. Ampliar su caja un 10 % de su tamaño hacia cada lado.
4. Conservar las detecciones cuyo centro cae dentro de esa zona.
5. Para cada prenda requerida X:
       si aparece la clase X      → W[X] += 1
       si aparece la clase NO-X   → V[X] += 1
```

**Al terminar la ventana**, una prenda se da por llevada solo si:

```
W[X] ≥ 3   y   W[X] > V[X]
```

Toda prenda que no cumpla ambas condiciones se incluye en `faltantes`. El alumno cumple si la lista queda vacía.

### Justificación de cada regla

| Regla | Qué evita |
|---|---|
| Toda prenda parte como faltante | Aprobar a alguien por no haber podido observarlo |
| Mínimo de 3 frames | Aprobar por un falso positivo aislado |
| Más positivos que negativos | Aprobar cuando el modelo alterna entre `X` y `NO-X` |
| Solo cuenta lo que está sobre la persona | Aprobar con una prenda ajena o que esté cerca |
| Margen del 10 % | Perder un casco que sobresale de la caja de la persona |

El diseño prefiere **reprobar por error antes que aprobar por error**: ante la duda, la prenda falta. Tiene un costo: si el modelo no detecta a la persona, todas las prendas salen como faltantes aunque las lleve puestas.

### Evidencia

Si el alumno no cumple, se guarda el último frame analizado con un rectángulo rojo alrededor de la última persona vista (o del frame completo, si no se vio a nadie) y el texto de lo que falta. Al ser una imagen, permite auditar el resultado después.

---

## 10. Flujos completos

### Enrolar a un alumno

```
Cliente                       Backend                          Cámara      MongoDB
   │  POST /camara/vista-previa  │                               │           │
   ├────────────────────────────►│ adquirir ────────────────────►│           │
   │  <img src="/stream?token="> │                               │           │
   │◄─────── video MJPEG ────────┤◄─────────── frames ───────────┤           │
   │                             │                               │           │
   │  POST /usuarios/alumnos     │ 1. ¿Código libre?             │           │
   ├────────────────────────────►│ 2. ¿Permisos sobre datos      │           │
   │                             │    y materias?                │           │
   │                             │ 3. Captura ◄──────────────────┤           │
   │                             │ 4. Embedding (exactamente     │           │
   │                             │    un rostro, o 422)          │           │
   │                             │ 5. Hash y cifrado             │           │
   │                             │ 6. Guardar usuario ──────────────────────►│
   │                             │ 7. Matricular en materias ───────────────►│
   │◄──────── UsuarioOut ────────┤                               │           │
   │  DELETE /camara/vista-previa│ liberar ─────────────────────►│           │
```

Las comprobaciones rápidas van antes de la captura, para no hacer esperar a alguien por la cámara y rechazarlo después. La captura y el embedding se ejecutan en hilos auxiliares, para no bloquear la API.

### Ejecutar una práctica

```
Docente (cliente)                  Endpoints               Orquestador            MongoDB
   │  POST /practicas                 │                         │                    │
   ├─────────────────────────────────►│ valida y crea "activa" ─────────────────────►│
   │                                  │ descifra candidatos ◄────────────────────────┤
   │                                  │ arranca hilo ──────────►│ adquiere la cámara │
   │◄─────── PracticaInDB ────────────┤                         │                    │
   │                                  │                         │                    │
   │  ═══════════ Fase: identificacion (cada ~1 s) ═══════════  │                    │
   │◄═══ WS estudiante_identificado ════════════════════════════┤                    │
   │                                  │                         │                    │
   │  POST /practicas/{id}/confirmar  │                         │                    │
   ├─────────────────────────────────►│ confirma ──────────────►│                    │
   │◄═══ WS fase_cambiada (indumentaria) ═══════════════════════┤                    │
   │                                  │                         │                    │
   │  ═══════════ Fase: indumentaria (6 s) ═══════════════════  │                    │
   │◄═══ WS detecciones_frame (por cada análisis) ══════════════┤                    │
   │                                  │                         │ evidencia a disco  │
   │                                  │                         │ guarda asistencia ►│
   │◄═══ WS asistencia_registrada ══════════════════════════════┤                    │
   │◄═══ WS fase_cambiada (identificacion) ═════════════════════┤                    │
   │                                  │                         │                    │
   │        ... se repite con cada alumno ...                   │                    │
   │                                  │                         │                    │
   │  POST /practicas/{id}/end        │ detiene el hilo ───────►│ libera la cámara   │
   │                                  │ marca "finalizada" ─────────────────────────►│
   │◄─────── PracticaInDB ────────────┤                         │                    │
```

Comprobaciones al iniciar, en este orden: que no haya otra práctica en memoria, que la materia exista y sea del docente, y que el área tenga catálogo. Si después falla la cámara o el descifrado de rostros, se borra el registro recién creado y se responde `500`.

### Máquina de estados del orquestador

```
          POST /confirmar (solo el último identificado)
        ┌───────────────────────────────────────────┐
        │                                           ▼
 ┌────────────────┐                        ┌────────────────┐
 │ identificacion │                        │  indumentaria  │
 └────────────────┘                        └────────────────┘
        ▲                                           │
        └───────────────────────────────────────────┘
              vence el plazo de 6 s: guarda el resultado
```

### Consultar un reporte

`GET /practicas/{id}/reporte` comprueba la pertenencia, carga la materia, sus asistencias y sus alumnos, y genera una fila por cada matriculado. Quien no tenga asistencia sale como ausente. El cálculo se hace al momento: los reportes no se guardan.

---

## 11. Concurrencia

Es la parte central del diseño. Inferir con modelos de visión es lento y bloqueante, mientras que FastAPI atiende todas las peticiones en un único bucle asíncrono. Si ambos compartieran hilo, toda la API se detendría durante cada inferencia.

### Unidades de ejecución

| Unidad | Tipo | Trabajo | Ritmo |
|---|---|---|---|
| Bucle de eventos | Hilo principal, asyncio | REST, WebSocket, video, MongoDB | Por evento |
| Captura | `threading.Thread` | Leer y reducir frames | 8 por segundo |
| Orquestador | `threading.Thread` | Inferencia facial y de objetos, decisión y evidencias | Cada ~1 s o ~0.3 s, más la inferencia |
| Hilos auxiliares | `asyncio.to_thread` | Enrolamiento y apertura de cámara de la vista previa | Por petición |
| Vigilante | Tarea asyncio | Apagar vistas previas sin lector | Cada 1 s |

### Comunicación entre hilos

```
 Hilo del orquestador                         Bucle de eventos
┌─────────────────────┐                     ┌──────────────────────┐
│ async_bridge        │ run_coroutine_      │ manager._broadcast() │──► WebSocket
│  .run_coroutine() ──┼─ threadsafe ───────►│ create_asistencia()  │──► MongoDB
└─────────────────────┘                     └──────────────────────┘
```

El cliente asíncrono de MongoDB y las conexiones WebSocket pertenecen al bucle de eventos. El orquestador no los usa directamente: les entrega las tareas con `asyncio.run_coroutine_threadsafe`. Es comunicación "dispara y olvida": si la tarea falla, solo se imprime `[ERROR async]` en consola, y el orquestador continúa.

### Estado compartido

| Dato | Protección |
|---|---|
| Último frame | `threading.Lock`, y se entregan copias |
| Consumidores de la cámara | `threading.RLock`; también protege la captura del enrolamiento |
| Vistas previas | `asyncio.Lock` |
| Estado del orquestador | Ninguna. `confirmar_identificacion` lo modifica desde el bucle de eventos mientras el hilo lo lee. Se apoya en que la fase es lo último que se escribe |

### Restricción de despliegue

El registro de prácticas, las conexiones WebSocket y el acceso a la cámara viven en la memoria de un único proceso. **El servidor debe correr con un solo worker.** Escalar horizontalmente requeriría rediseñar estos componentes.

---

## 12. Comunicación con el cliente

El cliente recibe información por tres canales, cada uno con su función:

| Canal | Dirección | Formato | Uso |
|---|---|---|---|
| REST (`/api/v1/...`) | Petición y respuesta | JSON | Datos y acciones |
| WebSocket (`/ws/detections`) | Del servidor al cliente | JSON | Resultados en tiempo real |
| MJPEG (`/api/v1/stream`) | Del servidor al cliente | `multipart/x-mixed-replace` | Video en un `<img>` |

**El video llega sin anotaciones.** Las cajas se envían por el WebSocket en coordenadas normalizadas de 0 a 1 y el cliente las dibuja encima. El video y el análisis quedan desacoplados, y el servidor no tiene que volver a codificar cada imagen con sus cajas.

MJPEG se reproduce sin nada especial en el navegador, a costa de más ancho de banda que un video comprimido. Se envía a unos 8 frames por segundo y se corta si la cámara se apaga, si pasan 5 segundos sin imagen o si el servidor se está apagando.

### Eventos del WebSocket

Solo pueden conectarse `docente`, `coordinador` y `admin`; los demás se rechazan con el código `1008`. Todos los eventos incluyen `evento` y `timestamp`, y se envían a **todos** los clientes conectados.

| Evento | Cuándo | Contenido |
|---|---|---|
| `estado_inicial` | Al conectarse | `practica_id`, `fase`, `identificado`, `alumno_id`, `segundos_restantes` |
| `estudiante_identificado` | Se reconoce a una persona nueva | `practica_id`, `alumno_id`, `nombre`, `codigo`, `confianza` |
| `fase_cambiada` | Cambia la fase | `practica_id`, `fase` y, en `indumentaria`, `alumno_id` |
| `detecciones_frame` | Cada análisis de la revisión | `frame_width`, `frame_height`, `items` |
| `asistencia_registrada` | Termina la revisión | `practica_id`, `alumno_id`, `cumplio_indumentaria`, `faltantes`, `evidencia_url` |

`estado_inicial` permite al cliente reconstruir la pantalla al recargar la página o reconectarse.

---

## 13. Seguridad y privacidad

### Medidas implementadas

| Activo | Medida |
|---|---|
| Contraseñas | Hash bcrypt con sal individual y costo 12; nunca salen de la API |
| Sesiones | JWT firmado con HS256 y expiración de 8 horas |
| Rostros en la base | Cifrado autenticado con Fernet; un valor alterado se rechaza |
| Rostros en la API | `UsuarioOut` excluye `face_embedding` y `password_hash` |
| Acceso a datos | Comprobación de rol y pertenencia |
| Evidencias | Se sirven por un endpoint que valida el token, que la ruta exista en una asistencia y el alcance del usuario |
| Entrada de datos | Validación con Pydantic y comprobación de `ObjectId` |
| Navegador | CORS limitado a los orígenes configurados |
| Identificación | Requiere confirmación humana antes de registrar |

### Tratamiento de datos biométricos

Los embeddings faciales son datos personales sensibles. Este es su ciclo de vida:

| Etapa | Estado del dato |
|---|---|
| Captura | La imagen existe solo en memoria y no se guarda |
| En reposo | Cifrado en MongoDB |
| Durante la práctica | Descifrado en memoria del proceso |
| Eliminación | No existe un endpoint para eliminar usuarios ni rostros |

La clave de cifrado está en el `.env` del mismo servidor: protege frente a una copia de la base de datos, no frente a un acceso al equipo. Las imágenes de evidencia sí muestran a la persona, se guardan sin cifrar y no tienen política de borrado.

Una investigación que use este sistema con personas reales debería revisar el consentimiento de los alumnos y la normativa local sobre datos biométricos. El código no implementa ningún mecanismo de consentimiento.

---

## 14. Limitaciones

### De funcionamiento

| Limitación | Efecto |
|---|---|
| **Falta el modelo de medicina** | Una práctica de `medicina` inicia, pero el hilo falla en la primera revisión y la práctica deja de responder |
| Una práctica a la vez | Hay una sola cámara por servidor |
| Una sola foto de enrolamiento | Una mala captura degrada el reconocimiento, y no hay endpoint para repetirla |
| Candidatos fijos al iniciar | Un alumno matriculado durante la práctica no se reconoce hasta la siguiente |
| Sin persona detectada, todo falta | Reprueba a alumnos que cumplen si están muy cerca, cortados o con poca luz |
| Otra persona más cerca de la cámara | Se evalúa a esa persona, no al alumno confirmado |
| Carga diferida de YOLO | El plazo de 6 s empieza al confirmar, así que la carga del modelo consume parte de la primera revisión |
| Finalizar durante una revisión | La revisión en curso se descarta y no se guarda su asistencia |

### De robustez

| Limitación | Efecto |
|---|---|
| Sin manejo de errores en el hilo del orquestador | Una excepción lo termina en silencio: la práctica sigue "activa", pero deja de analizar |
| Comprobación de práctica única solo en memoria y sin bloqueo | Dos peticiones simultáneas podrían pasar la comprobación a la vez |
| Asistencias sin índice único | Confirmar dos veces al mismo alumno guarda dos asistencias; el reporte muestra una |
| Abrir la cámara al iniciar una práctica | Bloquea brevemente el bucle de eventos |
| Codificación JPEG del video | Se ejecuta dentro del bucle de eventos |
| Errores registrados con `print` | No hay sistema de registros ni monitoreo |
| Pruebas limitadas | Hay 24 pruebas unitarias, sobre el uso compartido de la cámara y el cifrado. Los endpoints y los modelos no tienen pruebas |

### De seguridad

| Limitación | Efecto |
|---|---|
| `GET /materias/{id}/alumnos` sin comprobar pertenencia | Cualquier docente o coordinador ve los alumnos de cualquier materia |
| WebSocket y video sin filtrar por práctica | Cualquier docente o coordinador conectado recibe los eventos y el video de la práctica en curso, sea o no suya |
| Sin detección de vida | El reconocimiento no distingue un rostro real de una foto; la barrera es el docente |
| Tokens no revocables | Un token robado sirve hasta su expiración |
| Token en la URL | Puede quedar en el historial y en los registros del servidor |
| Sin límite de intentos de login | No hay protección contra ataques de fuerza bruta |
| Sin HTTPS propio | En producción necesita un proxy con TLS |

---

## 15. Alcance de la evidencia

Esta sección delimita lo que este documento permite afirmar.

**Sí describe:** la arquitectura, los algoritmos, los umbrales configurados y el comportamiento que se deduce del código.

**No aporta datos medidos.** El repositorio no contiene una evaluación del sistema completo, por lo que este documento no permite afirmar:

- La precisión del reconocimiento facial con los alumnos reales (tasas de falsa aceptación y de falso rechazo).
- La precisión del veredicto de cumplimiento: cuántas decisiones de "cumple" o "no cumple" son correctas.
- La latencia de cada etapa o los frames que se alcanzan a analizar en cada revisión.
- El efecto de la iluminación, la distancia o el ángulo de la cámara.

Los valores `0.60`, `3 frames`, `6 segundos` y `10 %` son **parámetros de diseño**, no resultados optimizados experimentalmente. Para presentar cifras de desempeño hay que medirlas en condiciones de uso.

---

## 16. Anexo: API REST

La API tiene 37 operaciones, documentadas de forma interactiva en `/docs`. Salvo que se indique, las rutas llevan el prefijo `/api/v1`. El `admin` también tiene acceso donde figuran `coordinador` o `docente`.

| Método y ruta | Función | Acceso |
|---|---|---|
| `GET /` (sin prefijo) | Confirmar que el proceso corre | Público |
| `GET /health` | Revisar el servicio y MongoDB | Público |
| `GET /practices` | Listar el catálogo de indumentaria | Público |
| `POST /auth/login` | Iniciar sesión | Público |
| `GET /auth/me` | Ver el perfil propio | Autenticado |
| `PATCH /auth/me` | Actualizar el perfil propio | Autenticado |
| `POST /auth/me/password` | Cambiar la contraseña propia | Autenticado |
| `POST /auth/refresh` | Renovar el token | Autenticado |
| `POST /usuarios/coordinadores` | Crear un coordinador | `admin` |
| `POST /usuarios/docentes` | Crear un docente | `coordinador` |
| `POST /usuarios/alumnos` | Enrolar a un alumno | `coordinador`, `docente` |
| `GET /usuarios` | Listar usuarios | `coordinador`, `docente` |
| `GET /usuarios/{id}` | Obtener un usuario | `coordinador`, `docente` |
| `PATCH /usuarios/{id}` | Actualizar datos académicos | `coordinador` |
| `POST /usuarios/{id}/password` | Restablecer una contraseña | `coordinador` |
| `POST /materias` | Crear una materia | `coordinador` |
| `GET /materias` | Listar materias | `coordinador`, `docente` |
| `GET /materias/{id}` | Obtener una materia | `coordinador`, `docente` |
| `PATCH /materias/{id}` | Actualizar una materia | `coordinador` |
| `POST /materias/{id}/alumnos` | Matricular a un alumno | `coordinador`, `docente` |
| `GET /materias/{id}/alumnos` | Listar los alumnos | `coordinador`, `docente` |
| `DELETE /materias/{id}/alumnos/{alumno_id}` | Quitar a un alumno | `coordinador`, `docente` |
| `POST /practicas` | Iniciar una práctica | `docente` |
| `GET /practicas` | Listar prácticas | `coordinador`, `docente` |
| `GET /practicas/active` | Obtener la práctica activa | `docente` |
| `POST /practicas/{id}/confirmar` | Confirmar al alumno identificado | `docente` |
| `POST /practicas/{id}/end` | Finalizar una práctica | `docente` |
| `GET /practicas/{id}/reporte` | Obtener el reporte | `coordinador`, `docente` |
| `GET /asistencias` | Listar asistencias | Autenticado, según su alcance |
| `GET /alumno/materias` | Ver las materias propias | `alumno` |
| `GET /alumno/asistencias` | Ver las asistencias propias | `alumno` |
| `GET /coordinacion/resumen` | Ver los indicadores | `coordinador` |
| `POST /camara/vista-previa` | Encender la vista previa | `coordinador`, `docente` |
| `GET /camara/vista-previa` | Consultar la vista previa | `coordinador`, `docente` |
| `DELETE /camara/vista-previa` | Apagar la vista previa | `coordinador`, `docente` |
| `GET /stream` | Ver el video en vivo | `coordinador`, `docente` |
| `GET /static/evidence/{fecha}/{archivo}` (sin prefijo) | Ver una evidencia | Autenticado, según su alcance |

Además, existe el WebSocket `/ws/detections`, sin prefijo y fuera de las 37 operaciones.
