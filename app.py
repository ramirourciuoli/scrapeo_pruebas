# app.py
from __future__ import annotations

from flask import Flask, jsonify, request, send_from_directory
import requests

import api_datos_catastrales as adc
from api_datos_catastrales.Scrapeo_Pruebas.api_datos_utiles import consultar_datos_utiles

# Módulo nuevo (Procesos Geográficos USIG)
import api_datos_catastrales.Scrapeo_Pruebas.api_procesos_geograficos as pg

# ✅ Autocomplete calles CABA
import api_datos_catastrales.Scrapeo_Pruebas.api_buscador_caba as abc


app = Flask(__name__)


# =========================
# Helpers (altura cercana)
# =========================
EPOK_BASE = "https://epok.buenosaires.gob.ar/catastro"


def _is_parcela_valida(obj: dict) -> bool:
    if not isinstance(obj, dict) or not obj:
        return False
    # señales típicas de parcela válida
    return bool(obj.get("smp") or obj.get("codigo") or obj.get("direccion") or obj.get("manzana"))


def _catastro_parcela_por_codcalle_altura(cod_calle: int, altura: int) -> dict:
    """
    Intenta obtener parcela de Catastro por cod_calle + altura.
    Primero intenta usando funciones del módulo adc si existieran,
    y si no, cae a requests directo a EPOK.
    """
    # 1) Si tu api_datos_catastrales.py ya tiene una función, úsala.
    for fname in ("catastro_parcela_by_codcalle_altura", "catastro_parcela_por_codcalle_altura"):
        fn = getattr(adc, fname, None)
        if callable(fn):
            try:
                return fn(int(cod_calle), int(altura)) or {}
            except Exception:
                pass

    # 2) Fallback HTTP directo (robusto a variantes de endpoint)
    params = {"cod_calle": int(cod_calle), "altura": int(altura)}

    # Probamos 2 variantes comunes: /parcela y /parcela/
    for url in (f"{EPOK_BASE}/parcela", f"{EPOK_BASE}/parcela/"):
        try:
            r = requests.get(url, params=params, timeout=10)
            if r.status_code == 200:
                data = r.json()
                return data if isinstance(data, dict) else {}
        except Exception:
            continue

    return {}


def sugerir_alturas_validas_cercanas(
    cod_calle: int,
    nombre_calle: str,
    altura_ingresada: int,
    limit: int = 6,
    max_delta: int = 120,
) -> list[dict]:
    """
    Busca alturas "válidas" cercanas probando hacia arriba/abajo
    hasta encontrar 'limit' parcelas reales en Catastro.
    Estrategia MVP: probing radial (±1, ±2, ±3...) para evitar scans grandes.
    """
    cod_calle = int(cod_calle)
    altura_ingresada = int(altura_ingresada)

    encontrados: list[dict] = []
    vistos = set()

    # probamos primero la misma altura (por si justo)
    for delta in range(0, max_delta + 1):
        # orden: 0, -1, +1, -2, +2, ...
        candidatos = []
        if delta == 0:
            candidatos = [altura_ingresada]
        else:
            candidatos = [altura_ingresada - delta, altura_ingresada + delta]

        for alt in candidatos:
            if alt <= 0:
                continue
            if alt in vistos:
                continue
            vistos.add(alt)

            parcela = _catastro_parcela_por_codcalle_altura(cod_calle, alt)
            if _is_parcela_valida(parcela):
                # armamos una sugerencia clara para UI
                direccion = (parcela.get("direccion") or f"{nombre_calle} {alt}").strip()
                smp = parcela.get("smp") or parcela.get("codigo") or None
                encontrados.append(
                    {
                        "altura": alt,
                        "direccion": f"{direccion}, CABA",
                        "smp": smp,
                        "parcela": parcela,
                    }
                )

                if len(encontrados) >= limit:
                    return encontrados

    return encontrados


# =========================
# Routes
# =========================
@app.get("/")
def home():
    """
    Sirve el HTML desde la carpeta actual.
    Acepta 'index.html' o 'Index.html' para evitar problemas de mayúsculas.
    """
    try:
        return send_from_directory(".", "index.html")
    except Exception:
        return send_from_directory(".", "Index.html")


@app.get("/health")
def health():
    return jsonify({"ok": True})


@app.get("/autocomplete/calles")
def autocomplete_calles():
    """
    Autocomplete de calles (CABA) y también calle+altura cuando el normalizador lo resuelve.
    Query params:
      - q: texto
      - limit: int
    """
    q = (request.args.get("q") or "").strip()
    limit = int(request.args.get("limit") or 12)
    try:
        data = abc.sugerir_calles_caba(q, limit=limit)
        return jsonify(data)
    except Exception as e:
        return jsonify({"query": q, "sugerencias": [], "error": str(e)}), 500


@app.post("/api/catastro")
def api_catastro():
    """
    Body JSON esperado:
      { "direccion": "Davila 1130, CABA" }

    ✅ MVP extra:
      - si la dirección está bien normalizada pero NO existe parcela (sin SMP),
        devuelve alternativas de alturas válidas cercanas para la misma calle.
    """
    payload = request.get_json(force=True, silent=True) or {}
    address = (payload.get("direccion") or payload.get("address") or "").strip()

    if not address:
        return jsonify({"ok": False, "error": "Falta 'direccion'"}), 400

    dbg: dict = {"address": address}

    try:
        # 1) Resolver SMP (y traer debug con dirección elegida USIG)
        smp, resolver_dbg = adc.resolve_smp_from_address(address)
        if isinstance(resolver_dbg, dict):
            dbg.update(resolver_dbg)

        # --- Si no hay SMP: ofrecer alturas válidas cercanas (MVP)
        if not smp:
            # Tomamos info USIG (si existe) para entender calle/cod_calle/altura
            d = (dbg.get("usig_direccion_elegida") or {})
            cod = (dbg.get("usig_cod_calle_altura") or {}).get("cod_calle") or d.get("cod_calle")
            altura = (dbg.get("usig_cod_calle_altura") or {}).get("altura") or d.get("altura")
            calle = d.get("nombre_calle") or d.get("calle") or (dbg.get("usig_calle_puerta") or {}).get("calle")

            alternativas = []
            try:
                if cod and altura and calle:
                    alternativas = sugerir_alturas_validas_cercanas(
                        cod_calle=int(cod),
                        nombre_calle=str(calle),
                        altura_ingresada=int(altura),
                        limit=6,
                        max_delta=140,
                    )
            except Exception as e:
                dbg["alturas_cercanas_error"] = str(e)

            return jsonify(
                {
                    "ok": False,
                    "error": "No se encontró parcela para esa altura (dirección sin SMP).",
                    "alternativas_altura": alternativas,  # ✅ lo usa el front para sugerir
                    "debug": dbg,
                }
            ), 404

        # 2) Traer parcela + geometría por SMP (Catastro)
        parcela = adc.catastro_parcela_by_smp(smp)
        geometria = adc.catastro_geometria_by_smp(smp)

        # 3) Área m²
        try:
            area_m2 = adc.geojson_area_m2(geometria)
        except Exception as e:
            area_m2 = 0
            dbg["area_error"] = str(e)

        # 4) Centroide XY (SRID interno 97433)
        cx = cy = None
        try:
            cx, cy = adc.geojson_centroid_xy(geometria)
        except Exception as e:
            dbg["centroide_xy_error"] = str(e)

        centroide_xy = {"x": cx, "y": cy} if (cx is not None and cy is not None) else None

        # 5) Centroide lon/lat (WGS84) usando Procesos Geográficos (USIG)
        centroide_lonlat = None
        try:
            if cx is not None and cy is not None:
                lon, lat = pg.gkba_a_lonlat(float(cx), float(cy))
                centroide_lonlat = {"lon": lon, "lat": lat}
        except Exception as e:
            dbg["procesos_geograficos_error"] = str(e)

        # 6) Datos Útiles (por calle/altura)
        datos_utiles = None
        try:
            d = (dbg.get("usig_direccion_elegida") or {})
            calle = d.get("nombre_calle") or d.get("calle")
            altura = d.get("altura") or d.get("puerta")
            if calle and altura:
                datos_utiles = consultar_datos_utiles(str(calle), int(altura))
        except Exception as e:
            dbg["datos_utiles_error"] = str(e)

        return jsonify(
            {
                "ok": True,
                "input": address,
                "smp": smp,
                "parcela": parcela,
                "geometria": geometria,
                "area_m2": area_m2,
                "centroide_xy": centroide_xy,
                "centroide_lonlat": centroide_lonlat,
                "datos_utiles": datos_utiles,
                "debug": dbg,
            }
        )

    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "debug": dbg}), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)