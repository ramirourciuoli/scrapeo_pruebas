import requests
import json

def consultar_datos_utiles(calle: str, altura: int) -> dict:

    url = "https://datosabiertos-usig-apis.buenosaires.gob.ar/datos_utiles"

    params = {
        "calle": calle.strip(),
        "altura": int(altura)
    }

    headers = {
        "Accept": "application/json"
    }

    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)

        try:
            return r.json()
        except Exception:
            return json.loads(r.text)

    except requests.exceptions.RequestException as e:
        return {
            "error": "Error de conexión con la API",
            "detalle": str(e)
        }