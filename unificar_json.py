import json
from pathlib import Path

# carpeta donde están los archivos
carpeta = Path")

# archivo final
salida = Path("lotes_unificados.jsonl")

with salida.open("w", encoding="utf-8") as outfile:

    for archivo in sorted(carpeta.glob("*_response*")):
        try:
            with archivo.open("r", encoding="utf-8") as f:
                data = json.load(f)

            json.dump(data, outfile, ensure_ascii=False)
            outfile.write("\n")

        except Exception as e:
            print(f"Error leyendo {archivo}: {e}")

print("Archivo creado:", salida)