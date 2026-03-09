import csv
import json
from pathlib import Path

from api_datos_epok import (
    resolve_smp_from_address,
    catastro_geometria_by_smp,
    geojson_area_m2,
    geojson_centroid_xy,
)

# ================= CONFIG =================

INPUT_FILE = "direcciones.txt"
OUT_DIR = Path("salida_lotes")
OUT_DIR.mkdir(exist_ok=True)

CSV_RESUMEN = OUT_DIR / "resumen.csv"


# ================= HELPERS =================

def guardar_json(path: Path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ================= MAIN =================

def main():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        direcciones = [line.strip() for line in f if line.strip()]

    filas_resumen = []

    for i, direccion in enumerate(direcciones, start=1):
        print("=" * 80)
        print(f"[{i}/{len(direcciones)}] Procesando: {direccion}")

        caso_id = f"{i:03d}"
        caso_dir = OUT_DIR / caso_id
        caso_dir.mkdir(exist_ok=True)

        resultado = {
            "direccion": direccion,
            "smp": None,
            "area_m2": None,
            "centroid_x": None,
            "centroid_y": None,
            "geometria_tipo": None,
            "ok": False,
            "error": None,
        }

        try:
            smp, dbg = resolve_smp_from_address(direccion)
            guardar_json(caso_dir / "debug_resolve_smp.json", dbg)

            resultado["smp"] = smp

            if smp:
                geo = catastro_geometria_by_smp(smp)
                guardar_json(caso_dir / "geometria.json", geo)

                area = geojson_area_m2(geo)
                cx, cy = geojson_centroid_xy(geo)

                resultado["area_m2"] = area
                resultado["centroid_x"] = cx
                resultado["centroid_y"] = cy

                # detectar tipo geometrico
                geom_type = None
                if isinstance(geo, dict):
                    t = geo.get("type")
                    if t == "FeatureCollection" and geo.get("features"):
                        geom_type = geo["features"][0].get("geometry", {}).get("type")
                    elif t == "Feature":
                        geom_type = geo.get("geometry", {}).get("type")
                    else:
                        geom_type = geo.get("type")

                resultado["geometria_tipo"] = geom_type
                resultado["ok"] = True

            else:
                resultado["error"] = "No se pudo resolver SMP"

        except Exception as e:
            resultado["error"] = str(e)

        guardar_json(caso_dir / "resultado.json", resultado)
        filas_resumen.append(resultado)

    # Guardar resumen CSV
    with open(CSV_RESUMEN, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "direccion",
                "smp",
                "area_m2",
                "centroid_x",
                "centroid_y",
                "geometria_tipo",
                "ok",
                "error",
            ],
        )
        writer.writeheader()
        writer.writerows(filas_resumen)

    print("\nProceso terminado.")
    print("Resumen guardado en:", CSV_RESUMEN)


if __name__ == "__main__":
    main()