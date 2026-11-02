from pipeline_limpieza  import procesar_texto

def test_procesar_texto_normaliza_mayusculas_y_puntuacion():
    texto = "¡Hola, Mundo!"
    esperado = ["hola", "mundo"]
    assert procesar_texto(texto) == esperado


def test_procesar_texto_solo_puntuacion_devuelve_lista_vacia():
    texto = "¡.,;:!?"
    esperado = []
    assert procesar_texto(texto) == esperado