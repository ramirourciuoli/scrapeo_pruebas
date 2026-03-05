from __future__ import annotations

from pathlib import Path
import re

import ezdxf
import geopandas as gpd
from shapely.geometry import Polygon


# ✅ Cambiá ESTA RUTA por la tuya real
BASE_MZ = Path(r"C:\TRABAJOS\Capas QGIS\MZ_CABA2019_202205")


def parse_smp(smp: str) -> tuple[str, str, str]:
    """
    "044-097A-029" -> ("044", "097A", "029")
    """
    m = re.match(r"^(\d{3})-([0-9A-Z]{3,4})-(\d{3})$", smp.strip().upper())
    if not m:
        raise ValueError(f"SMP inválido: {smp!r}")
    return m.group(1), m.group(2), m.group(3)


def get_manzana_path_from_smp(smp: str) -> Path:
    """
    Arma el path al DXF de la manzana:
    BASE/044_MZ_CABA2019/044-097A.dxf
    """
    seccion, manzana, _ = parse_smp(smp)
    carpeta = f"{seccion}_MZ_CABA2019"
    archivo = f"{seccion}-{manzana}.dxf"
    path = BASE_MZ / carpeta / archivo
    if not path.exists():
        raise FileNotFoundError(f"No existe el DXF esperado: {path}")
    return path


def _lwpolyline_to_polygon(e) -> Polygon | None:
    # pts: lista de (x,y)
    pts = [(p[0], p[1]) for p in e.get_points()]  # LWPOLYLINE
    if len(pts) < 3:
        return None
    # asegurar cierre
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    try:
        poly = Polygon(pts)
        if not poly.is_valid or poly.area == 0:
            return None
        return poly
    except Exception:
        return None


def leer_manzana_dxf(path: Path, crs_epsg: int = 22185) -> gpd.GeoDataFrame:
    """
    Lee un DXF de manzana y devuelve GeoDataFrame con polígonos.
    CRS default: EPSG:5347 (Gauss-Krüger BA, común en datasets CABA).
    Si tu DXF estuviera en otro CRS, lo ajustamos luego.
    """
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()

    polys = []
    for e in msp:
        if e.dxftype() == "LWPOLYLINE" and e.closed:
            poly = _lwpolyline_to_polygon(e)
            if poly is not None:
                polys.append(poly)

    if not polys:
        # algunos DXF vienen como POLYLINE (no LWPOLYLINE)
        for e in msp:
            if e.dxftype() == "POLYLINE" and e.is_closed:
                pts = [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices()]
                if len(pts) >= 3:
                    if pts[0] != pts[-1]:
                        pts.append(pts[0])
                    poly = Polygon(pts)
                    if poly.is_valid and poly.area > 0:
                        polys.append(poly)

    if not polys:
        raise ValueError("No encontré polígonos cerrados en el DXF (LWPOLYLINE/POLYLINE).")

    gdf = gpd.GeoDataFrame({"geometry": polys}, crs=f"EPSG:{crs_epsg}")
    return gdf


def cargar_manzana_por_smp(smp: str, crs_epsg: int = 5347) -> dict:
    """
    Devuelve resumen listo para inspección (sin app.py).
    """
    path = get_manzana_path_from_smp(smp)
    gdf = leer_manzana_dxf(path, crs_epsg=crs_epsg)

    geom_union = gdf.unary_union
    area_m2 = float(geom_union.area)
    cx, cy = geom_union.centroid.x, geom_union.centroid.y

    return {
        "smp": smp,
        "path": str(path),
        "crs": str(gdf.crs),
        "poligonos": int(len(gdf)),
        "area_m2": area_m2,
        "centroide_xy": {"x": float(cx), "y": float(cy)},
    }