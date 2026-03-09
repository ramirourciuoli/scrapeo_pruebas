import json
import re
from pathlib import Path
from urllib.parse import quote

import requests

# ================= CONFIG =================

OUT_DIR = Path("salida_epok_test")
OUT_DIR.mkdir(exist_ok=True)

BASE_CATASTRO = "https://epok.buenosaires.gob.ar/catastro"
BASE_CATASTROINF = "https://epok.buenosaires.gob.ar/catastroinformal"
BASE_USIG_NORM = "https://servicios.usig.buenosaires.gob.ar/normalizar/"
SRID_GEOM = 97433  # metros


# ================= HELPERS =================

def find_smp_anywhere(obj) -> str | None:
    patterns = [
        r"\b\d{2}-\d{3}-\d{3}\b",
        r"\b\d{3}-\d{3}[A-Z]-\d{3}\b",
        r"\b\d{3}-\d{3}[A-Z]-\d{3}[A-Z]\b",
        r"\b\d{2}-\d{3}[A-Z]-\d{3}[A-Z]\b",
    ]

    def scan_string(s: str):
        for p in patterns:
            m = re.search(p, s)
            if m:
                return m.group(0)
        return None

    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            for v in cur.values():
                if isinstance(v, str):
                    got = scan_string(v)
                    if got:
                        return got
                elif isinstance(v, (dict, list)):
                    stack.append(v)
        elif isinstance(cur, list):
            for it in cur:
                if isinstance(it, str):
                    got = scan_string(it)
                    if got:
                        return got
                elif isinstance(it, (dict, list)):
                    stack.append(it)
    return None


def pick_caba_direction(norm_json: dict) -> dict | None:
    dns = norm_json.get("direccionesNormalizadas", [])
    if not isinstance(dns, list) or not dns:
        return None

    for d in dns:
        if isinstance(d, dict) and str(d.get("cod_partido", "")).lower() == "caba":
            return d

    return dns[0] if isinstance(dns[0], dict) else None


def extract_lat_lng(d: dict):
    coords = d.get("coordenadas")
    if isinstance(coords, dict):
        try:
            return float(coords["y"]), float(coords["x"])
        except:
            pass
    return None, None


# ================= API CALLS =================

def usig_normalizar(address: str) -> dict:
    url = f"{BASE_USIG_NORM}?direccion={quote(address)}&geocodificar=true&srid=4326"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()


def catastro_parcela_by_codigo_calle_altura(codigo_calle: int, altura: int) -> dict:
    url = f"{BASE_CATASTRO}/parcela/"
    params = {
        "codigo_calle": codigo_calle,
        "altura": altura,
        "ib": "",
        "ft": ""
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def catastro_parcela_by_latlng_aprox(lat: float, lng: float) -> dict:
    url = f"{BASE_CATASTRO}/parcela/"
    params = {
        "lat": lat,
        "lng": lng,
        "aprox": "",
        "ib": "",
        "ft": ""
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def catastroinformal_by_calle_puerta(calle: str, puerta: str) -> dict:
    url = f"{BASE_CATASTROINF}/direccioninformal/?calle={quote(calle)}&puerta={quote(puerta)}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()


def catastro_parcela_by_smp(smp: str) -> dict:
    url = f"{BASE_CATASTRO}/parcela/"
    r = requests.get(url, params={"smp": smp}, timeout=30)
    r.raise_for_status()
    return r.json()


def catastro_geometria_by_smp(smp: str) -> dict:
    url = f"{BASE_CATASTRO}/geometria/"
    r = requests.get(url, params={"smp": smp, "srid": SRID_GEOM}, timeout=30)
    r.raise_for_status()
    return r.json()


# ================= RESOLVER SMP =================

def resolve_smp_from_address(address: str):
    dbg = {"address": address}

    norm = usig_normalizar(address)
    dbg["usig_normalizar"] = norm

    d = pick_caba_direction(norm)
    dbg["usig_direccion_elegida"] = d

    if not d:
        return None, dbg

    codigo_calle = d.get("cod_calle")
    altura = d.get("altura")

    dbg["usig_cod_calle_altura"] = {
        "cod_calle": codigo_calle,
        "altura": altura
    }

    # ================= RUTA PRINCIPAL =================
    if codigo_calle and altura:
        try:
            parc = catastro_parcela_by_codigo_calle_altura(int(codigo_calle), int(altura))
            dbg["catastro_parcela_por_codcalle_altura"] = parc

            # 🔥 USAR DIRECTAMENTE EL CAMPO SMP
            if isinstance(parc, dict) and parc.get("smp"):
                return parc["smp"], dbg

            # fallback por regex
            smp = find_smp_anywhere(parc)
            if smp:
                return smp, dbg

        except Exception as e:
            dbg["catastro_parcela_por_codcalle_altura_error"] = str(e)

    # ================= RUTA LAT/LNG =================
    lat, lng = extract_lat_lng(d)
    dbg["usig_latlng"] = {"lat": lat, "lng": lng}

    if lat is not None and lng is not None:
        try:
            parc = catastro_parcela_by_latlng_aprox(lat, lng)
            dbg["catastro_parcela_por_latlng_aprox"] = parc

            if isinstance(parc, dict) and parc.get("smp"):
                return parc["smp"], dbg

            smp = find_smp_anywhere(parc)
            if smp:
                return smp, dbg

        except Exception as e:
            dbg["catastro_parcela_por_latlng_aprox_error"] = str(e)

    # ================= FALLBACK INFORMAL =================
    calle = d.get("nombre_calle")
    puerta = d.get("altura")

    dbg["usig_calle_puerta"] = {"calle": calle, "puerta": puerta}

    if calle and puerta:
        try:
            catinf = catastroinformal_by_calle_puerta(str(calle), str(puerta))
            dbg["catastroinformal"] = catinf

            smp = find_smp_anywhere(catinf)
            if smp:
                return smp, dbg

        except Exception as e:
            dbg["catastroinformal_error"] = str(e)

    return None, dbg


# ================= GEOMETRIA =================

def polygon_area(coords):
    def ring_area(ring):
        if len(ring) < 3:
            return 0.0
        s = 0.0
        for i in range(len(ring) - 1):
            x1, y1 = ring[i]
            x2, y2 = ring[i + 1]
            s += x1 * y2 - x2 * y1
        return abs(s) / 2.0

    if not coords:
        return 0.0

    outer = ring_area(coords[0])
    holes = sum(ring_area(r) for r in coords[1:]) if len(coords) > 1 else 0.0
    return max(0.0, outer - holes)


def geojson_area_m2(geojson: dict):
    t = geojson.get("type")

    if t == "FeatureCollection":
        geom = geojson["features"][0]["geometry"]
    elif t == "Feature":
        geom = geojson["geometry"]
    else:
        geom = geojson

    if geom["type"] == "Polygon":
        return polygon_area(geom["coordinates"])

    if geom["type"] == "MultiPolygon":
        return sum(polygon_area(poly) for poly in geom["coordinates"])

    return 0.0


def polygon_centroid(ring):
    if len(ring) < 3:
        return None, None

    if ring[0] != ring[-1]:
        ring = ring + [ring[0]]

    A = 0.0
    Cx = 0.0
    Cy = 0.0

    for i in range(len(ring) - 1):
        x0, y0 = ring[i]
        x1, y1 = ring[i + 1]
        cross = x0 * y1 - x1 * y0
        A += cross
        Cx += (x0 + x1) * cross
        Cy += (y0 + y1) * cross

    A *= 0.5
    if A == 0:
        return None, None

    Cx /= (6.0 * A)
    Cy /= (6.0 * A)

    return Cx, Cy


def geojson_centroid_xy(geojson: dict):
    t = geojson.get("type")

    if t == "FeatureCollection":
        geom = geojson["features"][0]["geometry"]
    elif t == "Feature":
        geom = geojson["geometry"]
    else:
        geom = geojson

    if geom["type"] == "Polygon":
        return polygon_centroid(geom["coordinates"][0])

    if geom["type"] == "MultiPolygon":
        return polygon_centroid(geom["coordinates"][0][0])

    return None, None