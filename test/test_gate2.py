"""
Pruebas de los cuatro criterios no compensables del Gate 2, sobre el servicio real
(src/Gate2/servicio_rag.py) en modo simulado: no llaman a la API ni gastan cuota.

Ejecutar desde la raíz del proyecto:
    python -m pytest test/test_gate2.py -v
"""
import logging

import pytest
from langgraph.types import Command

from grafo_supervision import HUELLA_NUEVA, app_despliegue
from log_rag import JsonFormatter, logger
from servicio_rag import cargar_indice, crear_modelo, responder

# Dato sensible de prueba que NUNCA debe aparecer en los logs
CORREO = "ana.perez@example.com"
PREGUNTA = "¿Como deshago un commit que ya comparti con mi equipo? Mi correo es " + CORREO


# ===== Adaptación al proyecto: el servicio real, con embeddings y modelo simulados =====
@pytest.fixture(scope="module")
def vectorstore(tmp_path_factory):
    """Índice persistido en una carpeta temporal, indexado con el corpus real."""
    vs, _, n_chunks = cargar_indice(simulado=True, directorio=tmp_path_factory.mktemp("indice"))
    assert n_chunks > 0
    return vs


def ejecutar_servicio(vectorstore, pregunta):
    """Devuelve (respuesta, fuentes), igual que la plantilla de la guía."""
    resultado = responder(pregunta, vectorstore, crear_modelo(simulado=True), simulado=True)
    assert "error" not in resultado, f"el servicio capturó un error: {resultado.get('error')}"
    return resultado["respuesta"], resultado["fuentes"]
# ===== Fin de la adaptación =====


def test_1_pipeline_sin_excepciones(vectorstore):
    respuesta, _ = ejecutar_servicio(vectorstore, PREGUNTA)
    assert respuesta.strip(), "el servicio devolvio una respuesta vacia"


def test_2_respuesta_cita_fuente(vectorstore):
    respuesta, fuentes = ejecutar_servicio(vectorstore, PREGUNTA)
    assert fuentes, "el servicio no devolvio ninguna fuente"
    assert any(f in respuesta for f in fuentes), "la respuesta no menciona su fuente"


def test_3_logs_sin_contenido_crudo(vectorstore, caplog, tmp_path, monkeypatch):
    # El logger del proyecto tiene propagate=False (para no duplicar líneas), así que caplog no
    # lo vería por sí solo. Se le conecta directo, junto con un archivo JSON igual al real.
    archivo = logging.FileHandler(tmp_path / "rag_logs.jsonl", encoding="utf-8")
    archivo.setFormatter(JsonFormatter())
    monkeypatch.setattr(logger, "handlers", [caplog.handler, archivo])

    with caplog.at_level(logging.DEBUG, logger=logger.name):
        ejecutar_servicio(vectorstore, PREGUNTA)
    archivo.close()

    assert caplog.records, "no se capturó ningún log: la prueba no estaría verificando nada"
    texto_logs = " ".join(r.getMessage() + " " + str(r.__dict__) for r in caplog.records)
    texto_logs += (tmp_path / "rag_logs.jsonl").read_text(encoding="utf-8")
    assert CORREO not in texto_logs, "un dato sensible aparece en los logs"
    assert PREGUNTA not in texto_logs, "la consulta completa aparece en los logs"


def test_4_supervision_pausa_y_reanuda():
    config = {"configurable": {"thread_id": "test-gate2-aprobar"}}
    pausado = app_despliegue.invoke({"huella_nueva": HUELLA_NUEVA, "aprobado": False}, config=config)
    assert "__interrupt__" in pausado, "el grafo no se detuvo en el punto de supervision"
    final = app_despliegue.invoke(Command(resume=True), config=config)
    assert "__interrupt__" not in final, "el grafo sigue pausado despues de reanudar"
    assert final["aprobado"] is True, "la decision no quedo registrada"

    # El camino de rechazo, con otro thread_id
    config = {"configurable": {"thread_id": "test-gate2-rechazar"}}
    app_despliegue.invoke({"huella_nueva": HUELLA_NUEVA, "aprobado": False}, config=config)
    assert app_despliegue.invoke(Command(resume=False), config=config)["aprobado"] is False
