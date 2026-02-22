import re
import requests

USIG_NORMALIZAR_URL = "https://servicios.usig.buenosaires.gob.ar/normalizar/"


def _solo_caba(item: dict) -> bool:
    return (item.get("cod_partido") or "").strip().lower() == "caba"


def _tipo_permitido(item: dict) -> bool:
    tipo = (item.get("tipo") or "").strip().lower()
    # Tipos útiles para tu caso (solo calles y direcciones)
    tipos_permitidos = {"calle", "calle_altura", "calle_y_calle"}
    return (not tipo) or (tipo in tipos_permitidos)


def _tiene_texto_de_calle(item: dict) -> bool:
    """
    Asegura que la sugerencia sea de calle/dirección.
    """
    nombre_calle = (item.get("nombre_calle") or "").strip()
    direccion = (item.get("direccion") or "").strip()

    if nombre_calle:
        return True
    if direccion and re.search(r"[a-záéíóúüñ]", direccion, re.IGNORECASE):
        return True
    return False


def _armar_label(item: dict) -> str:
    """
    - Si es calle_altura: preferimos 'direccion' (ej: 'DAVILA 1130')
    - Si es calle: preferimos 'nombre_calle'
    - Fallback: 'direccion'
    """
    tipo = (item.get("tipo") or "").strip().lower()
    direccion = (item.get("direccion") or "").strip()
    nombre_calle = (item.get("nombre_calle") or "").strip()

    if tipo == "calle_altura" and direccion:
        return direccion

    return nombre_calle or direccion


def sugerir_calles_caba(query: str, limit: int = 10) -> dict:
    """
    Autocomplete de calles/direcciones (CABA) usando USIG normalizar.
    Acepta:
      - 'mitre' -> calles
      - 'davila 1130' -> direcciones con altura
      - 'davila 113' -> sugiere varias alturas cercanas (según lo que devuelva USIG)
    Devuelve:
      {"query": "...", "sugerencias": [ {label, nombre_calle, cod_calle, altura, tipo}, ... ]}
    """
    q = (query or "").strip()
    if len(q) < 3:
        return {"query": q, "sugerencias": []}

    params = {"direccion": q}

    try:
        r = requests.get(USIG_NORMALIZAR_URL, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
    except requests.exceptions.JSONDecodeError:
        return {"error": "La respuesta no es JSON válido", "query": q}
    except requests.exceptions.RequestException as e:
        return {"error": "Error consultando USIG normalizar", "detalle": str(e), "query": q}

    items = data.get("direccionesNormalizadas") or []

    # Filtrado duro: CABA + tipo permitido + tiene texto
    filtrados = [
        it for it in items
        if _solo_caba(it) and _tipo_permitido(it) and _tiene_texto_de_calle(it)
    ]

    sugerencias = []
    seen = set()

    for it in filtrados:
        label = _armar_label(it)
        if not label:
            continue

        # Dedupe
        key = label.upper()
        if key in seen:
            continue
        seen.add(key)

        sugerencias.append({
            "label": label,
            "nombre_calle": (it.get("nombre_calle") or "").strip() or None,
            "cod_calle": it.get("cod_calle"),
            "altura": it.get("altura"),
            "tipo": it.get("tipo"),
        })

        if len(sugerencias) >= limit:
            break

    return {"query": q, "sugerencias": sugerencias}