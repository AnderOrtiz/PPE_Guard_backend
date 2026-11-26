# PPE_Guard — Propuestas de pruebas piloto y obtención de resultados

Propuestas concretas para evaluar el sistema **en condiciones de uso real**, con protocolos, métricas y procedimientos de análisis. Está pensado para alimentar un archivo de investigación: cada piloto termina en una tabla o una cifra que se puede copiar al informe.

**Punto de partida.** `ARQUITECTURA_BACKEND.md` (sección 15) y `DOCUMENTACION_TECNICA.md` (sección 14) describen el código, pero no aportan datos medidos: no hay cifras de precisión facial, de acierto del veredicto de indumentaria, de latencia ni de efecto de la iluminación. Los valores `0.60`, `3 frames`, `6 segundos` y `10 %` son **parámetros de diseño**, no resultados. Este documento propone cómo medirlos; **no inventa resultados**. Donde diga `—`, hay que colocar el valor obtenido al ejecutar el piloto.

Está escrito a partir del código en el commit `d1942f4` (30 de octubre de 2026). Si algo contradice al código, vale el código.

**Documentos relacionados:** `ARQUITECTURA_BACKEND.md` (qué hace el sistema), `DOCUMENTACION_TECNICA.md` (parámetros ajustables), `GUIA_MODELOS.md` (requisitos de los `.pt`), `FRONTEND.md` (contrato de la API), `Orden.md` (secuencia para disparar una práctica).

---

## Índice

1. [Qué se quiere demostrar](#1-qué-se-quiere-demostrar)
2. [Reglas comunes a todos los pilotos](#2-reglas-comunes-a-todos-los-pilotos)
3. [Piloto 0 — preparación y verificación de los instrumentos](#3-piloto-0--preparación-y-verificación-de-los-instrumentos)
4. [Piloto 1 — exactitud del reconocimiento facial](#4-piloto-1--exactitud-del-reconocimiento-facial)
5. [Piloto 2 — acierto del veredicto de indumentaria](#5-piloto-2--acierto-del-veredicto-de-indumentaria)
6. [Piloto 3 — latencia, frames analizados y capacidad](#6-piloto-3--latencia-frames-analizados-y-capacidad)
7. [Piloto 4 — prueba integrada en un aula real](#7-piloto-4--prueba-integrada-en-un-aula-real)
8. [Piloto 5 — robustez, recuperación y permisos](#8-piloto-5--robustez-recuperación-y-permisos)
9. [Cómo sacar los resultados](#9-cómo-sacar-los-resultados)
10. [Plantillas para el archivo de investigación](#10-plantillas-para-el-archivo-de-investigación)
11. [Ética, privacidad y validez](#11-ética-privacidad-y-validez)
12. [Plan de ejecución](#12-plan-de-ejecución)
13. [Apéndice A — capturar eventos a JSONL](#13-apéndice-a--capturar-eventos-a-jsonl)
14. [Apéndice B — análisis con Polars](#14-apéndice-b--análisis-con-polars)

---

## 1. Qué se quiere demostrar

Las preguntas de investigación se derivan directamente de lo que el código **no** permite afirmar hoy.

| ID | Pregunta | Hipótesis de trabajo (falsable) | Piloto |
|---|---|---|---|
| RQ1 | ¿Reconoce el sistema a los alumnos reales frente a la cámara del aula? | Con 15 alumnos matriculados y luz de laboratorio, ≥ 90 % de las presentaciones generan el evento correcto y < 5 % confunden a un alumno con otro | 1 |
| RQ2 | ¿Coincide el veredicto "cumple / no cumple" con lo que ve un observador humano? | El veredicto coincide en ≥ 85 % de las revisiones; los falsos "cumple" son < 5 % | 2 |
| RQ3 | ¿Cuánto tarda cada etapa y cuántos frames se analizan realmente en los 6 segundos? | La revisión analiza ≥ 8 frames útiles de los ~20 teóricos y el tiempo hasta la asistencia es ≤ 8 s | 3 |
| RQ4 | ¿Afectan la luz, la distancia y el ángulo a los resultados? | La tasa de acierto baja > 15 puntos en contraluz o a más de 2 m | 1 y 2 |
| RQ5 | ¿Es operable en una práctica completa? | Se registran ≥ 90 % de los alumnos presentes, con ≤ 2 intervenciones del docente y sin prácticas huérfanas | 4 |
| RQ6 | ¿Se comporta el sistema ante fallos y reinicios? | La recuperación tras reinicio conserva la práctica si tiene < 8 h; los casos límite quedan documentados | 5 |

**Regla de oro:** las hipótesis son ejemplos para discutir, no expected results. Se aceptan o se rechazan con los datos del piloto. Ninguna cifra de esta tabla debe copiarse al informe como si ya estuviera medida.

---

## 2. Reglas comunes a todos los pilotos

1. **Verdad de terreno independiente.** Un observador anota lo que ocurre (quién está, qué prendas lleva, cuándo empieza y termina) *antes* de mirar lo que dijo el sistema. Si se mira primero el resultado, se contamina la etiqueta.
2. **Ciego cuando sea posible.** Quien etiqueta las evidencias no debe saber si el sistema marcó "cumple" o "no cumple".
3. **Un solo conjunto de parámetros por medición.** Anotar commit, `.env`, constantes y versión de los modelos antes de empezar. Cambiar **una** variable a la vez y repetir el piloto.
4. **Separar calibración de evaluación.** El 60 % de las muestras sirve para ajustar umbrales; el 40 % restante se guarda sin tocar y se usa solo para el informe.
5. **Serializar.** Hay una sola cámara y una sola práctica activa por servidor (`DOCUMENTACION_TECNICA.md`, sección 6). Los pilotos no se corren en paralelo.
6. **Guardar artefactos, no conclusiones.** Por cada piloto se conservan: archivo JSONL de eventos, hoja de verdad de terreno, evidencias, salida de consola de uvicorn y una foto de la configuración usada. Las cifras se recalculan desde los artefactos.
7. **Sincronizar relojes.** El observador y el servidor deben usar el mismo reloj (NTP o, como mínimo, ajustar manualmente antes de empezar). Los `timestamp` del WebSocket vienen en UTC con zona (`+00:00`); las fechas de la API REST vienen en UTC **sin** zona. Normalizar todo a UTC antes de cruzar datos.
8. **Usar códigos seudónimos en el informe.** En el archivo de investigación se publican agregados; las tablas con nombres reales se quedan en el artefacto local.

### Hoja de verdad de terreno (plantilla)

Guardar como `datos/<piloto>/verdad_terreno.csv`:

```csv
registro_id,alumno_codigo,condicion,inicio_utc,fin_utc,cumple_real,faltantes_reales,observador,notas
F001,A014,luz_normal,2026-11-24T10:03:11+00:00,2026-11-24T10:03:15+00:00,,hardhat,AO,perfil ligero
R001,A014,cumple_total,2026-11-24T10:05:02+00:00,2026-11-24T10:05:09+00:00,si,,AO,Casco y chaleco visibles
```

`cumple_real` y `faltantes_reales` se llenan con el criterio humano; `condicion` permite después agrupar por luz, distancia o tipo de falta.

### Registro de configuración (plantilla)

```text
Fecha:                 —
Commit del backend:    d1942f4
Entorno:               yolo (Python 3.11.16)
SIMILARITY_THRESHOLD:  0.60
CONFIDENCE_THRESHOLD:  0.50
REVIEW_CONFIRM_FRAMES: 3
REVIEW_PERSON_MARGIN:  0.10
REVIEW_DURATION_SECONDS: 6
IDENTIFICATION_INTERVAL_SECONDS: 1.0
INDUMENTARIA_INTERVAL_SECONDS: 0.3
Pesos YOLO:            weights/civil.pt (sha256: —)
Cámara:                índice 0, 640 px, 8 fps
Observador:            —
```

---

## 3. Piloto 0 — preparación y verificación de los instrumentos

**Objetivo:** asegurar que lo que se va a medir está realmente capturado antes de gastar tiempo con alumnos reales.

**Duración estimada:** 30–45 minutos.

### Pasos

1. Levantar la base con `docker compose up -d` y el servidor con `uvicorn app.main:app --reload` (`Orden.md`, terminales 0 y 1).
2. Verificar `/health` y `/docs`.
3. Si la base está vacía, `python -m scripts.seed_inicializar`. Crear un coordinador, un docente, una materia de `civil` y dos alumnos de prueba con su rostro.
4. **Crear el capturador de eventos.** `Orden.md` invoca `python -m scripts.test_ws_client`, pero ese archivo **no está hoy en el repositorio**. Hay que crearlo; se propone `scripts/capturar_eventos.py` en el [Apéndice A](#13-apéndice-a--capturar-eventos-a-jsonl).
5. Iniciar la captura antes de la práctica y dejarla corriendo en su propia terminal.
6. Confirmar que no hay práctica activa con `GET /api/v1/practicas/active` (debe dar `null`) y arrancar una práctica de prueba de dos alumnos.
7. Recorrer el flujo completo de `Orden.md`: identificar → confirmar → esperar `asistencia_registrada` → finalizar.
8. Revisar el JSONL generado y compararlo con la colección `asistencias`.

### Criterios de salida (checklist)

- [ ] El JSONL contiene `estado_inicial`, `estudiante_identificado`, `fase_cambiada`, `detecciones_frame` y `asistencia_registrada`.
- [ ] Los `alumno_id` del JSONL coinciden con los de `asistencias` en Mongo.
- [ ] Los `timestamp` difieren del reloj local en menos de 1 segundo.
- [ ] `GET /practicas/active` vuelve a dar `null` tras finalizar.
- [ ] Se guardó la configuración usada y una copia de la base (`mongodump`) antes de los pilotos con personas.

**Si falla:** no se siga. El resto del documento asume que esta captura funciona.

---

## 4. Piloto 1 — exactitud del reconocimiento facial

**Pregunta:** RQ1 y RQ4.  
**Duración estimada:** 2–3 sesiones de 30 minutos.

### Qué se mide

El evento `estudiante_identificado` trae `alumno_id`, `codigo`, `nombre` y `confianza` (la similitud del coseno). El sistema emite el evento **solo cuando cambia la persona identificada**: si el mismo alumno sigue en cuadro, no vuelve a emitir. Por eso la unidad de análisis es la **presentación** (entrada y salida de una persona del encuadre), no el evento suelto.

### Diseño

| Elemento | Valor propuesto |
|---|---|
| Participantes | 15 alumnos matriculados en la materia de la práctica |
| Presentaciones por alumno | 3 (una por condición) → 45 pruebas positivas |
| Condiciones | A: luz normal, de frente, 1–2 m; B: contraluz o perfil; C: con gafas / cubreboca / gorra |
| Pruebas negativas | 10 presentaciones de persona no matriculada + 5 con dos rostros en cuadro |
| División | 60 % calibración del umbral, 40 % evaluación final intacta |

Colocar una marca en el piso a 1.5 m de la cámara, como recomienda `DOCUMENTACION_TECNICA.md` (sección 8), y mantenerla fija en todos los pilotos.

### Protocolo por presentación

1. El observador escribe `inicio_utc`, `alumno_codigo` y `condicion` en la hoja de verdad **antes** de que la persona se pare delante de la cámara.
2. La persona se para en la marca y permanece 3 segundos.
3. El observador escribe `fin_utc` cuando la persona sale de cuadro.
4. El docente **no confirma** todavía: este piloto solo observa eventos de identificación.
5. Repetir hasta completar las 45 + 15 presentaciones.
6. Al terminar, cruzar cada presentación con los eventos del JSONL: se considera acierto si en `[inicio, fin]` hay un `estudiante_identificado` con el `alumno_id` correcto.
7. Guardar la `confianza` de cada evento para analizar el umbral.

### Métricas

| Métrica | Fórmula | Qué significa |
|---|---|---|
| Tasa de reconocimiento | `aciertos / presentaciones de matriculados` | RQ1: cuántas veces aparece la persona correcta |
| Falso rechazo (FRR) | `sin evento / presentaciones de matriculados` | No lo reconoció |
| Confusión entre alumnos | `evento con otro alumno / presentaciones de matriculados` | El error más grave del sistema |
| Falsa aceptación (FAR) | `no matriculados identificados como alguien / presentaciones no matriculadas` | Riesgo de suplantación |
| Fallo con dos rostros | `eventos emitidos / presentaciones con dos rostros` | Debería ser 0 según el código |
| Latencia de identificación | `timestamp del evento - inicio_utc` | Tiempo hasta que el docente ve la tarjeta |
| Confianza media por condición | `media de confianza agrupada por condición` | Base para calibrar `SIMILARITY_THRESHOLD` |

### Calibración del umbral

Con el subconjunto de calibración, barrer `SIMILARITY_THRESHOLD` en `0.50, 0.55, 0.60, 0.65, 0.70, 0.75` **sobre los valores de `confianza` ya capturados** (no hace falta volver a correr el piloto para cada valor, porque el umbral solo decide si se acepta el candidato ya calculado). Para cada umbral registrar aciertos, confusiones y falsas aceptaciones. Elegir el punto que mantenga las confusiones por debajo del objetivo y aplicarlo al subconjunto de evaluación.

Si se decide cambiar el valor en código, hay que reiniciar el servidor y **repetir** el piloto con el nuevo valor; no se puede mezclar configuraciones en una misma cifra.

### Resultado que se lleva al informe

- Matriz de confusión alumno real × alumno identificado (15 × 15, con `sin evento` como fila/columna adicional).
- Tabla de acierto por condición A/B/C.
- Tabla de umbral vs. acierto / confusión / falsa aceptación.
- Una caja de bigotes de `confianza` por condición (matplotlib ya está en `requirements.txt`).

**Limitación que debe quedar escrita:** no hay detección de vida, así que una foto impresa puede ser aceptada; y cada alumno fue enrolado con **una sola** captura. Este piloto mide el sistema tal como está, no esas dos debilidades.

---

## 5. Piloto 2 — acierto del veredicto de indumentaria

**Pregunta:** RQ2 y RQ4.  
**Duración estimada:** 3–4 sesiones cortas.  
**Área:** `civil` (`Hardhat`, `Safety Vest`). El área `medicina` está **bloqueada** porque `weights/medicina.pt` no existe: una práctica de medicina inicia pero el hilo muere en la primera revisión (`DOCUMENTACION_TECNICA.md`, sección 14). Si el informe necesita medicina, hay que entrenar el modelo antes (`GUIA_MODELOS.md`, sección 4) y registrarlo como hallazgo.

### Qué se mide

Al terminar la revisión, `asistencia_registrada` trae `cumplio_indumentaria`, `faltantes` y `evidencia_url`. La verdad de terreno la da un observador que mira al alumno **en el momento de la confirmación**, con la misma lista del catálogo.

### Diseño

| Escenario | Revisiones propuestas | Etiqueta humana esperada |
|---|---:|---|
| Casco y chaleco puestos | 20 | `cumple = sí` |
| Falta solo el casco | 15 | `cumple = no`, `faltantes = [Hardhat]` |
| Falta solo el chaleco | 15 | `cumple = no`, `faltantes = [Safety Vest]` |
| Casco en la mano, no puesto | 10 | `cumple = no` |
| Casco de otro compañero en cuadro | 10 | `cumple = no` para el alumno revisado |
| Contraluz / alumno cortado por el borde | 10 | según lo que vea el observador |

Total orientativo: 80 revisiones. Es mejor repetir pocas condiciones bien etiquetadas que muchas sin control.

### Protocolo por revisión

1. El observador llena `registro_id`, `alumno_codigo`, `condicion`, `inicio_utc` y `cumple_real` / `faltantes_reales` antes de confirmar.
2. El docente confirma al alumno identificado con `POST /api/v1/practicas/{id}/confirmar` y body `{"alumno_id": "..."}` (`Orden.md`).
3. El observador anota `fin_utc` al recibir `asistencia_registrada` en el JSONL.
4. Copiar del evento: `cumplio_indumentaria`, `faltantes`, `evidencia_url`.
5. Si hay evidencia, descargar la foto y renombrarla con el `registro_id` seudónimo para etiquetarla después sin conocer el veredicto del sistema.

### Métricas

| Métrica | Fórmula |
|---|---|
| Exactitud del veredicto | `revisiones con cumplio igual al observador / total de revisiones` |
| Falso aprobado (FAR) | `sistema dice "cumple" y el observador dice "no" / revisiones donde el observador dice "no"` |
| Falso reprobado (FRR) | `sistema dice "no cumple" y el observador dice "sí" / revisiones donde el observador dice "sí"` |
| Exactitud por prenda | `clasificaciones correctas de la prenda / revisiones`, para `Hardhat` y `Safety Vest` |
| Faltante correctamente detectado | `faltantes del sistema = faltantes reales` (comparación por lista) |
| Frames de la revisión | `número de eventos detecciones_frame entre fase_cambiada(indumentaria) y asistencia_registrada` |
| Frames útiles | `frames con al menos una detección Person / frames totales` |

Sobre la relevancia del falso aprobado: el código aplica **faltante por defecto** y prefiere reprobar por error antes que aprobar por error (`ARQUITECTURA_BACKEND.md`, sección 9). El piloto debe reportar ambos errores por separado; un solo número de "exactitud" esconde cuál de los dos ocurrió.

### Calibración (en el 60 % de las muestras)

Probar **una variable a la vez**:

| Variable | Valores | Efecto esperado |
|---|---|---|
| `REVIEW_CONFIRM_FRAMES` | 3 → 2 → 4 | Menos frames exige, más aprobaciones; más frames, más reprobaciones |
| `REVIEW_PERSON_MARGIN` | 0.10 → 0.20 → 0.00 | Más margen cuenta prendas que sobresalen; menos margen las descarta |
| `CONFIDENCE_THRESHOLD` | 0.50 → 0.45 | Más detecciones aceptadas, incluidas falsas |

Los cambios implican editar constantes y reiniciar; cada configuración necesita su propio JSONL. El 40 % de reserva se evalúa solo con la configuración ganadora.

### Resultado que se lleva al informe

- Matriz de confusión `cumple_real` × `cumplio_indumentaria`.
- Tabla por escenario: exactitud, falso aprobado, falso reprobado, frames útiles (media y mínimo).
- Tabla por prenda con aciertos y errores, más ejemplos de evidencia anotados.
- Nota sobre el caso "veo el casco pero no veo a la persona": es la causa conocida de que todo salga como faltante (`DOCUMENTACION_TECNICA.md`, sección 8).

---

## 6. Piloto 3 — latencia, frames analizados y capacidad

**Pregunta:** RQ3.  
**Coste adicional:** cero si se instrumenta durante el piloto 2 o el 4; aprovechar esos mismos JSONL.

### Métricas y cómo obtenerlas

| Métrica | Cálculo desde los eventos |
|---|---|
| Tiempo hasta identificación | `estudiante_identificado.timestamp - presentación.inicio_utc` (del piloto 1) |
| Tiempo de revisión | `asistencia_registrada.timestamp - fase_cambiada(fase=indumentaria).timestamp` |
| Frames analizados | conteo de `detecciones_frame` en esa ventana |
| Frames por segundo analizados | `frames analizados / tiempo de revisión` |
| Tiempo total por alumno | `asistencia_registrada.timestamp - confirmación HTTP` (anotar la hora local de la llamada `curl`) |
| Capacidad | `asistencias registradas / minutos de práctica` (alumnos por minuto) |
| Uso de CPU y memoria | muestrear `ps -p <pid> -o %cpu,rss` cada segundo durante la práctica |

**Ojo con los eventos:** `detecciones_frame` **no incluye** `practica_id`. Para atribuirlos a una revisión hay que segmentar el JSONL entre `fase_cambiada` con `fase = "indumentaria"` y el `asistencia_registrada` correspondiente. `estado_inicial` y todos los eventos sí incluyen `practica_id`.

**Comparación frío / caliente:** YOLO y DeepFace se cargan la primera vez que se usan, no al arrancar (`ARQUITECTURA_BACKEND.md`, sección 4). Por eso la **primera** revisión de la sesión consume parte de los 6 segundos en cargar el modelo. Registrar por separado la primera revisión y el resto; reportar ambas, porque mezclarlas daría una media engañosa.

### Resultado que se lleva al informe

Tabla de percentiles (p50, p90, máximo) de: latencia de identificación, duración real de la revisión, frames analizados, tiempo total por alumno. Gráfico de línea de `frames analizados` por revisión, con una línea de referencia en 20 (el máximo teórico con 6 s / 0.3 s).

---

## 7. Piloto 4 — prueba integrada en un aula real

**Pregunta:** RQ5.  
**Duración estimada:** una práctica completa de 45–60 minutos.

### Diseño

- Grupo real de 15–30 alumnos matriculados en una materia de `civil`.
- Docente usando el frontend React si está disponible; si no, el flujo de `Orden.md` con `curl` + el capturador de eventos. Anotar cuál de las dos vías se usó: es una limitación del piloto.
- Lista de asistencia tradicional hecha por el docente, como **línea base** independiente.
- Un observador cronometra y anota incidencias.

### Variables a registrar

| Variable | Fuente |
|---|---|
| Matriculados / presentes / ausentes | Lista del docente y `GET /materias/{id}/alumnos` |
| Asistencias guardadas | `GET /practicas/{id}/reporte` y colección `asistencias` |
| Duración total de la práctica | `hora_inicio` y `hora_fin` de `practicas` |
| Intervenciones del docente | Hoja de incidencias (reconfirmar, repetir enrolamiento, esperar, corregir) |
| Incidencias | Tipo, hora, severidad, acción correctiva |
| Satisfacción | Encuesta anónima de 5 preguntas Likert + una abierta, para docente y alumnos |

Cuestionario sugerido (1 = muy en desacuerdo, 5 = muy de acuerdo):

1. El reconocimiento fue lo suficientemente rápido.
2. Entendí cuándo debía pararme frente a la cámara.
3. Confié en el resultado mostrado por el sistema.
4. El sistema me resultó menos cargoso que el procedimiento habitual.
5. Volvería a usar el sistema en otra práctica.

La pregunta abierta: *"¿Qué cambiarías del procedimiento?"*.

### Métricas

| Métrica | Fórmula |
|---|---|
| Cobertura | `asistencias guardadas / alumnos presentes según el docente` |
| Acuerdo con la lista tradicional | `alumnos con el mismo estado en ambas fuentes / matriculados` |
| Tiempo de paso | `duración total / alumnos presentes` |
| Intervenciones | total y por alumno |
| Incidencias bloqueantes | número de eventos que detuvieron la práctica |
| Satisfacción | mediana por pregunta + recuento de respuestas abiertas tematizadas |

### Resultado que se lleva al informe

Tabla comparativa sistema vs. lista tradicional, curva de tiempo acumulado por alumno, resumen de incidencias y cita textual anónima de la pregunta abierta. Si el frontend no existió, decirlo explícitamente: la prueba valida el backend y el flujo, no la interfaz.

---

## 8. Piloto 5 — robustez, recuperación y permisos

**Pregunta:** RQ6.  
**Importante:** ejecutarlo en una base de **prueba** con respaldo. Varios casos dejan datos inconsistentes a propósito.

### Casos propuestos

| Caso | Procedimiento | Resultado esperado según el código | Qué registrar |
|---|---|---|---|
| Reinicio en plena práctica | Iniciar práctica, matar uvicorn, volver a arrancar | Se reanuda en fase de identificación si tiene < 8 h | Estado de `practicas`, cámara encendida al arrancar |
| Práctica con más de 8 h | Manipular `hora_inicio` en la base y reiniciar | Se marca `finalizada` | Estado antes/después |
| Dos inicios simultáneos | Dos `POST /practicas` casi al mismo tiempo | Debería rechazarse la segunda con `409` | Códigos HTTP y número de prácticas activas |
| Confirmación duplicada | Confirmar dos veces al mismo alumno | Se guardan **dos** asistencias; el reporte muestra una | Conteo en `asistencias` vs. filas del reporte |
| Finalizar durante revisión | `POST /end` antes de `asistencia_registrada` | La revisión se descarta | Asistencia sí/no guardada |
| Vista previa huérfana | Encender vista previa, cerrar navegador, esperar 10 s | Se apaga sola | Consumidores activos de la cámara |
| Permisos cruzados | Docente A consulta `GET /materias/{id}/alumnos` de docente B | Hoy **lo permite** (fallo conocido) | Código HTTP y datos devueltos |
| Video global | Conectar dos WebSocket de docentes distintos | Ambos reciben los eventos de la misma práctica | Eventos por conexión |
| Token expirado | Usar un token manipulado | `401` | Código HTTP |
| Evidencia con ruta ajena | Pedir `evidencia_url` de otra materia con token de docente ajeno | Debería rechazarse por alcance | Código HTTP |
| Área medicina | Iniciar práctica de medicina y confirmar alumno | El hilo muere en silencio; práctica queda "activa" | Salida de consola y última fase observada |

### Resultado que se lleva al informe

Tabla `caso / esperado / observado / severidad / recomendación`. Este piloto no produce métricas de precisión: produce **hallazgos cualitativos** sobre robustez y seguridad. Conviene presentarlos en una sección separada del informe, para no mezclarlos con el desempeño de los modelos.

---

## 9. Cómo sacar los resultados

### 9.1 Fuentes de datos

| Fuente | Formato | Para qué sirve | Cómo se obtiene |
|---|---|---|---|
| WebSocket `/ws/detections` | JSONL, una línea por evento | Identificaciones, fases, frames, veredictos y tiempos | `scripts/capturar_eventos.py` (Apéndice A) |
| `asistencias` | Documentos en Mongo | Resultado persistente, faltantes, ruta de evidencia | `GET /asistencias` o `mongosh` |
| `practicas` | Documentos en Mongo | Estado, `hora_inicio`, `hora_fin` | `GET /practicas` o `mongosh` |
| Evidencias | JPG en `static/evidence/<fecha>/` | Auditoría visual de los "no cumple" | `GET /static/evidence/...?token=` |
| Hoja de verdad | CSV | Etiqueta humana independiente | Observador durante el piloto |
| Consola de uvicorn | Texto | Errores `[ERROR async]`, tracebacks del orquestador | Redirigir salida a `datos/<piloto>/uvicorn.log` |
| Configuración | Texto | Reproducibilidad | Plantilla de la sección 2 |

### 9.2 Limpieza

1. **Normalizar tiempos.** Convertir todos los `timestamp` a `datetime` UTC. Las fechas REST no traen zona: asumir UTC y marcarlas como tal al parsear.
2. **Quitar el ruido del inicio.** `estado_inicial` no es una medición; se usa solo para saber el estado previo.
3. **Segmentar por práctica y por fase.** Los eventos `detecciones_frame` no llevan `practica_id`: asignarlos al intervalo abierto por `fase_cambiada(indumentaria)` y cerrado por `asistencia_registrada`.
4. **Deduplicar identificaciones.** Varios eventos del mismo `alumno_id` en una sola presentación cuentan como uno.
5. **Marcar muestras inválidas.** Presentaciones sin inicio/fin, revisiones sin `asistencia_registrada` (posible fallo del hilo) y evidencias ilegibles. Se excluyen del denominador y se reporta cuántas se excluyeron.
6. **Cruzar con la verdad por `registro_id`**, nunca por nombre, para no filtrar la etiqueta.

Si se quiere reproducir exactamente la decisión del motor de indumentaria a partir de `detecciones_frame`, hay que aplicar la misma regla del código: quedar solo con el `Person` de caja más grande, ampliar su caja un 10 % de su tamaño hacia cada lado y contar solo las detecciones cuyo centro cae dentro. Contar simplemente las clases que aparecen en `items` **sobreestima** los frames útiles, porque el evento incluye todas las detecciones del frame, incluso las que el motor ignoró.

### 9.3 Cálculo

Todo se puede hacer con `polars` y `matplotlib`, que ya están en `requirements.txt`; no hace falta instalar nada nuevo.

- **Agregados:** una fila por presentación o por revisión, con columnas `real`, `sistema`, `acierto`, `condicion`, `confianza`, `frames`, `latencia`.
- **Matrices:** `group_by(real, sistema).len()`.
- **Tasas:** dividir cada celda entre el total de su fila (para sensibilidad) o de su columna (para precisión), y dejar claro cuál se usa.
- **Distribuciones:** media, mediana, desviación estándar, p90 y rango. Con muestras pequeñas, acompañar la media de la mediana: un solo reinicio puede deformar la media.
- **Incertidumbre:** si se quiere un intervalo, usar bootstrap sobre las muestras (remuestreo con reemplazo, 1000 repeticiones) e informar el intervalo del 95 %. `scipy` también está disponible.
- **Comparación de condiciones:** diferencia de tasas entre A y B/C, en puntos porcentuales, en vez de solo "mejor/peor".

### 9.4 Consultas útiles

```bash
# Asistencias de una práctica (mongosh)
db.asistencias.find({practica_id: "<id>"},
  {alumno_id: 1, cumplio_indumentaria: 1, faltantes: 1, evidencia_url: 1, hora_identificacion: 1})

# Prácticas con algún problema
db.practicas.find({estado: "activa"}).sort({hora_inicio: -1})

# Conteo de asistencias por alumno (detecta duplicados)
db.asistencias.aggregate([
  {$group: {_id: "$alumno_id", n: {$sum: 1}}},
  {$match: {n: {$gt: 1}}}
])
```

```python
# Equivalente con pymongo síncrono, dentro del entorno yolo
from pymongo import MongoClient
from app.core.config import settings

db = MongoClient(settings.mongo_url)[settings.mongo_db_name]
rows = list(db.asistencias.find({"practica_id": "<id>"}, {"_id": 0}))
```

Si se usa el reporte de la API en vez de Mongo, recordar que calcula ausencias al momento comparando matrícula y asistencias, y que **no guarda** el reporte (`ARQUITECTURA_BACKEND.md`, sección 10).

### 9.5 Diagrama de flujo del análisis

```text
JSONL de eventos  +  verdad_terreno.csv  +  asistencias (Mongo)
            │                 │                    │
            └──── normalizar UTC y cruzar por id ───┘
                              │
             ┌────────────────┼────────────────┐
             ▼                ▼                ▼
      métricas RQ1/RQ2   métricas RQ3     incidencias RQ5
             │                │                │
             └────── tablas y figuras ─────────┘
                              │
                    apartado del informe
       (método + configuración + cifra + limitación)
```

---

## 10. Plantillas para el archivo de investigación

Copiar y rellenar. Conviene que cada apartado del informe siga el orden **método → configuración → resultado → limitación**.

### 10.1 Reconocimiento facial

| Condición | Presentaciones | Reconocidos | Confundidos | Sin evento | Acierto % | Confianza media |
|---:|---:|---:|---:|---:|---:|---:|
| Luz normal | 15 | — | — | — | — | — |
| Contraluz / perfil | 15 | — | — | — | — | — |
| Gafas / cubreboca / gorra | 15 | — | — | — | — | — |
| No matriculados | 10 | — (falsas aceptaciones) | — | — | — | — |

> Texto listo: *"Con `SIMILARITY_THRESHOLD = 0.60` se reconocieron correctamente — de — presentaciones (— %); se produjeron — confusiones entre alumnos y — falsas aceptaciones. El umbral se calibró con el 60 % de la muestra y se evaluó con el 40 % restante."*

### 10.2 Indumentaria

| Escenario | Revisiones | Veredicto correcto | Falso aprobado | Falso reprobado | Frames útiles (media) |
|---:|---:|---:|---:|---:|---:|
| Casco y chaleco | 20 | — | — | — | — |
| Falta casco | 15 | — | — | — | — |
| Falta chaleco | 15 | — | — | — | — |

> Texto listo: *"El veredicto coincidió con el observador en — de — revisiones (— %). El error más frecuente fue —, con — casos. Con `REVIEW_CONFIRM_FRAMES = —` y `REVIEW_PERSON_MARGIN = —` se analizaron — frames por revisión de media."*

### 10.3 Latencia

| Métrica | p50 | p90 | Máximo |
|---:|---:|---:|---:|
| Latencia de identificación (s) | — | — | — |
| Duración de la revisión (s) | — | — | — |
| Frames analizados | — | — | — |
| Tiempo total por alumno (s) | — | — | — |

> Texto listo: *"La revisión duró — s de media frente a los 6 s configurados, y se analizaron — frames. La primera revisión de la sesión, con los modelos aún sin cargar, tardó — s."*

### 10.4 Integración

| Indicador | Sistema | Lista tradicional |
|---:|---:|---:|
| Alumnos presentes registrados | — | — |
| Ausentes correctamente detectados | — | — |
| Tiempo total (min) | — | — |
| Minutos por alumno | — | — |

### 10.5 Declaración de alcance (obligatoria)

> *"Los resultados corresponden a — prácticas, — alumnos y un único laboratorio con cámara fija a — m. No se evaluaron otras áreas porque `medicina.pt` no existe en esta versión. Los parámetros usados fueron —. Las cifras no se extrapolan a otras aulas, modelos de cámara o políticas de iluminación."*

---

## 11. Ética, privacidad y validez

El sistema trata **datos biométricos**. `ARQUITECTURA_BACKEND.md` (sección 13) señala que el código no implementa consentimiento y que las imágenes de evidencia se guardan sin cifrar y sin política de borrado. Antes de cualquier piloto con personas:

- [ ] Consentimiento informado por escrito de cada alumno, explicando qué se captura, dónde se guarda y cuánto tiempo se conserva.
- [ ] Alternativa equivalente para quien no quiera participar (no debe afectar su calificación).
- [ ] Revisar la normativa local sobre datos biométricos antes de publicar cualquier cifra o imagen.
- [ ] Seudonimizar códigos en el informe; no publicar rostros ni evidencias sin autorización explícita.
- [ ] Borrar al final del estudio las evidencias y la base de prueba, y documentar el borrado.
- [ ] No usar los resultados del piloto para calificar a los alumnos.

**Amenazas a la validez que hay que anotar en el informe:**

| Amenaza | Cómo mitigarla |
|---|---|
| Efecto Hawthorne: los alumnos posan mejor porque saben que se mide | Repetir una sesión sin aviso previo (con consentimiento general firmado) |
| Mismo experto etiqueta y opera | Usar un observador independiente y ciego al resultado |
| Ajustar umbrales con la misma muestra que se reporta | Separar calibración (60 %) y evaluación (40 %) |
| Cargar modelos en la primera revisión | Reportar la primera revisión por separado |
| Una sola cámara y un solo aula | Declarar el alcance; no generalizar |
| Muestra pequeña | Acompañar tasas con recuentos absolutos e intervalos bootstrap |

---

## 12. Plan de ejecución

| Orden | Piloto | Bloqueante para los demás | Resultado principal |
|---:|---|---|---|
| 0 | Preparación e instrumentos | Sí: sin captura no hay datos | JSONL válido |
| 1 | Reconocimiento facial | No | RQ1, RQ4, calibración de umbral |
| 2 | Indumentaria | No | RQ2, calibración de reglas |
| 3 | Latencia | No (usa datos de 1 y 2) | RQ3 |
| 4 | Integración en aula | Recomienda terminar 1 y 2 | RQ5 |
| 5 | Robustez y permisos | No, pero en base de prueba | RQ6 |

**Mínimo publicable:** piloto 0 + piloto 1 + piloto 2 con al menos 30 presentaciones y 40 revisiones. Con eso ya se pueden responder RQ1 y RQ2 con cifras propias, que es lo que hoy falta en la documentación. El piloto 4 agrega validez ecológica; el 5 agrega ingeniería y seguridad.

**Orden de prioridad si hay poco tiempo:** 0 → 2 → 1 → 4 → 3 → 5. El veredicto de indumentaria es el corazón del sistema y el que tiene el fallo conocido más visible (falso reprobado por no detectar a la persona).

---

## 13. Apéndice A — capturar eventos a JSONL

Crear `scripts/capturar_eventos.py`. Usa `websockets` (ya en `requirements.txt`) y no modifica el backend.

```python
"""Captura los eventos del WebSocket en un archivo JSONL.

Uso:
    python -m scripts.capturar_eventos <token> datos/piloto1/eventos.jsonl
"""
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import websockets

WS_URL = "ws://127.0.0.1:8000/ws/detections"


async def main(token: str, salida: str) -> None:
    ruta = Path(salida)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    async with websockets.connect(f"{WS_URL}?token={token}") as ws:
        with ruta.open("a", encoding="utf-8") as f:
            print(f"Capture iniciada en {ruta}. Ctrl+C para detener.")
            async for raw in ws:
                evento = json.loads(raw)
                evento["recibido_en"] = datetime.now(timezone.utc).isoformat()
                f.write(json.dumps(evento, ensure_ascii=False) + "\n")
                f.flush()
                print(evento.get("evento"), evento.get("timestamp", ""))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Uso: python -m scripts.capturar_eventos <token> <archivo.jsonl>")
    asyncio.run(main(sys.argv[1], sys.argv[2]))
```

**Notas:** el token se obtiene con `POST /api/v1/auth/login` (`Orden.md`, terminal 3). Solo pueden conectarse `docente`, `coordinador` y `admin`; un `alumno` recibe el código de cierre `1008`. Si la conexión se corta, reiniciar el script: no reconecta automáticamente. El token en la URL queda en logs e historial, así que no compartirlo y usarlo solo en local.

Útil para sincronizar la hoja de verdad:

```bash
date -u +"%Y-%m-%dT%H:%M:%S+00:00"
```

---

## 14. Apéndice B — análisis con Polars

Esqueleto mínimo para convertir el JSONL en una tabla de revisiones. Asume `polars` y `matplotlib` del entorno.

```python
import json
from datetime import datetime
from pathlib import Path

import polars as pl


def cargar_eventos(ruta: str) -> pl.DataFrame:
    filas = [json.loads(linea) for linea in Path(ruta).read_text().splitlines() if linea.strip()]
    df = pl.DataFrame(filas)
    return df.with_columns(
        pl.col("timestamp").str.to_datetime(strict=False).alias("ts_utc")
    ).sort("ts_utc")


def revisiones_desde_eventos(df: pl.DataFrame) -> pl.DataFrame:
    """Une cada fase de indumentaria con su asistencia_registrada."""
    fases = (
        df.filter(pl.col("evento") == "fase_cambiada", pl.col("fase") == "indumentaria")
          .select(["ts_utc", "practica_id"])
          .rename({"ts_utc": "inicio"})
    )
    cierres = (
        df.filter(pl.col("evento") == "asistencia_registrada")
          .select([
              "ts_utc", "alumno_id", "cumplio_indumentaria", "faltantes", "evidencia_url"
          ])
          .rename({"ts_utc": "fin"})
    )
    return fases.with_columns(
        pl.col("inicio").rank("ordinal").alias("n")
    ).join(
        cierres.with_columns(pl.col("fin").rank("ordinal").alias("n")), on="n"
    ).with_columns(
        (pl.col("fin") - pl.col("inicio")).dt.total_seconds().alias("duracion_s")
    )


def items_sobre_persona(items, margen=0.10):
    """Replica el filtro del compliance_engine sobre bbox_norm [x1,y1,x2,y2]."""
    personas = [i for i in items if i["class_name"] == "Person"]
    if not personas:
        return []
    p = max(
        personas,
        key=lambda i: (i["bbox_norm"][2] - i["bbox_norm"][0])
                      * (i["bbox_norm"][3] - i["bbox_norm"][1]),
    )
    x1, y1, x2, y2 = p["bbox_norm"]
    dx, dy = (x2 - x1) * margen, (y2 - y1) * margen
    x1, x2, y1, y2 = x1 - dx, x2 + dx, y1 - dy, y2 + dy
    utiles = []
    for i in items:
        bx1, by1, bx2, by2 = i["bbox_norm"]
        cx, cy = (bx1 + bx2) / 2, (by1 + by2) / 2
        if x1 <= cx <= x2 and y1 <= cy <= y2:
            utiles.append(i)
    return utiles


def frames_por_revision(df: pl.DataFrame) -> dict[str, int]:
    """Cuenta frames totales y frames con Person por alumno confirmado."""
    totales: dict[str, int] = {}
    actual = None
    for fila in df.iter_rows(named=True):
        evento = fila["evento"]
        if evento == "fase_cambiada" and fila.get("fase") == "indumentaria":
            actual = fila["practica_id"]
        elif evento == "detecciones_frame" and actual is not None:
            totales[actual] = totales.get(actual, 0) + 1
        elif evento == "asistencia_registrada":
            actual = None
    return totales


if __name__ == "__main__":
    eventos = cargar_eventos("datos/piloto2/eventos.jsonl")
    revisiones = revisiones_desde_eventos(eventos)
    print(revisiones.select([
        "alumno_id", "cumplio_indumentaria", "faltantes", "duracion_s"
    ]))
    verdad = pl.read_csv("datos/piloto2/verdad_terreno.csv", try_parse_dates=True)
    comparado = revisiones.join(verdad, on="alumno_id", how="inner")
    print(comparado.group_by(["cumple_real", "cumplio_indumentaria"]).len())
```

**Advertencia:** el emparejamiento por `alumno_id` del esqueleto es ilustrativo. En un piloto real, cruzar por `registro_id` o por ventana temporal `[inicio_utc, fin_utc]`, porque un mismo alumno puede revisarse más de una vez y el CSV de verdad es la fuente de la etiqueta.

---

## Cierre

Este documento solo propone. Para convertirlo en evidencia, hace falta ejecutar los pilotos y rellenar las plantillas con datos reales. Hasta entonces, cualquier cifra de desempeño que se escriba en el archivo de investigación debe ir acompañada de la configuración exacta con la que se midió y de la limitación correspondiente.
