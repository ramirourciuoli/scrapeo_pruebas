from __future__ import annotations

import api_datos_catastrales as adc
from api_datos_utiles import consultar_datos_utiles
import api_procesos_geograficos as pg
from ciudad3d.servicio_ciudad3d import obtener_prefactibilidad


def consultar_lote_completo(address: str) -> dict:
    """
    Consulta un lote completo a partir de una dirección y devuelve:
    - smp
    - parcela
    - geometria
    - area_m2
    - centroide_xy
    - centroide_lonlat
    - datos_utiles
    - ciudad3d
    - debug
    """
    address = (address or "").strip()

    if not address:
        return {
            "ok": False,
            "error": "Falta 'direccion'",
            "debug": {"address": address},
        }

    dbg = {"address": address}

    try:
        # 1) Resolver SMP
        smp, resolver_dbg = adc.resolve_smp_from_address(address)

        if isinstance(resolver_dbg, dict):
            dbg.update(resolver_dbg)

        if not smp:
            return {
                "ok": False,
                "error": "No se encontró parcela para esa dirección.",
                "debug": dbg,
            }

        # 2) Datos de parcela
        parcela = adc.catastro_parcela_by_smp(smp)

        # 3) Geometría
        geometria = adc.catastro_geometria_by_smp(smp)

        # 4) Área geométrica
        try:
            area_m2 = adc.geojson_area_m2(geometria)
        except Exception as e:
            area_m2 = 0
            dbg["area_error"] = str(e)

        # 5) Centroide XY
        centroide_xy = None
        cx = cy = None
        try:
            cx, cy = adc.geojson_centroid_xy(geometria)
            centroide_xy = {"x": cx, "y": cy}
        except Exception as e:
            dbg["centroide_xy_error"] = str(e)

        # 6) Centroide lon/lat
        centroide_lonlat = None
        try:
            if cx is not None and cy is not None:
                lon, lat = pg.gkba_a_lonlat(float(cx), float(cy))
                centroide_lonlat = {"lon": lon, "lat": lat}
        except Exception as e:
            dbg["centroide_lonlat_error"] = str(e)

        # 7) Datos útiles
        datos_utiles = None
        try:
            d = dbg.get("usig_direccion_elegida", {}) or {}
            calle = d.get("nombre_calle")
            altura = d.get("altura")

            if calle and altura:
                datos_utiles = consultar_datos_utiles(str(calle), int(altura))
        except Exception as e:
            dbg["datos_utiles_error"] = str(e)

        # 8) Ciudad3D
        ciudad3d_data = None
        try:
            ciudad3d_data = obtener_prefactibilidad(smp)
        except Exception as e:
            dbg["ciudad3d_error"] = str(e)

        return {
            "ok": True,
            "input": address,
            "smp": smp,
            "parcela": parcela,
            "geometria": geometria,
            "area_m2": area_m2,
            "centroide_xy": centroide_xy,
            "centroide_lonlat": centroide_lonlat,
            "datos_utiles": datos_utiles,
            "ciudad3d": ciudad3d_data,
            "debug": dbg,
        }

    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "debug": dbg,
        }