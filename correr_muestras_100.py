"""
correr_muestras_100.py
======================

OBJETIVO
--------
1) Busca un Excel en la misma carpeta del script (o usa uno indicado por parámetro)
   que tenga columnas: frente, num_dom.
2) Construye direccion = "<frente> <num_dom>".
3) POST a API:
      http://127.0.0.1:8000/api/catastro
4) Guarda auditoría y resultados en salida_muestras_100/
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pandas as pd
import requests


# =====================
# CONFIG
# =====================
API_URL = "http://127.0.0.1:8000/api/catastro"

# Carpeta del script (no depende de desde dónde lo ejecutes)
SCRIPT_DIR = Path(__file__).resolve().parent

OUT_DIR = SCRIPT_DIR / "salida_muestras_100"
OUT_DIR.mkdir(exist_ok=True)

TIMEOUT_SECS = 30
RETRIES = 2
SLEEP_BETWEEN_RETRIES = 0.75
SLEEP_BETWEEN_REQUESTS = 0.20
PRINT_EVERY = 10


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
    if s.endswith(".0"):
        s = s[:-2]
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
    last_exc: Optional[Exception] = None

    for _attempt in range(RETRIES + 1):
        try:
            t0 = time.time()
            r = requests.post(API_URL, json=payload, timeout=TIMEOUT_SECS)
            elapsed = time.time() - t0
            return CallResult(http_code=r.status_code, text=r.text, elapsed_s=elapsed)
        except Exception as e:
            last_exc = e
            time.sleep(SLEEP_BETWEEN_RETRIES)

    return CallResult(http_code=None, text="", elapsed_s=None, error=repr(last_exc))


def excel_tiene_columnas(path: Path) -> bool:
    """Chequea rápido si el Excel tiene columnas frente/num_dom (sin leer todo)."""
    try:
        header = pd.read_excel(path, nrows=0)
        cols = [str(c).strip().lower() for c in header.columns]
        return ("frente" in cols) and ("num_dom" in cols)
    except Exception:
        return False


def elegir_excel_input() -> Path:
    """
    Prioridad:
    1) Si pasás un argumento: python correr_muestras_100.py archivo.xlsx -> usa ese
    2) Si no, busca en la carpeta del script el Excel más nuevo que tenga frente/num_dom
    """
    # 1) Argumento opcional
    if len(sys.argv) >= 2:
        p = Path(sys.argv[1])
        if not p.is_absolute():
            p = (SCRIPT_DIR / p).resolve()
        if not p.exists():
            raise FileNotFoundError(f"No encuentro el Excel indicado: {p}")
        if p.suffix.lower() not in (".xlsx", ".xls"):
            raise ValueError(f"El archivo indicado no parece Excel: {p.name}")
        if not excel_tiene_columnas(p):
            raise ValueError(f"El Excel indicado no tiene columnas 'frente' y 'num_dom': {p.name}")
        return p

    # 2) Autodetección en carpeta del script
    candidatos = []
    for ext in ("*.xlsx", "*.xls"):
        for p in SCRIPT_DIR.glob(ext):
            # Evitar tomar archivos temporales de Excel
            if p.name.startswith("~$"):
                continue
            if excel_tiene_columnas(p):
                candidatos.append(p)

    if not candidatos:
        raise FileNotFoundError(
            "No encontré ningún Excel en la misma carpeta del script con columnas "
            "'frente' y 'num_dom'. Poné el Excel al lado del .py o pasalo como parámetro."
        )

    # Si hay varios, elegir el más nuevo por fecha de modificación
    candidatos.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return candidatos[0]


def main() -> None:
    # ---------- Elegir Excel ----------
    EXCEL_IN = elegir_excel_input()
    print("Usando Excel:", EXCEL_IN.name)

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

        direccion = build_direccion(row["frente"], row["num_dom"])
        payload = {"direccion": direccion}

        req_path = OUT_DIR / f"{n:03d}_request.json"
        resp_json_path = OUT_DIR / f"{n:03d}_response.json"
        resp_txt_path = OUT_DIR / f"{n:03d}_response.txt"

        dump_json(req_path, payload)

        status = "OK"
        err = ""

        result = call_api(payload)

        if result.http_code is None:
            status = "ERROR"
            err = result.error or "Error desconocido (sin HTTP)"
            dump_text(resp_txt_path, err)
        else:
            if result.http_code >= 400:
                status = "ERROR"
                err = f"HTTP {result.http_code}"

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

        if PRINT_EVERY and (n % PRINT_EVERY == 0 or n == total):
            print(f"[{n:03d}/{total}] {status} - {direccion}")

        time.sleep(SLEEP_BETWEEN_REQUESTS)

    # ---------- Guardar resumen ----------
    resumen_df = pd.DataFrame(resumen_rows)
    resumen_csv = OUT_DIR / "resumen.csv"
    resumen_df.to_csv(resumen_csv, index=False, encoding="utf-8")

    # ---------- Generar input_motor.jsonl ----------
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

            data["_testcase"] = {"n": r["n"], "direccion": r["direccion"]}
            f.write(json.dumps(data, ensure_ascii=False) + "\n")
            ok_written += 1

    ok_count = int((resumen_df["status"] == "OK").sum())
    err_count = int((resumen_df["status"] == "ERROR").sum())

    print("\n=== LISTO ===")
    print("API_URL:", API_URL)
    print("Excel usado:", EXCEL_IN.resolve())
    print("Carpeta salida:", OUT_DIR.resolve())
    print("Resumen:", resumen_csv.resolve())
    print("Input motor:", jsonl_path.resolve())
    print(f"OK: {ok_count} | ERROR: {err_count} | JSONL escritos: {ok_written}")


if __name__ == "__main__":
    main()