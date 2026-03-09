import api_manzanas
print("USANDO api_manzanas DESDE:", api_manzanas.__file__)

from api_manzanas import cargar_manzana_por_smp

if __name__ == "__main__":
    smp = "044-097A-029"
    info = cargar_manzana_por_smp(smp)
    print("=== OK: manzana cargada ===")
    for k, v in info.items():
        print(f"{k}: {v}")