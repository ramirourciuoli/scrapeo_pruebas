from ciudad3d.extraer_prefactibilidad import extraer_prefactibilidad


def obtener_prefactibilidad_ciudad3d(direccion: str) -> dict:
    """
    Punto único de entrada para Ciudad3D
    """
    return extraer_prefactibilidad(direccion)