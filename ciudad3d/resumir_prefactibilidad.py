import json
from pathlib import Path
from datetime import date

# -------------------------------------------------------
# UTILIDADES
# -------------------------------------------------------

def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def round1(x):
    try:
        return round(float(x), 1)
    except:
        return None




def cargar_codigo_urbanistico():
    path = Path("salida_json/codigo_urbanistico.json")
    if not path.exists():
        return None
    return load_json(path)


# -------------------------------------------------------
# PROCESO PRINCIPAL
# -------------------------------------------------------

def resumir_prefactibilidad(input_file: str):

    p = Path(input_file)
    data = load_json(p)

    codigo_urbanistico = cargar_codigo_urbanistico()

    # -----------------------------
    # BLOQUES BASE
    # -----------------------------

    cur3d = data.get("cur3d", {}) or {}
    edif_raw = cur3d.get("seccion_edificabilidad", {}) or {}

    afect_raw = edif_raw.get("afectaciones", {}) or {}
    fot_raw = edif_raw.get("fot", {}) or {}

    normalizada = data.get("normalizada_elegida", {}) or {}
    datos_utiles = data.get("datos_utiles", {}) or {}

    # -----------------------------
    # IDENTIFICACIÓN
    # -----------------------------

    identificacion = {
        "direccion": normalizada.get("direccion"),
        "smp": cur3d.get("smp"),
        "comuna": datos_utiles.get("comuna"),
        "barrio": datos_utiles.get("barrio"),
    }

    # -----------------------------
    # PARCELA
    # -----------------------------

    ff = cargar_frente_fondo()

    parcela = {
        "superficie_lote_m2": round1(edif_raw.get("superficie_parcela")),
        "frente_m": ff.get("frente_m"),
        "fondo_m": ff.get("fondo_m"),
    }

    # -----------------------------
    # EDIFICABILIDAD
    # -----------------------------

    zona = None
    altura_max = None
    articulo_cu = None

    # PRIORIDAD 1: Código Urbanístico (si existe)
    if codigo_urbanistico:
        zona = codigo_urbanistico.get("unidad")
        altura_max = codigo_urbanistico.get("altura_maxima_m")
        articulo_cu = codigo_urbanistico.get("articulo_cu")

    # PRIORIDAD 2: datos de Ciudad3D
    if not zona:
        zona = (
            edif_raw.get("tipo_edificabilidad")
            or edif_raw.get("edificabilidad")
            or edif_raw.get("codigo_edificabilidad")
            or edif_raw.get("categoria")
        )

    edificabilidad = {
        "zona_cu_vigente": zona,
        "altura_maxima_m": round1(
            altura_max or (edif_raw.get("altura_max") or [None])[0]
        ),
        "articulo_cu": articulo_cu,
        "sup_edificable_planta_m2": round1(
            edif_raw.get("sup_edificable_planta")
        ),
        "sup_max_edificable_m2": round1(
            edif_raw.get("sup_max_edificable")
        ),
        "fot": {
            "medianera": fot_raw.get("fot_medianera"),
            "semi_libre": fot_raw.get("fot_semi_libre"),
            "perimetral": fot_raw.get("fot_perim_libre"),
        },
    }

    # -----------------------------
    # CONDICIONES URBANÍSTICAS
    # -----------------------------

    condiciones_urbanisticas = {
        "riesgo_hidrico": afect_raw.get("riesgo_hidrico"),
        "ensanche": afect_raw.get("ensanche"),
        "apertura": afect_raw.get("apertura"),
        "lep": afect_raw.get("lep"),
        "ci_digital": afect_raw.get("ci_digital"),
        "adps": edif_raw.get("adps"),
        "irregular": edif_raw.get("irregular"),
        "tipica": edif_raw.get("tipica"),
        "rivolta": edif_raw.get("rivolta"),
        "distrito_cpu_historico": (
            edif_raw.get("plusvalia") or {}
        ).get("distrito_cpu"),
    }

    # -----------------------------
    # FUENTES
    # -----------------------------

    fuentes = {
        "origen_datos": "Ciudad3D / Código Urbanístico – GCBA",
        "fecha_extraccion": date.today().strftime("%Y-%m-%d"),
    }

    # -----------------------------
    # JSON FINAL
    # -----------------------------

    resumen = {
        "identificacion": identificacion,
        "parcela": parcela,
        "edificabilidad": edificabilidad,
        "condiciones_urbanisticas": condiciones_urbanisticas,
        "fuentes": fuentes,
    }

    out = p.with_name(p.stem + "_RESUMEN.json")

    out.write_text(
        json.dumps(resumen, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print("✔ Resumen generado:", out.resolve())


# -------------------------------------------------------
# EJECUCIÓN
# -------------------------------------------------------

if __name__ == "__main__":

    carpeta = Path("salida_prefactibilidad")
    archivos = list(carpeta.glob("prefactibilidad_*.json"))

    if not archivos:
        raise FileNotFoundError(
            "No se encontró ningún prefactibilidad_*.json en salida_prefactibilidad"
        )

    resumir_prefactibilidad(str(archivos[0]))