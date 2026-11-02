import time
import random
from typing import Callable, Any
from consumir_api import armar_peticion, extraer_texto, enviar_peticion, registrar_costo

MODELO = "gemini-3.5-flash-lite"
costo_total_sesion = 0.0

# Función que reintenta una llamada con espera exponencial cuando el servicio no responde
def con_reintento(
    funcion: Callable[[], Any],
    intentos: int = 3,
    espera_base: float = 2,
    espera_maxima: float = 30,
) -> Any:
    for intento in range(1, intentos + 1):
        try:
            return funcion()
        except TimeoutError:
            if intento == intentos:
                raise
            espera = min(espera_base * (2 ** (intento - 1)), espera_maxima)
            espera_con_jitter = espera + random.uniform(0, espera * 0.1)
            print(f"Intento {intento} de {intentos} falló. Reintentando en {espera_con_jitter:.1f}s...")
            time.sleep(espera_con_jitter)

# Función que consulta el modelo con reintentos y acumula el costo de la sesión
def consultar_modelo(pregunta, modelo=MODELO, system_instruction=None):
    global costo_total_sesion
    url, cuerpo = armar_peticion(pregunta, modelo, system_instruction)
    try:
        respuesta = con_reintento(lambda: enviar_peticion(url, cuerpo))
    except TimeoutError:
        raise RuntimeError("El servicio no respondió tras varios intentos. Intenta más tarde.")
    costo_total_sesion += registrar_costo(respuesta, modelo)
    return extraer_texto(respuesta)


if __name__ == "__main__":
    try:
        resultado = consultar_modelo("¿Cuál es la capital de Chile?")
        print(resultado)
        print(f"Costo total de la sesión: ${costo_total_sesion:.6f}")
    except (ValueError, RuntimeError) as error:
        print("No se pudo completar la operación:", error)
