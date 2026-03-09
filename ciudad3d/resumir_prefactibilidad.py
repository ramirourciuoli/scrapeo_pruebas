from datetime import date

def resumir_prefactibilidad(data: dict) -> dict:

    cur3d = data.get("cur3d", {}) or {}
    edif_raw = cur3d.get("seccion_edificabilidad", {}) or {}

    afect_raw = edif_raw.get("afectaciones", {}) or {}
    fot_raw = edif_raw.get("fot", {}) or {}

    normalizada = data.get("normalizada_elegida", {}) or {}
    datos_utiles = data.get("datos_utiles", {}) or {}

    identificacion = {
        "direccion": normalizada.get("direccion"),
        "smp": cur3d.get("smp"),
        "comuna": datos_utiles.get("comuna"),
        "barrio": datos_utiles.get("barrio"),
    }

    parcela = {
        "superficie_lote_m2": edif_raw.get("superficie_parcela"),
    }

    edificabilidad = {
        "zona_cu_vigente": (
            edif_raw.get("tipo_edificabilidad")
            or edif_raw.get("edificabilidad")
        ),
        "altura_maxima_m": (edif_raw.get("altura_max") or [None])[0],
        "sup_max_edificable_m2": edif_raw.get("sup_max_edificable"),
        "fot": {
            "medianera": fot_raw.get("fot_medianera"),
            "semi_libre": fot_raw.get("fot_semi_libre"),
            "perimetral": fot_raw.get("fot_perim_libre"),
        },
    }

    condiciones_urbanisticas = {
        "riesgo_hidrico": afect_raw.get("riesgo_hidrico"),
        "ensanche": afect_raw.get("ensanche"),
    }

    fuentes = {
        "origen_datos": "Ciudad3D – GCBA",
        "fecha_extraccion": date.today().strftime("%Y-%m-%d"),
    }

    return {
        "identificacion": identificacion,
        "parcela": parcela,
        "edificabilidad": edificabilidad,
        "condiciones_urbanisticas": condiciones_urbanisticas,
        "fuentes": fuentes,
    }