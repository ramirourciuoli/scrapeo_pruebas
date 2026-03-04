"""
correr_muestras_100.py
======================

OBJETIVO
--------
1) Lee el Excel "muestra_100_frente_num_dom.xlsx" (columnas: frente, num_dom).
2) Construye direccion = "<frente> <num_dom>".
3) Llama a tu API Flask:

      POST http://127.0.0.1:8000/api/catastro
      JSON: {"direccion": "CALLE 123"}

4) Guarda auditoría y resultados:
   - salida_muestras_100/001_request.json ... 100_request.json
   - salida_muestras_100/001_response.json ... 100_response.json (si es JSON)
   - salida_muestras_100/001_response.txt  ... 100_response.txt  (si no es JSON o hay error)
   - salida_muestras_100/resumen.csv
   - salida_muestras_100/input_motor.jsonl    (SOLO casos OK, 1 JSON por línea)

NOTA IMPORTANTE (opción 1)
--------------------------
El archivo input_motor.jsonl es el "input limpio" para el motor:
- 1 línea = 1 caso
- Cada JSON incluye una llave _testcase con (n, direccion) para trazabilidad.

REQUISITOS
----------
pip install pandas requests openpyxl
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pandas as pd
import requests


# =====================
# CONFIG
# =====================
EXCEL_IN = Path("muestra_100_frente_num_dom.xlsx")

API_URL = "http://127.0.0.1:8000/api/catastro"

OUT_DIR = Path("salida_muestras_100")
OUT_DIR.mkdir(exist_ok=True)

TIMEOUT_SECS = 30
RETRIES = 2
SLEEP_BETWEEN_RETRIES = 0.75  # segundos
SLEEP_BETWEEN_REQUESTS = 0.20  # segundos (para no saturar tu servidor ni endpoints externos)

PRINT_EVERY = 10  # feedback cada N casos


# =====================
# MODELOS / HELPERS
# =====================
@dataclass
class CallResult:
    http_code: Optional[int]
    text: str
    elapsed_s: Optional[float]
    error: str = ""


def dump_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def dump_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def normalize_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df


def clean_num_dom(num_dom: Any) -> str:
    """Normaliza num_dom por si viene como 123.0 u otros formatos."""
    if pd.isna(num_dom):
        return ""
    s = str(num_dom).strip()
    # caso típico Excel: 123.0
    if s.endswith(".0"):
        s = s[:-2]
    # compactar espacios
    s = " ".join(s.split())
    return s


def build_direccion(frente: Any, num_dom: Any) -> str:
    f = "" if pd.isna(frente) else str(frente).strip()
    f = " ".join(f.split())
    n = clean_num_dom(num_dom)
    direccion = f"{f} {n}".strip()
    direccion = " ".join(direccion.split())
    return direccion


def try_parse_json(text: str) -> Tuple[bool, Any]:
    try:
        return True, json.loads(text)
    except Exception:
        return False, None


def call_api(payload: Dict[str, Any]) -> CallResult:
    """POST JSON a la API con reintentos. Devuelve siempre texto para poder auditar."""
    last_exc: Optional[Exception] = None

    for attempt in range(RETRIES + 1):
        try:
            t0 = time.time()
            r = requests.post(API_URL, json=payload, timeout=TIMEOUT_SECS)
            elapsed = time.time() - t0
            return CallResult(http_code=r.status_code, text=r.text, elapsed_s=elapsed)

        except Exception as e:
            last_exc = e
            time.sleep(SLEEP_BETWEEN_RETRIES)

    return CallResult(http_code=None, text="", elapsed_s=None, error=repr(last_exc))


def main() -> None:
    # ---------- Validaciones iniciales ----------
    if not EXCEL_IN.exists():
        raise FileNotFoundError(
            f"No encuentro {EXCEL_IN}. Ponelo en la misma carpeta que este script."
        )

    # ---------- Leer Excel ----------
    df = pd.read_excel(EXCEL_IN)
    df = normalize_cols(df)

    if "frente" not in df.columns or "num_dom" not in df.columns:
        raise ValueError(
            f"Columnas encontradas: {list(df.columns)}. Se requieren 'frente' y 'num_dom'."
        )

    total = len(df)
    resumen_rows = []

    # ---------- Loop principal ----------
    for i, row in df.iterrows():
        n = i + 1

        frente = row["frente"]
        num_dom = row["num_dom"]
        direccion = build_direccion(frente, num_dom)

        payload = {"direccion": direccion}

        req_path = OUT_DIR / f"{n:03d}_request.json"
        resp_json_path = OUT_DIR / f"{n:03d}_response.json"
        resp_txt_path = OUT_DIR / f"{n:03d}_response.txt"

        dump_json(req_path, payload)

        status = "OK"
        err = ""

        result = call_api(payload)

        # Caso: no hubo HTTP (excepción)
        if result.http_code is None:
            status = "ERROR"
            err = result.error or "Error desconocido (sin HTTP)"
            dump_text(resp_txt_path, err)

        else:
            # Si HTTP indica error, lo marcamos, pero igual intentamos parsear y guardar
            if result.http_code >= 400:
                status = "ERROR"
                err = f"HTTP {result.http_code}"

            # Parsear JSON
            ok_json, data = try_parse_json(result.text)

            if ok_json:
                dump_json(resp_json_path, data)
            else:
                dump_text(resp_txt_path, result.text)
                status = "ERROR"
                err = (err + " | " if err else "") + "Respuesta no es JSON válido"

        resumen_rows.append(
            {
                "n": n,
                "direccion": direccion,
                "status": status,
                "http_code": result.http_code,
                "elapsed_s": result.elapsed_s,
                "error": err,
            }
        )

        # Feedback en consola
        if PRINT_EVERY and (n % PRINT_EVERY == 0 or n == total):
            print(f"[{n:03d}/{total}] {status} - {direccion}")

        # Pausa para no saturar
        time.sleep(SLEEP_BETWEEN_REQUESTS)

    # ---------- Guardar resumen ----------
    resumen_df = pd.DataFrame(resumen_rows)
    resumen_csv = OUT_DIR / "resumen.csv"
    resumen_df.to_csv(resumen_csv, index=False, encoding="utf-8")

    # ---------- Generar input_motor.jsonl (Opción 1) ----------
    # 1 línea = 1 caso OK (JSON válido), con _testcase agregado para trazabilidad.
    jsonl_path = OUT_DIR / "input_motor.jsonl"

    ok_written = 0
    with jsonl_path.open("w", encoding="utf-8") as f:
        for r in resumen_rows:
            if r["status"] != "OK":
                continue

            resp_path = OUT_DIR / f"{r['n']:03d}_response.json"
            if not resp_path.exists():
                continue

            try:
                data = json.loads(resp_path.read_text(encoding="utf-8"))
            except Exception:
                continue

            # Agregar metadata de test
            data["_testcase"] = {"n": r["n"], "direccion": r["direccion"]}

            f.write(json.dumps(data, ensure_ascii=False) + "\n")
            ok_written += 1

    # ---------- Resumen final ----------
    ok_count = int((resumen_df["status"] == "OK").sum())
    err_count = int((resumen_df["status"] == "ERROR").sum())

    print("\n=== LISTO ===")
    print("API_URL:", API_URL)
    print("Carpeta salida:", OUT_DIR.resolve())
    print("Resumen:", resumen_csv.resolve())
    print("Input motor:", jsonl_path.resolve())
    print(f"OK: {ok_count} | ERROR: {err_count} | JSONL escritos: {ok_written}")


if __name__ == "__main__":
    main()