import requests

BASE_URL = "https://servicios.usig.buenosaires.gob.ar"


def listar_partidos_amba() -> dict:
    url = f"{BASE_URL}/callejero-amba/partidos/"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()

        # Esta API suele devolver texto (no JSON), lo dejamos estable
        return {"partidos_raw": r.text}

    except requests.exceptions.RequestException as e:
        return {"error": "No pude listar partidos AMBA", "detalle": str(e), "url": url}


def obtener_callejero_partido(partido_id: str) -> dict:
    url = f"{BASE_URL}/callejero-amba/callejero/"
    params = {"partido": partido_id.strip()}
    try:
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()

        # Suele devolver texto/json según implementación; intentamos json y si no, texto
        try:
            return {"partido": partido_id, "callejero": r.json()}
        except ValueError:
            return {"partido": partido_id, "callejero_raw": r.text}

    except requests.exceptions.RequestException as e:
        return {
            "error": "No pude obtener el callejero del partido",
            "detalle": str(e),
            "url": r.url if "r" in locals() else url,
            "params": params,
        }


if __name__ == "__main__":
    print(listar_partidos_amba())
    print(obtener_callejero_partido("vicente_lopez"))