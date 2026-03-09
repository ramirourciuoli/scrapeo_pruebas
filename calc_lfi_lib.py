"""
calc_lfi_lib.py
================
Calcula LFI y LIB para una carpeta de respuestas JSON (muestras), usando:
- Reglas base del Código Urbanístico (tabla)
- Excepciones normativas (manzanas atípicas / banda mínima, si están disponibles)
- Geometría (si se provee) para detectar tipo de lote y/o ajustar por banda mínima.

Salida:
- out_lfi_lib.csv

USO:
  python calc_lfi_lib.py --responses ./salida_muestras_100 --out out_lfi_lib.csv

OPCIONAL (si tenés capas):
  --parcelas ./data/capas/parcelas.(shp|gpkg|geojson|csv)
  --linea_oficial ./data/capas/linea_oficial.(shp|gpkg|geojson|csv)
  --banda_minima ./data/capas/banda_minima.(shp|gpkg|geojson|csv)
  --manzanas_dxf ./data/capas/manzanas_dxf
  --cu ./data/tablas/codigo-urbanistico.xlsx
  --atipicas ./data/tablas/Manzanas_Atipicas_Listado Editable.xlsx
"""

from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import pandas as pd

# Si tenés geopandas instalado, habilitamos cálculo geométrico.
# Si no, el script igual corre (pero con menos precisión).
try:
    import geopandas as gpd
    from shapely.geometry import shape
    from shapely import wkt
    HAS_GEO = True
except Exception:
    HAS_GEO = False


# -----------------------------
# Utilidades
# -----------------------------
SMP_RE = re.compile(r"\b(\d{3}-\d{3}[A-Z]?-?\d{3}[A-Z]?)\b")

def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))

def safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).strip().replace(",", ".")
        if s == "":
            return None
        return float(s)
    except Exception:
        return None

def pick_smp(obj: Any) -> Optional[str]:
    # Busca SMP en cualquier string dentro del JSON
    s = json.dumps(obj, ensure_ascii=False)
    m = SMP_RE.search(s)
    return m.group(1) if m else None


# -----------------------------
# Modelo de salida
# -----------------------------
@dataclass
class Result:
    archivo: str
    smp: str | None
    unidad: str | None
    frente_m: float | None
    fondo_m: float | None
    lfi_m: float | None
    lib_m: float | None
    origen: str
    warnings: str


# -----------------------------
# Carga de tablas (CU / excepciones)
# -----------------------------
def load_cu_table(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path)
    # Normalizamos columnas esperadas
    # (si tus nombres cambian, ajustamos acá)
    df.columns = [str(c).strip().lower() for c in df.columns]
    # esperadas: unidad, altura_max, altura_basamento, retiro_frente, retiro_lateral, retiro_fondo, lib, lfi
    return df

def load_atipicas(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path)
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df


# -----------------------------
# Geometría (opcional)
# -----------------------------
def load_layer_any(path: Path):
    """
    Carga SHP/GPKG/GEOJSON/CSV con WKT.
    Requiere geopandas.
    """
    if not HAS_GEO:
        return None

    suffix = path.suffix.lower()
    if suffix in [".shp", ".gpkg", ".geojson", ".json"]:
        gdf = gpd.read_file(path)
        return gdf
    if suffix == ".csv":
        df = pd.read_csv(path)
        cols = [c.lower() for c in df.columns]
        # Buscamos WKT
        wkt_col = None
        for c in df.columns:
            if c.lower() in ("wkt", "geom", "geometry", "the_geom"):
                wkt_col = c
                break
        if wkt_col is None:
            raise RuntimeError(f"CSV sin WKT reconocible: {path.name}")
        gdf = gpd.GeoDataFrame(df, geometry=df[wkt_col].apply(wkt.loads), crs="EPSG:4326")
        return gdf

    raise RuntimeError(f"Formato no soportado: {path.name}")


# -----------------------------
# Reglas base (ajustables)
# -----------------------------
def regla_base_lfi_lib(frente_m: float | None, fondo_m: float | None) -> tuple[float | None, float | None]:
    """
    Regla “clásica” tipo corredor:
    - LFI: 26m (si el fondo lo permite)
    - LIB: 16m (si el fondo lo permite)
    Si el lote es corto: se recorta al fondo real.
    """
    if fondo_m is None:
        return (26.0, 16.0)
    lfi = min(26.0, fondo_m)
    lib = min(16.0, fondo_m)
    return (lfi, lib)


def aplicar_excepciones(
    smp: str | None,
    unidad: str | None,
    frente_m: float | None,
    fondo_m: float | None,
    cu_df: pd.DataFrame | None,
    atip_df: pd.DataFrame | None,
    g_parcela=None,
    g_banda=None,
) -> tuple[float | None, float | None, str, str]:
    """
    Devuelve (lfi, lib, origen, warnings)
    """
    warnings = []

    # 1) Base
    lfi, lib = regla_base_lfi_lib(frente_m, fondo_m)
    origen = "regla_base"

    # 2) Tabla CU: si tu CU trae lfi/lib explícitos (como metros), lo usamos.
    #    (Esto puede cambiar: si en tu tabla no son metros, desactivar esta parte.)
    if cu_df is not None and unidad:
        # intentamos match por unidad
        # normalizamos unidad al estilo del df
        u = str(unidad).strip().lower()
        if "unidad" in cu_df.columns:
            row = cu_df[cu_df["unidad"].astype(str).str.strip().str.lower() == u]
            if len(row) > 0:
                r = row.iloc[0]
                lfi_cu = safe_float(r.get("lfi"))
                lib_cu = safe_float(r.get("lib"))
                # si aparecen como números razonables, pisan regla base
                if lfi_cu and lfi_cu > 0:
                    lfi = min(lfi_cu, fondo_m) if fondo_m else lfi_cu
                    origen = "tabla_cu"
                if lib_cu and lib_cu > 0:
                    lib = min(lib_cu, fondo_m) if fondo_m else lib_cu
                    origen = "tabla_cu"
            else:
                warnings.append("No match unidad en tabla CU")

    # 3) Manzana atípica: si el SMP cae en una lista de excepciones,
    #    acá se deberían aplicar overrides.
    #    (Depende de cómo venga tu archivo; dejamos estructura lista.)
    if atip_df is not None and smp:
        # ejemplo: si tu tabla tiene una columna 'smp' o similar
        cols = set(atip_df.columns)
        if "smp" in cols:
            hit = atip_df[atip_df["smp"].astype(str).str.contains(smp, na=False)]
            if len(hit) > 0:
                # Si hubiera columnas específicas de lfi/lib excepcionales, se aplican acá:
                # lfi_exc = safe_float(hit.iloc[0].get("lfi"))
                # lib_exc = safe_float(hit.iloc[0].get("lib"))
                # ...
                origen = "excepcion_manzana_atipica"
                warnings.append("Hit en manzana atípica (revisar reglas específicas)")

    # 4) Banda mínima edificable (si hay geometría):
    #    Si la parcela intersecta la banda mínima, podrías restringir lfi/lib
    #    según el espesor/corredor edificable real.
    if HAS_GEO and g_parcela is not None and g_banda is not None:
        try:
            if g_parcela.intersects(g_banda):
                # esto es un placeholder: el cálculo real depende de cómo representes la banda mínima.
                # Podés, por ejemplo, medir “profundidad edificable” como distancia desde línea oficial hasta el borde interno de banda.
                origen = "banda_minima"
                warnings.append("Intersecta banda mínima: falta cálculo específico (placeholder)")
        except Exception:
            warnings.append("Error aplicando banda mínima")

    return lfi, lib, origen, " | ".join(warnings)


# -----------------------------
# Parse de tus JSON de muestras
# -----------------------------
def extract_frente_fondo_unidad(resp: dict) -> tuple[str | None, float | None, float | None, str | None]:
    smp = pick_smp(resp)

    # Estos paths varían según tu API.
    # Intento flexible: busca llaves típicas.
    frente = None
    fondo = None
    unidad = None

    # 1) Frente/fondo: si vienen “ya calculados” en el JSON
    #    (por ejemplo: resp["parcela"]["frente_m"])
    s = json.dumps(resp, ensure_ascii=False).lower()

    # patrones típicos (ajustá a tu JSON real si hace falta)
    for key in ["frente_m", "frente", "ancho_frente"]:
        if key in resp:
            frente = safe_float(resp.get(key))
    for key in ["fondo_m", "fondo", "profundidad"]:
        if key in resp:
            fondo = safe_float(resp.get(key))

    # Búsqueda más profunda si viene anidado
    def deep_find(obj, target_keys):
        if isinstance(obj, dict):
            for k, v in obj.items():
                kl = str(k).lower()
                if kl in target_keys:
                    return v
                got = deep_find(v, target_keys)
                if got is not None:
                    return got
        elif isinstance(obj, list):
            for it in obj:
                got = deep_find(it, target_keys)
                if got is not None:
                    return got
        return None

    if frente is None:
        frente = safe_float(deep_find(resp, {"frente_m","frente","ancho_frente"}))
    if fondo is None:
        fondo = safe_float(deep_find(resp, {"fondo_m","fondo","profundidad"}))

    # Unidad edificabilidad
    unidad = deep_find(resp, {"unidad","unidad_edificabilidad","edificabilidad","zonificacion"})
    if unidad is not None:
        unidad = str(unidad)

    return smp, frente, fondo, unidad


# -----------------------------
# Main
# -----------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--responses", required=True, help="Carpeta con *_response.json")
    ap.add_argument("--out", default="out_lfi_lib.csv")

    ap.add_argument("--cu", default="./data/tablas/codigo-urbanistico.xlsx")
    ap.add_argument("--atipicas", default="./data/tablas/Manzanas_Atipicas_Listado Editable.xlsx")

    # capas opcionales
    ap.add_argument("--parcelas", default="")
    ap.add_argument("--linea_oficial", default="")
    ap.add_argument("--banda_minima", default="")

    args = ap.parse_args()

    resp_dir = Path(args.responses)
    out_path = Path(args.out)

    cu_path = Path(args.cu)
    atip_path = Path(args.atipicas)

    cu_df = load_cu_table(cu_path) if cu_path.exists() else None
    atip_df = load_atipicas(atip_path) if atip_path.exists() else None

    # capas (opcionales)
    gdf_parcelas = load_layer_any(Path(args.parcelas)) if args.parcelas else None
    gdf_banda = load_layer_any(Path(args.banda_minima)) if args.banda_minima else None

    results: list[Result] = []
    for p in sorted(resp_dir.glob("*_response.json")):
        try:
            resp = read_json(p)
        except Exception as e:
            results.append(Result(p.name, None, None, None, None, None, None, "error_json", f"JSON inválido: {e}"))
            continue

        smp, frente, fondo, unidad = extract_frente_fondo_unidad(resp)

        # Si tu unidad viene como lista (como mostraste: "[22.8,0,0,0]"), la dejamos como string.
        # (Idealmente después la convertimos a "USAA/USAM/etc" desde tu pipeline real)
        warnings = []
        if unidad and unidad.strip().startswith("["):
            warnings.append("Unidad viene como lista numérica; falta mapear a etiqueta (USAA/...)")

        # geometría específica de parcela (si tu capa trae smp para join)
        g_parcela = None
        g_banda = None
        if HAS_GEO and gdf_parcelas is not None and smp:
            # intentamos localizar por columna SMP
            cols = [c.lower() for c in gdf_parcelas.columns]
            smp_col = None
            for c in gdf_parcelas.columns:
                if str(c).lower() in ("smp","smp_parcela","smp_2020","smp_caba"):
                    smp_col = c
                    break
            if smp_col:
                hit = gdf_parcelas[gdf_parcelas[smp_col].astype(str) == smp]
                if len(hit) > 0:
                    g_parcela = hit.iloc[0].geometry
                else:
                    warnings.append("No encontré geometría de parcela por SMP en capa parcelas")
            else:
                warnings.append("Capa parcelas no tiene columna SMP reconocible")

        if HAS_GEO and gdf_banda is not None:
            # banda mínima como unión (si es una capa por áreas)
            try:
                g_banda = gdf_banda.unary_union
            except Exception:
                g_banda = None

        lfi, lib, origen, warn2 = aplicar_excepciones(
            smp=smp,
            unidad=unidad,
            frente_m=frente,
            fondo_m=fondo,
            cu_df=cu_df,
            atip_df=atip_df,
            g_parcela=g_parcela,
            g_banda=g_banda,
        )

        all_warn = " | ".join([w for w in (warnings + ([warn2] if warn2 else [])) if w])
        results.append(Result(
            archivo=p.name,
            smp=smp,
            unidad=unidad,
            frente_m=frente,
            fondo_m=fondo,
            lfi_m=lfi,
            lib_m=lib,
            origen=origen,
            warnings=all_warn
        ))

    df_out = pd.DataFrame([r.__dict__ for r in results])
    df_out.to_csv(out_path, index=False, encoding="utf-8")
    print(f"OK -> {out_path.resolve()} ({len(df_out)} filas)")

if __name__ == "__main__":
    main()