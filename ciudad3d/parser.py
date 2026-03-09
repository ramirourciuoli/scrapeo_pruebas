def parsear_prefactibilidad(data: dict) -> dict:
    cur3d = data.get("cur3d", {})

    return {
        "identificacion": {
            "smp": cur3d.get("smp"),
        },
        "edificabilidad": cur3d.get("seccion_edificabilidad", {}),
        "fuentes": {
            "origen": "Ciudad3D"
        }
    }