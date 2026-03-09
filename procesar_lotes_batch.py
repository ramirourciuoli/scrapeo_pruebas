import csv
import json
import time
from pathlib import Path

import requests


# ================= CONFIG =================

INPUT_FILE = "direcciones.txt"
OUT_DIR = Path("salida_lotes_batch")
OUT_DIR.mkdir(exist_ok=True)

CSV_RESUMEN = OUT_DIR / "resumen.csv"

API_URL = "http://127.0.0.1:8000/api/catastro"
TIMEOUT = 120   # segundos
PAUSA_ENTRE_CONSULTAS = 0.5  # segundos


# ================= HELPERS =================

def guardar_json(path: Path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def post_catastro(direccion: str) -> dict:
    payload = {"direccion": direccion}
    r = requests.post(API_URL, json=payload, timeout=TIMEOUT)

    # Intentamos parsear siempre como JSON
    try:
        data = r.json()
    except Exception:
        data = {
            "ok": False,
            "error": "La respuesta no fue JSON válido",
            "status_code": r.status_code,
            "text": r.text,
        }

    # guardamos status por si vino 404/500 pero con JSON útil
    if isinstance(data, dict):
        data["_http_status"] = r.status_code

    return data


def extraer_resumen(resultado: dict, direccion: str) -> dict:
    parcela = resultado.get("parcela") or {}
    datos_utiles = resultado.get("datos_utiles") or {}
    ciudad3d = resultado.get("ciudad3d") or {}

    cur3d = ciudad3d.get("cur3d") if isinstance(ciudad3d, dict) else {}
    seccion_edif = cur3d.get("seccion_edificabilidad") if isinstance(cur3d, dict) else {}

    altura_max = seccion_edif.get("altura_max")
    unidad_edificabilidad = seccion_edif.get("unidad_edificabilidad")
    manzanas_atipicas = seccion_edif.get("manzanas_atipicas")

    return {
        "direccion": direccion,
        "ok": resultado.get("ok"),
        "http_status": resultado.get("_http_status"),
        "error": resultado.get("error"),

        "smp": resultado.get("smp"),
        "seccion": parcela.get("seccion"),
        "manzana": parcela.get("manzana"),
        "parcela": parcela.get("parcela"),

        "frente": parcela.get("frente"),
        "fondo": parcela.get("fondo"),
        "superficie_total": parcela.get("superficie_total"),
        "superficie_cubierta": parcela.get("superficie_cubierta"),
        "unidades_funcionales": parcela.get("unidades_funcionales"),
        "propiedad_horizontal": parcela.get("propiedad_horizontal"),

        "area_m2": resultado.get("area_m2"),
        "centroid_x": (resultado.get("centroide_xy") or {}).get("x"),
        "centroid_y": (resultado.get("centroide_xy") or {}).get("y"),
        "centroid_lon": (resultado.get("centroide_lonlat") or {}).get("lon"),
        "centroid_lat": (resultado.get("centroide_lonlat") or {}).get("lat"),

        "comuna": datos_utiles.get("comuna"),
        "barrio": datos_utiles.get("barrio"),
        "codigo_postal": datos_utiles.get("codigo_postal"),
        "codigo_postal_argentino": datos_utiles.get("codigo_postal_argentino"),

        "altura_max": json.dumps(altura_max, ensure_ascii=False) if altura_max is not None else None,
        "altura_max_plano_limite": seccion_edif.get("altura_max_plano_limite"),
        "unidad_edificabilidad": json.dumps(unidad_edificabilidad, ensure_ascii=False) if unidad_edificabilidad is not None else None,
        "sup_edificable_planta": seccion_edif.get("sup_edificable_planta"),
        "superficie_parcela_ciudad3d": seccion_edif.get("superficie_parcela"),

        "irregular": seccion_edif.get("irregular"),
        "tipica": seccion_edif.get("tipica"),
        "memo": seccion_edif.get("memo"),
        "microcentr": seccion_edif.get("microcentr"),
        "lr": seccion_edif.get("lr"),
        "rivolta": seccion_edif.get("rivolta"),
        "adps": seccion_edif.get("adps"),

        "distrito_especial": json.dumps(seccion_edif.get("distrito_especial"), ensure_ascii=False) if seccion_edif.get("distrito_especial") is not None else None,
        "catalogacion": json.dumps(seccion_edif.get("catalogacion"), ensure_ascii=False) if seccion_edif.get("catalogacion") is not None else None,
        "afectaciones": json.dumps(seccion_edif.get("afectaciones"), ensure_ascii=False) if seccion_edif.get("afectaciones") is not None else None,
        "fot": json.dumps(seccion_edif.get("fot"), ensure_ascii=False) if seccion_edif.get("fot") is not None else None,
        "plusvalia": json.dumps(seccion_edif.get("plusvalia"), ensure_ascii=False) if seccion_edif.get("plusvalia") is not None else None,
        "manzanas_atipicas": json.dumps(manzanas_atipicas, ensure_ascii=False) if manzanas_atipicas is not None else None,

        "croquis_parcela": ((seccion_edif.get("link_imagen") or {}).get("croquis_parcela") if isinstance(seccion_edif.get("link_imagen"), dict) else None),
        "perimetro_manzana": ((seccion_edif.get("link_imagen") or {}).get("perimetro_manzana") if isinstance(seccion_edif.get("link_imagen"), dict) else None),
        "plano_indice": ((seccion_edif.get("link_imagen") or {}).get("plano_indice") if isinstance(seccion_edif.get("link_imagen"), dict) else None),
    }


# ================= MAIN =================

def main():
    input_path = Path(INPUT_FILE)

    if not input_path.exists():
        print(f"ERROR: no existe {INPUT_FILE}")
        return

    with open(input_path, "r", encoding="utf-8") as f:
        direcciones = [line.strip() for line in f if line.strip()]

    if not direcciones:
        print("ERROR: direcciones.txt está vacío")
        return

    print(f"Se procesarán {len(direcciones)} direcciones")
    print(f"Consultando backend real en: {API_URL}")

    filas_resumen = []

    for i, direccion in enumerate(direcciones, start=1):
        print("=" * 80)
        print(f"[{i}/{len(direcciones)}] Procesando: {direccion}")

        caso_id = f"{i:04d}"
        caso_dir = OUT_DIR / caso_id
        caso_dir.mkdir(exist_ok=True)

        try:
            resultado = post_catastro(direccion)

        except requests.exceptions.RequestException as e:
            resultado = {
                "ok": False,
                "error": f"Error de conexión con backend: {e}",
                "_http_status": None,
            }

        guardar_json(caso_dir / "resultado_completo.json", resultado)

        fila = extraer_resumen(resultado, direccion)
        filas_resumen.append(fila)

        time.sleep(PAUSA_ENTRE_CONSULTAS)

    with open(CSV_RESUMEN, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=list(filas_resumen[0].keys())
        )
        writer.writeheader()
        writer.writerows(filas_resumen)

    print("\nProceso terminado.")
    print("Resultados guardados en:", OUT_DIR.resolve())
    print("Resumen CSV:", CSV_RESUMEN.resolve())


if __name__ == "__main__":
    main()