import requests


def obtener_prefactibilidad(smp: str) -> dict:
    """
    Recibe un SMP ya resuelto y consulta directamente
    los endpoints de CUR3D.
    """

    if not smp:
        return {
            "ok": False,
            "error": "SMP vacío"
        }

    try:
        parcelas_enrase = requests.get(
            "https://epok.buenosaires.gob.ar/cur3d/parcelas_plausibles_a_enrase/",
            params={"smp": smp}
        ).json()

        estado_parcelario = requests.get(
            "https://epok.buenosaires.gob.ar/cur3d/constitucion_estado_parcelario/",
            params={"smp": smp}
        ).json()

        seccion_edificabilidad = requests.get(
            "https://epok.buenosaires.gob.ar/cur3d/seccion_edificabilidad/",
            params={"smp": smp}
        ).json()

        return {
            "ok": True,
            "smp": smp,
            "cur3d": {
                "parcelas_plausibles_a_enrase": parcelas_enrase,
                "constitucion_estado_parcelario": estado_parcelario,
                "seccion_edificabilidad": seccion_edificabilidad
            }
        }

    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "smp": smp
        }