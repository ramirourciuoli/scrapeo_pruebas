# app.py

from flask import Flask, jsonify, request, send_from_directory
import requests

# ✅ IMPORTS LOCALES (misma carpeta)
import api_datos_catastrales as adc
from api_datos_utiles import consultar_datos_utiles
import api_procesos_geograficos as pg
import api_buscador_caba as abc


app = Flask(__name__)


# =========================
# HOME
# =========================
@app.get("/")
def home():
    return send_from_directory(".", "index.html")


@app.get("/health")
def health():
    return jsonify({"ok": True})


# =========================
# AUTOCOMPLETE
# =========================
@app.get("/autocomplete/calles")
def autocomplete_calles():
    q = (request.args.get("q") or "").strip()
    limit = int(request.args.get("limit") or 12)

    try:
        data = abc.sugerir_calles_caba(q, limit=limit)
        return jsonify(data)
    except Exception as e:
        return jsonify({
            "query": q,
            "sugerencias": [],
            "error": str(e)
        }), 500


# =========================
# API CATASTRO
# =========================
@app.post("/api/catastro")
def api_catastro():

    payload = request.get_json(force=True, silent=True) or {}
    address = (payload.get("direccion") or "").strip()

    if not address:
        return jsonify({"ok": False, "error": "Falta 'direccion'"}), 400

    dbg = {"address": address}

    try:
        # 1️⃣ Resolver SMP
        smp, resolver_dbg = adc.resolve_smp_from_address(address)

        if isinstance(resolver_dbg, dict):
            dbg.update(resolver_dbg)

        if not smp:
            return jsonify({
                "ok": False,
                "error": "No se encontró parcela para esa altura (dirección sin SMP).",
                "debug": dbg
            }), 404

        # 2️⃣ Traer parcela
        parcela = adc.catastro_parcela_by_smp(smp)
        geometria = adc.catastro_geometria_by_smp(smp)

        # 3️⃣ Área
        try:
            area_m2 = adc.geojson_area_m2(geometria)
        except Exception as e:
            area_m2 = 0
            dbg["area_error"] = str(e)

        # 4️⃣ Centroide XY
        cx, cy = adc.geojson_centroid_xy(geometria)
        centroide_xy = {"x": cx, "y": cy}

        # 5️⃣ Convertir a lon/lat
        lon, lat = pg.gkba_a_lonlat(float(cx), float(cy))
        centroide_lonlat = {"lon": lon, "lat": lat}

        # 6️⃣ Datos útiles
        datos_utiles = None
        try:
            d = (dbg.get("usig_direccion_elegida") or {})
            calle = d.get("nombre_calle")
            altura = d.get("altura")
            if calle and altura:
                datos_utiles = consultar_datos_utiles(str(calle), int(altura))
        except Exception as e:
            dbg["datos_utiles_error"] = str(e)

        return jsonify({
            "ok": True,
            "input": address,
            "smp": smp,
            "parcela": parcela,
            "geometria": geometria,
            "area_m2": area_m2,
            "centroide_xy": centroide_xy,
            "centroide_lonlat": centroide_lonlat,
            "datos_utiles": datos_utiles,
            "debug": dbg
        })

    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e),
            "debug": dbg
        }), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)