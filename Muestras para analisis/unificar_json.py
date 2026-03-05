import json
from pathlib import Path

# ✅ CAMBIÁ ESTA RUTA a la carpeta real donde están 001_response, 002_response, etc.
CARPETA = Path(r"C:\Users\ramir\OneDrive\Escritorio\Interfaz Buscador\Scrapeo_Pruebas\Muestras para analisis")

SALIDA_JSONL = CARPETA / "lotes_unificados.jsonl"
SALIDA_ERRORES = CARPETA / "errores_unificacion.txt"

# 1) Buscar candidatos (toma response con cualquier extensión)
candidatos = sorted([p for p in CARPETA.iterdir() if p.is_file() and "response" in p.name.lower()])

print(f"[INFO] Carpeta: {CARPETA}")
print(f"[INFO] Archivos encontrados con 'response' en el nombre: {len(candidatos)}")

if not candidatos:
    print("[ERROR] No encontré archivos 'response'. Revisá la ruta CARPETA o los nombres.")
    raise SystemExit(1)

ok = 0
fail = 0

with SALIDA_JSONL.open("w", encoding="utf-8") as out, SALIDA_ERRORES.open("w", encoding="utf-8") as err:
    for archivo in candidatos:
        try:
            text = archivo.read_text(encoding="utf-8", errors="replace").strip()
            if not text:
                fail += 1
                err.write(f"VACIO: {archivo.name}\n")
                continue

            data = json.loads(text)  # intenta parsear

            json.dump(data, out, ensure_ascii=False)
            out.write("\n")
            ok += 1

        except Exception as e:
            fail += 1
            err.write(f"ERROR: {archivo.name} -> {e}\n")

print(f"[RESULT] OK: {ok} | FAIL: {fail}")
print(f"[SALIDA] JSONL: {SALIDA_JSONL}")
print(f"[SALIDA] ERRORES: {SALIDA_ERRORES}")