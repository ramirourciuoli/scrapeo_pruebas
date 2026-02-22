# api_procesos_geograficos.py
from __future__ import annotations
import requests

BASE_CONVERTIR = "https://ws.usig.buenosaires.gob.ar/rest/convertir_coordenadas"

class ProcesosGeograficosError(RuntimeError):
    pass

def convertir_coordenadas(x: float, y: float, output: str) -> dict:
    """
    output: "gkba" o "lonlat" (y otros formatos que soporte USIG)
    Devuelve dict con {"tipo_resultado": "...", "resultado": {"x": "...", "y": "..."}}
    """
    params = {"x": x, "y": y, "output": output}
    r = requests.get(BASE_CONVERTIR, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()

    if str(data.get("tipo_resultado", "")).lower() != "ok":
        raise ProcesosGeograficosError(str(data))

    return data

def gkba_a_lonlat(x: float, y: float) -> tuple[float, float]:
    data = convertir_coordenadas(x, y, output="lonlat")
    rx = float(data["resultado"]["x"])  # lon
    ry = float(data["resultado"]["y"])  # lat
    return rx, ry

def lonlat_a_gkba(lon: float, lat: float) -> tuple[float, float]:
    data = convertir_coordenadas(lon, lat, output="gkba")
    rx = float(data["resultado"]["x"])
    ry = float(data["resultado"]["y"])
    return rx, ry