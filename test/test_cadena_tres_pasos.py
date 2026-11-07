from unittest.mock import MagicMock
from langchain_core.messages import AIMessage
from cadena_tres_pasos import construir_cadena

# El side_effect va en el mock directo: LangChain lo llama como modelo_falso(...), no con .invoke
def crear_modelo_falso():
    modelo_falso = MagicMock()
    modelo_falso.side_effect = [
        AIMessage(content="punto 1\npunto 2\npunto 3"),
        AIMessage(content="texto simplificado"),
        AIMessage(content="- viñeta 1\n- viñeta 2"),
    ]
    return modelo_falso

def test_cadena_conecta_los_tres_pasos():
    modelo_falso = crear_modelo_falso()
    cadena = construir_cadena(modelo_falso)
    resultado = cadena.invoke({"texto": "texto de prueba"})
    assert modelo_falso.call_count == 3
    assert "viñeta" in resultado

def test_cadena_pasa_la_salida_de_cada_paso_al_siguiente():
    modelo_falso = crear_modelo_falso()
    construir_cadena(modelo_falso).invoke({"texto": "texto de prueba"})
    extraccion, simplificacion, formato = [llamada.args[0].to_string() for llamada in modelo_falso.call_args_list]
    assert "texto de prueba" in extraccion
    assert "punto 1\npunto 2\npunto 3" in simplificacion
    assert "texto simplificado" in formato
