import logging
from unittest.mock import MagicMock
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from enrutamiento import (
    MENSAJE_ERROR,
    construir_cadena_con_enrutamiento,
    construir_cadena_queja_segura,
    construir_cadena_robusta,
    construir_paso_clasificacion,
    procesar_mensaje_seguro,
)

# Pruebas del flujo orquestado de enrutamiento.py, ordenadas según el checklist del Bloque 20.

# Crea una clasificación falsa que siempre devuelve la categoría indicada
def crear_clasificacion_falsa(categoria):
    clasificacion_falsa = MagicMock()
    clasificacion_falsa.return_value = categoria
    return clasificacion_falsa

# Crea una ruta falsa que siempre devuelve la respuesta indicada
def crear_ruta_falsa(respuesta):
    ruta_falsa = MagicMock()
    ruta_falsa.return_value = respuesta
    return ruta_falsa

# ================= TESTS CLASIFICACIÓN =================

def test_clasificacion_normaliza_antes_de_comparar():
    modelo_falso = MagicMock()
    modelo_falso.return_value = AIMessage(content=" Queja \n")

    resultado = construir_paso_clasificacion(modelo_falso).invoke(
        {"mensaje": "algo salió mal"}
    )

    assert resultado == "queja"

def test_clasificacion_respuesta_vacia_no_rompe_el_paso():
    modelo_falso = MagicMock()
    modelo_falso.return_value = AIMessage(content="  \n")

    resultado = construir_paso_clasificacion(modelo_falso).invoke({"mensaje": ""})

    assert resultado == ""

def test_clasificacion_vacia_cae_en_la_ruta_por_defecto():
    cadena_pregunta_falsa = crear_ruta_falsa("respuesta por defecto")
    cadena = construir_cadena_con_enrutamiento(
        paso_clasificacion=crear_clasificacion_falsa(""),
        cadena_pregunta=cadena_pregunta_falsa,
    )

    assert cadena.invoke({"mensaje": ""}) == "respuesta por defecto"

# ================= TESTS BIFURCACIÓN =================

def test_enrutamiento_va_a_cadena_queja():
    cadena_queja_falsa = crear_ruta_falsa("respuesta de queja")
    cadena = construir_cadena_con_enrutamiento(
        paso_clasificacion=crear_clasificacion_falsa("queja"),
        cadena_queja=cadena_queja_falsa,
    )
    resultado = cadena.invoke({"mensaje": "esto no funciona nunca"})

    assert cadena_queja_falsa.called
    assert resultado == "respuesta de queja"

def test_enrutamiento_va_a_cadena_sugerencia():
    cadena_sugerencia_falsa = crear_ruta_falsa("respuesta de sugerencia")
    cadena = construir_cadena_con_enrutamiento(
        paso_clasificacion=crear_clasificacion_falsa("sugerencia"),
        cadena_sugerencia=cadena_sugerencia_falsa,
    )
    resultado = cadena.invoke({"mensaje": "sería útil un modo oscuro"})

    assert cadena_sugerencia_falsa.called
    assert resultado == "respuesta de sugerencia"

def test_enrutamiento_va_a_cadena_pregunta():
    cadena_pregunta_falsa = crear_ruta_falsa("respuesta de pregunta")
    cadena = construir_cadena_con_enrutamiento(
        paso_clasificacion=crear_clasificacion_falsa("pregunta"),
        cadena_pregunta=cadena_pregunta_falsa,
    )
    resultado = cadena.invoke({"mensaje": "¿cómo cambio mi contraseña?"})

    assert cadena_pregunta_falsa.called
    assert resultado == "respuesta de pregunta"

def test_enrutamiento_usa_default_ante_categoria_desconocida():
    cadena_pregunta_falsa = crear_ruta_falsa("respuesta por defecto")
    cadena = construir_cadena_con_enrutamiento(
        paso_clasificacion=crear_clasificacion_falsa("categoria_inventada"),
        cadena_pregunta=cadena_pregunta_falsa,
    )
    resultado = cadena.invoke({"mensaje": "mensaje ambiguo"})

    assert cadena_pregunta_falsa.called
    assert resultado == "respuesta por defecto"

def test_enrutamiento_pasa_mensaje_y_categoria_a_la_ruta():
    cadena_queja_falsa = crear_ruta_falsa("respuesta de queja")
    cadena = construir_cadena_con_enrutamiento(
        paso_clasificacion=crear_clasificacion_falsa("queja"),
        cadena_queja=cadena_queja_falsa,
    )
    cadena.invoke({"mensaje": "esto no funciona nunca"})

    entrada_de_la_ruta = cadena_queja_falsa.call_args.args[0]
    assert entrada_de_la_ruta == {"mensaje": "esto no funciona nunca", "categoria": "queja"}

# ================= TESTS FALLBACK POR RUTA =================

def test_cadena_queja_usa_fallback_ante_fallo_del_modelo():
    def fallar_a_proposito(x):
        raise ConnectionError("simulado")
    cadena_queja_falsa = RunnableLambda(fallar_a_proposito)
    cadena_queja_segura = construir_cadena_queja_segura(cadena_queja_falsa)

    resultado = cadena_queja_segura.invoke({"mensaje": "esto no funciona"})

    assert "equipo" in resultado.lower()

# ================= TESTS FALLBACK DE LA CADENA COMPLETA =================

def test_cadena_robusta_usa_respaldo_si_falla_la_clasificacion():
    clasificacion_que_falla = MagicMock(side_effect=RuntimeError("API caída"))
    respaldo_falso = crear_ruta_falsa("respuesta de respaldo")
    cadena = construir_cadena_robusta(
        construir_cadena_con_enrutamiento(paso_clasificacion=clasificacion_que_falla),
        respaldo=RunnableLambda(respaldo_falso),
    )
    resultado = cadena.invoke({"mensaje": "esto no funciona nunca"})

    assert resultado == "respuesta de respaldo"
    entrada_del_respaldo = respaldo_falso.call_args.args[0]
    assert isinstance(entrada_del_respaldo["error"], RuntimeError)

def test_cadena_robusta_no_usa_respaldo_si_no_hay_error():
    respaldo_falso = crear_ruta_falsa("respuesta de respaldo")
    cadena = construir_cadena_robusta(
        construir_cadena_con_enrutamiento(
            paso_clasificacion=crear_clasificacion_falsa("queja"),
            cadena_queja=crear_ruta_falsa("respuesta de queja"),
        ),
        respaldo=RunnableLambda(respaldo_falso),
    )

    assert cadena.invoke({"mensaje": "esto no funciona nunca"}) == "respuesta de queja"
    assert not respaldo_falso.called

def test_cadena_robusta_registra_el_error_original(caplog):
    cadena = construir_cadena_robusta(
        construir_cadena_con_enrutamiento(
            paso_clasificacion=MagicMock(side_effect=RuntimeError("API caída"))
        )
    )

    with caplog.at_level(logging.WARNING, logger="enrutamiento"):
        resultado = cadena.invoke({"mensaje": "esto no funciona nunca"})

    assert resultado.startswith("Gracias por tu mensaje")
    assert "API caída" in caplog.text

def test_capturador_registra_cada_error_una_sola_vez(caplog):
    cadena = construir_cadena_robusta(
        construir_cadena_con_enrutamiento(
            paso_clasificacion=MagicMock(side_effect=RuntimeError("API caída"))
        )
    )

    with caplog.at_level(logging.WARNING, logger="enrutamiento"):
        cadena.invoke({"mensaje": "primer mensaje"})
        cadena.invoke({"mensaje": "segundo mensaje"})

    assert len(caplog.records) == 2
    assert "[RuntimeError] -> API caída" in caplog.records[0].getMessage()

# ================= TESTS FLUJO COMPLETO =================

def test_procesar_mensaje_seguro_no_propaga_excepciones():
    clasificacion_falsa = MagicMock()
    clasificacion_falsa.side_effect = ConnectionError("simulado")
    cadena_falsa = construir_cadena_con_enrutamiento(
        paso_clasificacion=clasificacion_falsa,
    )

    resultado = procesar_mensaje_seguro(cadena_falsa, "mensaje de prueba")

    assert "no pudimos procesar" in resultado.lower()

def test_procesar_mensaje_seguro_registra_error_y_devuelve_mensaje(caplog):
    cadena_que_falla = MagicMock()
    cadena_que_falla.invoke.side_effect = RuntimeError("todo falló")

    with caplog.at_level(logging.ERROR, logger="enrutamiento"):
        resultado = procesar_mensaje_seguro(cadena_que_falla, "hola")

    assert resultado == MENSAJE_ERROR
    assert "todo falló" in caplog.text
