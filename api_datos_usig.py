# api_datos_usig.py
from __future__ import annotations

from urllib.parse import quote
import requests

BASE_USIG_DATOS_UTILES = "https://datosabiertos-usig-apis.buenosaires.gob.ar/datos_utiles"
BASE_USIG_GEOCODER_22 = "https://ws.usig.buenosaires.gob.ar/geocoder/2.2"
# Docs OpenAPI (por si después querés autodetectar endpoints):
#  - Datos Útiles: /swagger/spec/datos_utiles.json  (ver BA Data)  :contentReference[oaicite:5]{index=5}
#  - Búsqueda Lugares: /swagger/spec/busqueda_lugares.json         :contentReference[oaicite:6]{index=6}
#  - Procesos Geográficos: /swagger/spec/procesos_geograficos.json :contentReference[oaicite:7]{index=7}

def usig_datos_utiles_por_xy(x: float, y: float) -> dict:
    """
    Devuelve barrio, comuna, comisaría, área hospitalaria, región sanitaria,
    distrito escolar, etc. a partir de un punto (x,y).
    """
    params = {"x": x, "y": y}
    r = requests.get(BASE_USIG_DATOS_UTILES, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def usig_datos_utiles_por_direccion(calle: str, altura: int) -> dict:
    """
    Alternativa sin (x,y): datos útiles por calle/altura.
    """
    params = {"calle": calle, "altura": altura}
    r = requests.get(BASE_USIG_DATOS_UTILES, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def usig_geocoder_reverse(lat: float, lon: float) -> dict:
    """
    Si algún día lo querés: reverse geocode (depende de la API; se ajusta cuando lo uses).
    """
    # OJO: este endpoint puede variar; está en docs del geocoder.
    # Lo dejamos como placeholder realista.
    url = f"{BASE_USIG_GEOCODER_22}/reversegeocoding/"
    params = {"lat": lat, "lon": lon}
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()
