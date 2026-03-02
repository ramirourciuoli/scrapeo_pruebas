import json
import re
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

URL = "https://ciudad3d.buenosaires.gob.ar/"
SEARCH_INPUT = "#usig-autocomplete-input"
OUT_DIR = Path("salida_json")


# -------------------------------------------------------
# UTILIDADES
# -------------------------------------------------------
def close_legal_modal_if_present(page, timeout_ms=12000):
    dialog = page.locator("div[role='dialog']").first
    try:
        dialog.wait_for(state="visible", timeout=timeout_ms)
    except PWTimeoutError:
        return False

    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)
        if not dialog.is_visible():
            return True
    except:
        pass

    for sel in [
        "button[aria-label*='cerrar' i]",
        "button[aria-label*='close' i]",
        "div[role='dialog'] button"
    ]:
        try:
            btn = page.locator(sel).first
            if btn.is_visible():
                btn.click()
                page.wait_for_timeout(500)
                return True
        except:
            pass

    return False


def is_json_response(resp) -> bool:
    try:
        ct = (resp.headers.get("content-type") or "").lower()
        url = resp.url.lower()

        if "mbtiles" in url:
            return False

        if not ("json" in ct or "geo+json" in ct):
            return False

        # 🔎 Filtramos SOLO endpoints útiles
        return any(k in url for k in [
            "cur3d",
            "codigo",
            "edificabilidad",
            "parcel"
        ])
    except:
        return False


def safe_name(url: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9]+", "_", url)
    return name[:180] + ".json"


# -------------------------------------------------------
# PROCESO PRINCIPAL
# -------------------------------------------------------
def run(address: str):
    OUT_DIR.mkdir(exist_ok=True)
    captured = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1400, "height": 900}
        )
        page = context.new_page()

        # -----------------------------
        # Captura de responses
        # -----------------------------
        def handle_response(resp):
            if not is_json_response(resp):
                return
            try:
                data = resp.json()
            except:
                return

            fn = safe_name(resp.url)
            (OUT_DIR / fn).write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            captured.append(resp.url)
            print("✔ JSON capturado:", resp.url)

        page.on("response", handle_response)

        # -----------------------------
        # Navegación
        # -----------------------------
        page.goto(URL, wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(5000)

        close_legal_modal_if_present(page)

        # -----------------------------
        # Búsqueda de dirección
        # -----------------------------
        page.wait_for_selector(SEARCH_INPUT, timeout=30000)
        search = page.locator(SEARCH_INPUT)
        search.click()
        search.fill(address)
        page.wait_for_timeout(300)
        search.press("Enter")

        # -----------------------------
        # Esperar respuestas reales
        # -----------------------------
        page.wait_for_timeout(12000)

        browser.close()

    (OUT_DIR / "_urls_capturadas.txt").write_text(
        "\n".join(captured),
        encoding="utf-8"
    
    )
    print(f"\n✔ Listo. Guardé {len(captured)} JSON en: {OUT_DIR.resolve()}")

    
# -------------------------------------------------------
# EJECUCIÓN
# -------------------------------------------------------
if __name__ == "__main__":
    run("Dávila 1172")