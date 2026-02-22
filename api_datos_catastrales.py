import json
import re
from pathlib import Path
from urllib.parse import quote

import requests

# ====== CONFIG ======
OUT_DIR = Path("salida_epok_test")
OUT_DIR.mkdir(exist_ok=True)

BASE_CATASTRO = "https://epok.buenosaires.gob.ar/catastro"
BASE_CATASTROINF = "https://epok.buenosaires.gob.ar/catastroinformal"
BASE_USIG_NORM = "https://servicios.usig.buenosaires.gob.ar/normalizar/"
SRID_GEOM = 97433  # metros

# ====== HELPERS ======
def dump(path: Path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def find_smp_anywhere(obj) -> str | None:
    patterns = [
    r"\b\d{2}-\d{3}-\d{3}\b",            # 01-001-010
    r"\b\d{3}-\d{3}[A-Z]-\d{3}\b",       # 044-097A-029  ✅ (TU CASO)
    r"\b\d{3}-\d{3}[A-Z]-\d{3}[A-Z]\b",  # 056-066A-014A
    r"\b\d{2}-\d{3}[A-Z]-\d{3}[A-Z]\b",  # variantes raras
    ]

    def scan_string(s: str) -> str | None:
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

def extract_lat_lng(d: dict) -> tuple[float | None, float | None]:
    # busca coordenadas en varios formatos típicos
    for k in ["coordenadas", "ubicacion", "geo", "punto", "location", "coords"]:
        v = d.get(k)
        if isinstance(v, dict):
            lat = v.get("y") or v.get("lat") or v.get("latitude")
            lng = v.get("x") or v.get("lng") or v.get("lon") or v.get("longitude")
            if lat is not None and lng is not None:
                try:
                    return float(lat), float(lng)
                except:
                    pass

    # aplanadas
    for lat_k in ["lat", "latitude", "y"]:
        for lng_k in ["lng", "lon", "longitude", "x"]:
            if lat_k in d and lng_k in d:
                try:
                    return float(d[lat_k]), float(d[lng_k])
                except:
                    pass

    # x/y sueltas
    if "x" in d and "y" in d:
        try:
            return float(d["y"]), float(d["x"])
        except:
            pass

    return None, None

# ====== API CALLS ======
def usig_normalizar(address: str) -> dict:
    url = f"{BASE_USIG_NORM}?direccion={quote(address)}&geocodificar=true&srid=4326"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()

def catastro_parcela_by_latlng(lat: float, lng: float) -> dict:
    url = f"{BASE_CATASTRO}/parcela/"
    params = {"lat": lat, "lng": lng, "ib": "", "ft": ""}
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
    params = {"smp": smp, "ib": "", "ft": ""}
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def catastro_geometria_by_smp(smp: str) -> dict:
    url = f"{BASE_CATASTRO}/geometria/"
    params = {"smp": smp, "srid": SRID_GEOM}
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

# ====== GEOM (sin shapely) ======
def polygon_area(coords):
    """
    coords: lista de anillos. Cada anillo es lista [ [x,y], [x,y], ... ]
    Calcula area usando shoelace para el anillo exterior - interiores.
    """
    def ring_area(ring):
        if len(ring) < 3:
            return 0.0
        s = 0.0
        for i in range(len(ring)-1):
            x1, y1 = ring[i]
            x2, y2 = ring[i+1]
            s += x1*y2 - x2*y1
        return abs(s) / 2.0

    if not coords:
        return 0.0

    outer = ring_area(coords[0])
    holes = sum(ring_area(r) for r in coords[1:]) if len(coords) > 1 else 0.0
    return max(0.0, outer - holes)

def geojson_area_m2(geojson: dict) -> float:
    t = geojson.get("type")

    if t == "FeatureCollection":
        geom = geojson["features"][0]["geometry"]
    elif t == "Feature":
        geom = geojson["geometry"]
    else:
        geom = geojson

    gt = geom.get("type")

    if gt == "Polygon":
        return polygon_area(geom["coordinates"])

    if gt == "MultiPolygon":
        total = 0.0
        for poly in geom["coordinates"]:
            total += polygon_area(poly)
        return total
    
    raise ValueError(f"Geometría no soportada: {gt}")

# ====== MAIN ======
def resolve_smp_from_address(address: str) -> tuple[str | None, dict]:
    dbg = {"address": address}

    norm = usig_normalizar(address)
    dbg["usig_normalizar"] = norm

    d = pick_caba_direction(norm)
    dbg["usig_direccion_elegida"] = d
    if not d:
        return None, dbg

    # Datos fuertes desde USIG
    codigo_calle = d.get("cod_calle")
    altura = d.get("altura")
    dbg["usig_cod_calle_altura"] = {"cod_calle": codigo_calle, "altura": altura}

    # 1) MEJOR RUTA: Catastro por codigo_calle + altura
    if codigo_calle and altura:
        try:
            parc = catastro_parcela_by_codigo_calle_altura(int(codigo_calle), int(altura))
            dbg["catastro_parcela_por_codcalle_altura"] = parc
            smp = find_smp_anywhere(parc)
            if smp:
                return smp, dbg
        except Exception as e:
            dbg["catastro_parcela_por_codcalle_altura_error"] = str(e)

    # 2) RUTA 2: Catastro por lat/lng con aprox
    lat, lng = extract_lat_lng(d)
    dbg["usig_latlng"] = {"lat": lat, "lng": lng}

    if lat is not None and lng is not None:
        try:
            parc = catastro_parcela_by_latlng_aprox(lat, lng)
            dbg["catastro_parcela_por_latlng_aprox"] = parc
            smp = find_smp_anywhere(parc)
            if smp:
                return smp, dbg
        except Exception as e:
            dbg["catastro_parcela_por_latlng_aprox_error"] = str(e)

    # 3) Fallback: catastroinformal (puede devolver {})
    calle = d.get("nombre_calle") or d.get("calle")
    puerta = d.get("altura") or d.get("puerta")
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

def catastro_parcela_by_codigo_calle_altura(codigo_calle: int, altura: int) -> dict:
    url = f"{BASE_CATASTRO}/parcela/"
    params = {"codigo_calle": codigo_calle, "altura": altura, "ib": "", "ft": ""}
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def catastro_parcela_by_latlng_aprox(lat: float, lng: float) -> dict:
    url = f"{BASE_CATASTRO}/parcela/"
    params = {"lat": lat, "lng": lng, "aprox": "", "ib": "", "ft": ""}  # 👈 aprox
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def test_by_address(address: str):
    smp, dbg = resolve_smp_from_address(address)
    dump(OUT_DIR / "debug_resolver_smp.json", dbg)

    if not smp:
        print("❌ No pude resolver SMP desde la dirección.")
        print(f"📄 Debug guardado en: {OUT_DIR / 'debug_resolver_smp.json'}")
    return
def resolver_paquete_catastro(address: str) -> dict:
    smp, dbg = resolve_smp_from_address(address)
    if not smp:
        return {"ok": False, "error": "No pude resolver SMP", "debug": dbg}

    parcela = catastro_parcela_by_smp(smp)
    geometria = catastro_geometria_by_smp(smp)

    area_m2 = None
    try:
        area_m2 = geojson_area_m2(geometria)
    except Exception as e:
        dbg["area_error"] = str(e)

    return {
        "ok": True,
        "input": address,
        "smp": smp,
        "parcela": parcela,
        "geometria": geometria,
        "area_m2": area_m2,
        "debug": dbg
    }
def polygon_centroid(ring):
    """
    ring: lista de puntos [[x,y], [x,y], ...] (idealmente cerrado)
    Retorna (cx, cy) usando fórmula de centroide de polígono.
    """
    if len(ring) < 3:
        return None, None

    # Asegurar cierre
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

def geojson_centroid_xy(geojson: dict) -> tuple[float | None, float | None]:
    """
    Toma la geometría de catastro/geometria (GeoJSON en SRID 97433 en tu caso)
    y retorna un centroide (x,y) aproximado del polígono exterior.
    """
    t = geojson.get("type")
    if t == "FeatureCollection":
        geom = geojson["features"][0]["geometry"]
    elif t == "Feature":
        geom = geojson["geometry"]
    else:
        geom = geojson

    gt = geom.get("type")
    coords = geom.get("coordinates")

    if gt == "Polygon":
        outer_ring = coords[0]
        return polygon_centroid(outer_ring)

    if gt == "MultiPolygon":
        # Tomamos el primer polígono como aproximación
        outer_ring = coords[0][0]
        return polygon_centroid(outer_ring)

    return None, None


if __name__ == "__main__":
    test_by_address("Davila 1130, CABA")