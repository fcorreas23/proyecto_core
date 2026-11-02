from unittest.mock import patch, Mock, call
import pytest
import requests
import cliente
from cliente import con_reintento, consultar_modelo
from consumir_api import enviar_peticion, registrar_costo

MODELO = "gemini-3.5-flash-lite"  # precios: entrada 0.0000003, salida 0.0000025
RESPUESTA_FALSA = {
    "candidates": [{"content": {"parts": [{"text": "Santiago"}]}}],
    "usageMetadata": {"promptTokenCount": 1000, "candidatesTokenCount": 100, "totalTokenCount": 1100},
}
COSTO_RESPUESTA_FALSA = 1000 * 0.0000003 + 100 * 0.0000025

# Reinicia el costo acumulado para que una prueba no contamine a la siguiente
@pytest.fixture(autouse=True)
def reiniciar_costo_total():
    cliente.costo_total_sesion = 0
    yield

# Evita que consultar_modelo dependa de la GEMINI_API_KEY real
@pytest.fixture
def peticion_armada():
    with patch("cliente.armar_peticion", return_value=("http://url_falsa", {"data": "test"})):
        yield

# ================= TESTS ENVIAR_PETICION =================

def test_enviar_peticion_credencial_invalida():
    respuesta_falsa = Mock(status_code=401)
    with patch("consumir_api.requests.post", return_value=respuesta_falsa):
        with pytest.raises(ValueError):
            enviar_peticion("http://url_falsa", {"data": "test"})

def test_enviar_peticion_limite_de_uso():
    respuesta_falsa = Mock(status_code=429, headers={})
    with patch("consumir_api.requests.post", return_value=respuesta_falsa):
        with pytest.raises(TimeoutError):
            enviar_peticion("http://url_falsa", {"data": "test"})

def test_enviar_peticion_error_del_servidor():
    respuesta_falsa = Mock(status_code=503)
    with patch("consumir_api.requests.post", return_value=respuesta_falsa):
        with pytest.raises(TimeoutError):
            enviar_peticion("http://url_falsa", {"data": "test"})

def test_enviar_peticion_tiempo_de_espera_agotado():
    with patch("consumir_api.requests.post", side_effect=requests.exceptions.Timeout):
        with pytest.raises(TimeoutError):
            enviar_peticion("http://url_falsa", {"data": "test"})

def test_enviar_peticion_exitosa():
    respuesta_falsa = Mock(status_code=200, json=lambda: {"resultado": "ok"})
    with patch("consumir_api.requests.post", return_value=respuesta_falsa):
        respuesta = enviar_peticion("http://url_falsa", {"data": "test"})
        assert respuesta == {"resultado": "ok"}

# ================= TESTS CON_REINTENTO =================

def test_con_reintento_agota_intentos():
    siempre_falla = Mock(side_effect=TimeoutError("simulado"))
    with patch("cliente.time.sleep") as dormir:
        with pytest.raises(TimeoutError):
            con_reintento(siempre_falla, intentos=3)
    assert siempre_falla.call_count == 3
    assert dormir.call_count == 2

def test_con_reintento_no_reintenta_value_error():
    falla_credencial = Mock(side_effect=ValueError("simulado"))
    with patch("cliente.time.sleep") as dormir:
        with pytest.raises(ValueError):
            con_reintento(falla_credencial)
    assert falla_credencial.call_count == 1
    dormir.assert_not_called()

def test_con_reintento_exitoso_tras_un_fallo():
    falla_una_vez = Mock(side_effect=[TimeoutError("simulado"), "ok"])
    with patch("cliente.time.sleep"):
        assert con_reintento(falla_una_vez) == "ok"
    assert falla_una_vez.call_count == 2

def test_con_reintento_esperas_crecen_hasta_el_maximo():
    siempre_falla = Mock(side_effect=TimeoutError("simulado"))
    with patch("cliente.time.sleep") as dormir, patch("cliente.random.uniform", return_value=0):
        with pytest.raises(TimeoutError):
            con_reintento(siempre_falla, intentos=4, espera_base=2, espera_maxima=5)
    assert dormir.call_args_list == [call(2), call(4), call(5)]

# ================= TESTS REGISTRAR_COSTO =================

def test_registrar_costo_usa_precio_de_entrada_y_salida():
    assert registrar_costo(RESPUESTA_FALSA, MODELO) == pytest.approx(COSTO_RESPUESTA_FALSA)

def test_registrar_costo_sin_uso_de_tokens():
    with pytest.raises(RuntimeError):
        registrar_costo({}, MODELO)

def test_registrar_costo_modelo_desconocido():
    with pytest.raises(ValueError):
        registrar_costo(RESPUESTA_FALSA, "modelo-inexistente")

# ================= TESTS CONSULTAR_MODELO =================

def test_consultar_modelo_convierte_error(peticion_armada):
    with patch("cliente.con_reintento", side_effect=TimeoutError("simulado")):
        with pytest.raises(RuntimeError):
            consultar_modelo("pregunta de prueba")

def test_consultar_modelo_devuelve_texto_y_acumula_costo(peticion_armada):
    with patch("cliente.enviar_peticion", return_value=RESPUESTA_FALSA):
        assert consultar_modelo("pregunta de prueba", MODELO) == "Santiago"
        consultar_modelo("pregunta de prueba", MODELO)
    assert cliente.costo_total_sesion == pytest.approx(2 * COSTO_RESPUESTA_FALSA)

def test_consultar_modelo_no_cobra_si_falla(peticion_armada):
    with patch("cliente.con_reintento", side_effect=TimeoutError("simulado")):
        with pytest.raises(RuntimeError):
            consultar_modelo("pregunta de prueba", MODELO)
    assert cliente.costo_total_sesion == 0
