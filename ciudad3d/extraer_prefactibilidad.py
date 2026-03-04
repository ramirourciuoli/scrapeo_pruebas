import json
import re
from urllib.parse import quote
from playwright.sync_api import sync_playwright

SMP_FALLBACK = "044-097A-032A"


def find_smp(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            if isinstance(v, str) and re.match(r"^\d{3}-\d{3}[A-Z]-\d{3}[A-Z]$", v):
                return v
            r = find_smp(v)
            if r:
                return r
    elif isinstance(obj, list):
        for it in obj:
            r = find_smp(it)
            if r:
                return r
    return None


def pick_caba_normalized(norm_json):
    for d in norm_json.get("direccionesNormalizadas", []):
        if (d.get("cod_partido") or "").lower() == "caba":
            return d
    return None


def extraer_prefactibilidad(address: str) -> dict:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # 1️⃣ Normalizar dirección
        norm = page.request.get(
            "https://servicios.usig.buenosaires.gob.ar/normalizar/",
            params={
                "direccion": address,
                "geocodificar": "true",
                "srid": "4326"
            }
        ).json()

        d = pick_caba_normalized(norm)
        if not d:
            browser.close()
            raise RuntimeError("No se pudo normalizar la dirección")

        calle = d.get("nombre_calle")
        puerta = d.get("altura")
        coords = d.get("coordenadas") or {}

        # 2️⃣ Catastro informal (✅ SIN quote)
        smp = None
        cat = {}
        if calle and puerta:
            cat = page.request.get(
                "https://epok.buenosaires.gob.ar/catastroinformal/direccioninformal/",
                params={
                    "calle": str(calle),
                    "puerta": str(puerta)
                }
            ).json()
            smp = find_smp(cat)

        if not smp:
            smp = SMP_FALLBACK

        # 3️⃣ CUR3D
        cur3d = {
            "smp": smp,
            "parcelas_plausibles_a_enrase": page.request.get(
                "https://epok.buenosaires.gob.ar/cur3d/parcelas_plausibles_a_enrase/",
                params={"smp": smp}
            ).json(),
            "constitucion_estado_parcelario": page.request.get(
                "https://epok.buenosaires.gob.ar/cur3d/constitucion_estado_parcelario/",
                params={"smp": smp}
            ).json(),
            "seccion_edificabilidad": page.request.get(
                "https://epok.buenosaires.gob.ar/cur3d/seccion_edificabilidad/",
                params={"smp": smp}
            ).json(),
        }

        browser.close()

    return {
        "input": {"address": address},
        "normalizada_elegida": d,
        "coords": coords,
        "cur3d": cur3d
    }