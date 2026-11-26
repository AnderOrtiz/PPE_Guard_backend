"""
Piloto de indumentaria (área civil) SIN levantar el backend completo.

Captura una "revisión" de 6 s con la cámara, corre YOLO frame a frame, emula el
veredicto del backend y guarda los datos para los pilotos 2 (acierto del veredicto)
y 3 (latencia / frames analizados / CPU / memoria).

Uso (desde la raíz del repo, con el entorno activado):

  # 1) Capturar. El observador declara ANTES la verdad de terreno:
  python -m scripts.piloto_indumentaria capturar --condicion completo --n 10
  python -m scripts.piloto_indumentaria capturar --condicion sin_casco --faltan Hardhat --n 10
  python -m scripts.piloto_indumentaria capturar --condicion sin_chaleco --faltan "Safety Vest" --n 10
  python -m scripts.piloto_indumentaria capturar --condicion nada --faltan "Hardhat,Safety Vest" --n 5

  # 2) Analizar (se puede repetir cambiando parámetros SIN volver a capturar):
  python -m scripts.piloto_indumentaria analizar
  python -m scripts.piloto_indumentaria analizar --confirm-frames 2 --margen 0.2

Salida en datos/piloto2/:
  revisiones.csv  una fila por revisión (verdad de terreno, veredicto, tiempos, CPU, RAM)
  frames.jsonl    detecciones crudas de cada frame (permite recalibrar sin recapturar)
  fotos/          (opcional, --fotos) último frame de cada revisión, sin anotar
"""
import argparse
import csv
import json
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from app.services.yolo_service import detect

try:
    import psutil
except ImportError:  # ultralytics suele traerlo; si no, se omite CPU/RAM
    psutil = None

AREA = "civil"
REQUERIDO = ["Hardhat", "Safety Vest"]  # ppe_requerido del área civil

DIR = Path("datos/piloto2")
CSV_PATH = DIR / "revisiones.csv"
FRAMES_PATH = DIR / "frames.jsonl"
FOTOS_DIR = DIR / "fotos"

# Parámetros de diseño del backend (según la documentación).
DURACION = 6.0         # segundos de revisión
INTERVALO = 0.3        # pausa entre análisis
CONFIRM_FRAMES = 3     # frames mínimos para dar una prenda por puesta
MARGEN = 0.10          # holgura de la caja Person

CAMPOS = (
    ["registro_id", "fecha_utc", "condicion", "area", "confirm_frames", "margen",
     "faltantes_reales", "faltantes_sistema", "cumple_real", "cumple_sistema", "acierto",
     "frames", "frames_utiles"]
    + [f"{pre}_{p}" for p in REQUERIDO for pre in ("pos", "neg")]
    + ["duracion_s", "fps_analizados", "lat_media_ms", "lat_max_ms",
       "cpu_pct", "rss_mb", "primera_de_sesion"]
)


# --------------------------------------------------------------------------
# Veredicto (réplica de la lógica descrita en GUIA_MODELOS.md, sección 1)
# --------------------------------------------------------------------------
def _area(b):
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def evaluar(frames, confirm_frames=CONFIRM_FRAMES, margen=MARGEN):
    """frames: lista de listas de detecciones. Devuelve (faltantes, frames_utiles, pos, neg)."""
    pos, neg = Counter(), Counter()
    utiles = 0
    for dets in frames:
        personas = [d for d in dets if d["class_name"] == "Person"]
        if not personas:
            continue  # sin Person el frame no cuenta
        utiles += 1
        x1, y1, x2, y2 = max(personas, key=lambda d: _area(d["bbox"]))["bbox"]
        mx, my = (x2 - x1) * margen, (y2 - y1) * margen
        vistos = set()
        for d in dets:
            nombre = d["class_name"]
            if nombre == "Person":
                continue
            bx1, by1, bx2, by2 = d["bbox"]
            cx, cy = (bx1 + bx2) / 2, (by1 + by2) / 2
            if x1 - mx <= cx <= x2 + mx and y1 - my <= cy <= y2 + my:
                vistos.add(nombre)
        for nombre in vistos:
            if nombre in REQUERIDO:
                pos[nombre] += 1
            elif nombre.startswith("NO-") and nombre[3:] in REQUERIDO:
                neg[nombre[3:]] += 1
    faltantes = [p for p in REQUERIDO if not (pos[p] >= confirm_frames and pos[p] > neg[p])]
    return faltantes, utiles, pos, neg


# --------------------------------------------------------------------------
# Captura
# --------------------------------------------------------------------------
def _siguiente_id():
    if not CSV_PATH.exists():
        return "R001"
    with open(CSV_PATH, encoding="utf-8") as fh:
        n = sum(1 for _ in fh) - 1  # menos la cabecera
    return f"R{n + 1:03d}"


def _revision(cap, estado):
    """Una revisión de DURACION s, analizando un frame cada INTERVALO s."""
    registros = []
    ultimo = None
    proc = psutil.Process() if psutil else None
    if proc:
        proc.cpu_percent(None)  # inicia la ventana de medición
    inicio = time.monotonic()
    proximo = inicio
    while time.monotonic() - inicio < DURACION:
        ret, frame = cap.read()  # se lee siempre para no analizar frames viejos del buffer
        if not ret or time.monotonic() < proximo:
            continue
        t0 = time.perf_counter()
        dets = detect(frame, area=AREA)
        lat_ms = (time.perf_counter() - t0) * 1000
        proximo = time.monotonic() + INTERVALO
        registros.append({
            "t": round(time.monotonic() - inicio, 3),
            "lat_ms": round(lat_ms, 1),
            "frio": estado["frio"],
            "dets": [{"class_name": d["class_name"],
                      "confidence": round(float(d["confidence"]), 3),
                      "track_id": d.get("track_id"),
                      "bbox": [round(float(v), 1) for v in d["bbox"]]} for d in dets],
        })
        estado["frio"] = False
        ultimo = frame
    duracion = time.monotonic() - inicio
    cpu = proc.cpu_percent(None) if proc else ""
    rss = round(proc.memory_info().rss / 1e6, 1) if proc else ""
    return registros, ultimo, duracion, cpu, rss


def cmd_capturar(args):
    faltan = [x.strip() for x in args.faltan.split(",") if x.strip()]
    invalidas = [x for x in faltan if x not in REQUERIDO]
    if invalidas:
        raise SystemExit(f"--faltan solo admite {REQUERIDO}; recibí {invalidas}")
    DIR.mkdir(parents=True, exist_ok=True)
    if args.fotos:
        FOTOS_DIR.mkdir(exist_ok=True)

    cap = cv2.VideoCapture(args.camara)
    for _ in range(10):  # la cámara ajusta exposición
        cap.read()

    estado = {"frio": True}  # solo la primera inferencia del proceso carga el modelo
    nuevo_csv = not CSV_PATH.exists()
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as fcsv, \
         open(FRAMES_PATH, "a", encoding="utf-8") as fjson:
        w = csv.DictWriter(fcsv, fieldnames=CAMPOS)
        if nuevo_csv:
            w.writeheader()
            fcsv.flush()  # para que _siguiente_id cuente bien la cabecera
        for k in range(args.n):
            input(f"\n[{k + 1}/{args.n}] condición='{args.condicion}' | "
                  f"faltan realmente: {faltan or 'ninguna'}\n"
                  f"Colócate y pulsa Enter... ")
            time.sleep(args.espera)
            primera = estado["frio"]
            rid = _siguiente_id()
            registros, ultimo, dur, cpu, rss = _revision(cap, estado)
            if not registros:
                print("  ✘ No se analizó ningún frame (¿cámara ocupada?). Revisión descartada.")
                continue

            falt_sis, utiles, pos, neg = evaluar([r["dets"] for r in registros],
                                                 CONFIRM_FRAMES, MARGEN)
            lats = [r["lat_ms"] for r in registros]
            cumple_real, cumple_sis = not faltan, not falt_sis
            fila = {
                "registro_id": rid,
                "fecha_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "condicion": args.condicion, "area": AREA,
                "confirm_frames": CONFIRM_FRAMES, "margen": MARGEN,
                "faltantes_reales": "|".join(faltan), "faltantes_sistema": "|".join(falt_sis),
                "cumple_real": "si" if cumple_real else "no",
                "cumple_sistema": "si" if cumple_sis else "no",
                "acierto": int(cumple_real == cumple_sis),
                "frames": len(registros), "frames_utiles": utiles,
                "duracion_s": round(dur, 2),
                "fps_analizados": round(len(registros) / dur, 2),
                "lat_media_ms": round(float(np.mean(lats)), 1),
                "lat_max_ms": round(max(lats), 1),
                "cpu_pct": cpu, "rss_mb": rss, "primera_de_sesion": int(primera),
            }
            for p in REQUERIDO:
                fila[f"pos_{p}"], fila[f"neg_{p}"] = pos[p], neg[p]
            w.writerow(fila)
            fcsv.flush()
            for i, r in enumerate(registros):
                fjson.write(json.dumps({"registro_id": rid, "i": i, **r}, default=float) + "\n")
            fjson.flush()
            if args.fotos and ultimo is not None:
                cv2.imwrite(str(FOTOS_DIR / f"{rid}.jpg"), ultimo)

            marca = "✔" if fila["acierto"] else "✘"
            print(f"  {marca} {rid}: sistema={fila['cumple_sistema']} "
                  f"(faltan {falt_sis or 'ninguna'}) | real={fila['cumple_real']} | "
                  f"frames={len(registros)} útiles={utiles} | "
                  f"lat media={fila['lat_media_ms']} ms"
                  f"{' (incluye carga del modelo)' if primera else ''}")
    cap.release()


# --------------------------------------------------------------------------
# Análisis
# --------------------------------------------------------------------------
def _pc(x):
    return "—" if x is None else f"{x * 100:.1f} %"


def _pct(v, p):
    return float(np.percentile(v, p)) if len(v) else float("nan")


def cmd_analizar(args):
    if not CSV_PATH.exists() or not FRAMES_PATH.exists():
        raise SystemExit("No hay datos. Corre primero el comando 'capturar'.")
    with open(CSV_PATH, encoding="utf-8") as fh:
        filas = list(csv.DictReader(fh))
    dets_por_id, lat_cal, lat_frio = defaultdict(list), [], []
    with open(FRAMES_PATH, encoding="utf-8") as fh:
        for linea in fh:
            r = json.loads(linea)
            dets_por_id[r["registro_id"]].append(r["dets"])
            (lat_frio if r["frio"] else lat_cal).append(r["lat_ms"])

    res = []
    for f in filas:
        falt_sis, utiles, _, _ = evaluar(dets_por_id[f["registro_id"]],
                                         args.confirm_frames, args.margen)
        falt_real = {x for x in f["faltantes_reales"].split("|") if x}
        res.append({"cond": f["condicion"], "real": falt_real, "sis": set(falt_sis),
                    "cumple_real": not falt_real, "cumple_sis": not falt_sis,
                    "frames": int(f["frames"]), "utiles": utiles,
                    "dur": float(f["duracion_s"]), "fps": float(f["fps_analizados"]),
                    "cpu": f["cpu_pct"], "rss": f["rss_mb"]})
    n = len(res)
    print(f"\n=== Piloto 2 — veredicto de indumentaria ({n} revisiones) ===")
    print(f"Parámetros: confirm_frames={args.confirm_frames}, margen={args.margen}\n")

    # Matriz de confusión
    vp = sum(r["cumple_real"] and r["cumple_sis"] for r in res)
    fn = sum(r["cumple_real"] and not r["cumple_sis"] for r in res)   # falso reprobado
    fp = sum(not r["cumple_real"] and r["cumple_sis"] for r in res)   # falso aprobado
    vn = sum(not r["cumple_real"] and not r["cumple_sis"] for r in res)
    print("Matriz de confusión (filas = real, columnas = sistema)")
    print(f"{'':14}{'cumple':>10}{'no cumple':>12}")
    print(f"{'real cumple':14}{vp:>10}{fn:>12}")
    print(f"{'real no cumple':14}{fp:>10}{vn:>12}\n")

    reales_si, reales_no = vp + fn, fp + vn
    print(f"Exactitud del veredicto : {_pc((vp + vn) / n if n else None)}")
    print(f"Falso aprobado (FAR)    : {_pc(fp / reales_no if reales_no else None)}  "
          f"({fp}/{reales_no})  <- el error grave")
    print(f"Falso reprobado (FRR)   : {_pc(fn / reales_si if reales_si else None)}  "
          f"({fn}/{reales_si})")
    exactos = sum(r["real"] == r["sis"] for r in res)
    print(f"Lista de faltantes exacta: {_pc(exactos / n if n else None)}\n")

    print("Exactitud por prenda")
    for p in REQUERIDO:
        ok = sum((p in r["sis"]) == (p in r["real"]) for r in res)
        print(f"  {p:12} {ok}/{n}  ({_pc(ok / n if n else None)})")

    print("\nPor escenario")
    print(f"{'condicion':18}{'n':>4}{'exactitud':>11}{'FAR':>8}{'FRR':>8}"
          f"{'útiles(media)':>15}{'útiles(mín)':>13}")
    por_cond = defaultdict(list)
    for r in res:
        por_cond[r["cond"]].append(r)
    for cond, rs in por_cond.items():
        k = len(rs)
        ex = sum(r["cumple_real"] == r["cumple_sis"] for r in rs) / k
        no = [r for r in rs if not r["cumple_real"]]
        si = [r for r in rs if r["cumple_real"]]
        far = sum(r["cumple_sis"] for r in no) / len(no) if no else None
        frr = sum(not r["cumple_sis"] for r in si) / len(si) if si else None
        ut = [r["utiles"] for r in rs]
        print(f"{cond:18}{k:>4}{_pc(ex):>11}{_pc(far):>8}{_pc(frr):>8}"
              f"{np.mean(ut):>15.1f}{min(ut):>13}")

    print("\n=== Piloto 3 — latencia y frames (solo inferencia YOLO, sin backend) ===")
    print(f"{'métrica':44}{'p50':>9}{'p90':>9}{'máx':>9}")
    filas_lat = [
        ("Latencia por frame, modelo caliente (ms)", lat_cal),
        ("Frames analizados por revisión", [r["frames"] for r in res]),
        ("Frames útiles por revisión", [r["utiles"] for r in res]),
        ("Duración real de la revisión (s)", [r["dur"] for r in res]),
        ("Frames por segundo analizados", [r["fps"] for r in res]),
    ]
    for nombre, v in filas_lat:
        print(f"{nombre:44}{_pct(v, 50):>9.1f}{_pct(v, 90):>9.1f}{max(v) if v else float('nan'):>9.1f}")
    if lat_frio:
        print(f"\nPrimera inferencia de la sesión (carga del modelo): "
              f"{', '.join(f'{x:.0f} ms' for x in lat_frio)}")
    cpus = [float(r["cpu"]) for r in res if r["cpu"] != ""]
    rss = [float(r["rss"]) for r in res if r["rss"] != ""]
    if cpus:
        print(f"CPU durante la revisión: media {np.mean(cpus):.0f} % (puede pasar de 100 % con varios núcleos)")
    if rss:
        print(f"Memoria del proceso (RSS): máx {max(rss):.0f} MB")
    print("\nTeórico: 6 s / 0.3 s = 20 frames como máximo; menos según lo que tarde cada inferencia.")


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("capturar", help="Graba revisiones de 6 s con la cámara")
    c.add_argument("--condicion", required=True, help="etiqueta del escenario, p. ej. sin_casco")
    c.add_argument("--faltan", default="", help='prendas que REALMENTE faltan, separadas por coma. Vacío = cumple')
    c.add_argument("--n", type=int, default=1, help="cuántas revisiones seguidas (default 1)")
    c.add_argument("--camara", type=int, default=0)
    c.add_argument("--espera", type=float, default=2.0, help="segundos entre Enter y el inicio")
    c.add_argument("--fotos", action="store_true", help="guarda el último frame (contiene rostros)")
    c.set_defaults(func=cmd_capturar)

    a = sub.add_parser("analizar", help="Calcula las métricas desde datos/piloto2/")
    a.add_argument("--confirm-frames", type=int, default=CONFIRM_FRAMES)
    a.add_argument("--margen", type=float, default=MARGEN)
    a.set_defaults(func=cmd_analizar)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

# python -m scripts.piloto_indumentaria analizar

# python -m scripts.piloto_indumentaria capturar --condicion completo --n 10
# python -m scripts.piloto_indumentaria capturar --condicion sin_casco --faltan Hardhat --n 10
# python -m scripts.piloto_indumentaria capturar --condicion sin_chaleco --faltan "Safety Vest" --n 10