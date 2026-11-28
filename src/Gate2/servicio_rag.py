"""
Gate 2 - Servicio RAG de punta a punta sobre la guía de Git/GitHub.

Une en un solo punto de entrada las piezas del Módulo 2:
  - Índice persistido con actualización incremental por ids fijos  (Bloque 25, rag_indexer.py)
  - Recuperación con citas [n] -> nombre del archivo fuente       (Bloques 26-27)
  - Latencia por etapa y costo por consulta                       (Bloque 28, registro_rag.py)
  - Logs JSON con trace_id, consumo y filtro de inyección          (Bloque 31, logging_rag.py)
  - Punto de supervisión humana con interrupt()/Command            (Bloque 32, grafo_supervision.py)

Uso (desde la raíz del proyecto):
    python src/Gate2/servicio_rag.py                       # consulta de ejemplo con Gemini real
    python src/Gate2/servicio_rag.py "¿Cómo creo una rama?"
    python src/Gate2/servicio_rag.py --simulado            # sin API: embeddings y modelo simulados
    python src/Gate2/servicio_rag.py --reindexar           # vuelve a indexar el corpus (upsert por id)
    python src/Gate2/servicio_rag.py --aprobar             # decisión de supervisión si no hay terminal

Los logs JSON salen por consola y se guardan en docs/rag_logs.jsonl. Nunca contienen el texto
de la pregunta, de los documentos ni de la respuesta: solo longitudes, huellas y nombres de archivo.
"""
import argparse
import itertools
import os
import re
import sys
import time
import uuid
from pathlib import Path

from langchain_core.documents import Document
from langchain_core.messages import AIMessage
from langgraph.types import Command

from grafo_supervision import HUELLA_NUEVA, app_despliegue
from log_rag import MODELO, HandlerDeTrazabilidad, logger, trace_id_var
from logging_rag import procesar_consulta
from rag_indexer import cargar_vectorstore, indexar_corpus
from registro_rag import calcular_costo, obtener_precios

RAIZ = Path(__file__).resolve().parents[2]
CORPUS = [RAIZ / "Guia_Git_GitHub_3_Usuarios.md"]
INDICE_REAL = RAIZ / "vectorstore"
INDICE_SIMULADO = RAIZ / "vectorstore_simulado"  # otra dimensión de embedding: nunca mezclar con el real
K = 3

PREGUNTA_EJEMPLO = "¿Cómo deshago un commit que ya compartí con mi equipo?"
SIN_CONTEXTO = "No tengo informacion suficiente y verificada para responder esto."
CONSULTA_BLOQUEADA = "La consulta fue bloqueada por el filtro de seguridad."
ERROR_SERVICIO = "El servicio no pudo generar una respuesta en este momento. Intenta de nuevo mas tarde."


# ---------------------------------------------------------------------------
# Modelos: reales (Gemini) o simulados (sin API ni costo)
# ---------------------------------------------------------------------------
def crear_embeddings(simulado: bool):
    if simulado:
        from langchain_core.embeddings import DeterministicFakeEmbedding
        return DeterministicFakeEmbedding(size=768)
    return None  # rag_indexer usa gemini-embedding-001 por defecto


def crear_modelo(simulado: bool):
    if simulado:
        from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
        respuesta = AIMessage(
            content="[SIMULADO] Para deshacer un commit que ya compartiste usa git revert, que crea un "
                    "commit nuevo que invierte los cambios sin reescribir el historial [1].",
            usage_metadata={"input_tokens": 420, "output_tokens": 35, "total_tokens": 455},
        )
        return GenericFakeChatModel(messages=itertools.repeat(respuesta))
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(model=MODELO)


# ---------------------------------------------------------------------------
# Índice persistido (Bloque 25)
# ---------------------------------------------------------------------------
def cargar_corpus() -> list[Document]:
    """Un Document por archivo, con "fuente" = nombre del archivo (es lo que se cita)."""
    return [
        Document(page_content=ruta.read_text(encoding="utf-8"), metadata={"fuente": ruta.name})
        for ruta in CORPUS
    ]


def cargar_indice(simulado: bool = False, reindexar: bool = False, directorio: Path | None = None):
    """Abre el índice persistido; solo indexa si está vacío o si se pide --reindexar.
    Los ids fijos (<archivo>_<n>) hacen que reindexar REEMPLACE chunks en vez de duplicarlos."""
    directorio = directorio or (INDICE_SIMULADO if simulado else INDICE_REAL)
    embeddings = crear_embeddings(simulado)
    vectorstore = cargar_vectorstore(str(directorio), embeddings=embeddings)
    n_chunks = vectorstore._collection.count()
    if n_chunks and not reindexar:
        return vectorstore, "indice_reutilizado", n_chunks
    inicio = time.perf_counter()
    vectorstore = indexar_corpus(cargar_corpus(), str(directorio), es_documento=True, embeddings=embeddings)
    logger.info("indice actualizado", extra={"extra_data": {
        "evento": "indice_actualizado",
        "n_chunks": vectorstore._collection.count(),
        "indexacion_ms": round((time.perf_counter() - inicio) * 1000, 1),
        "simulado": simulado,
    }})
    return vectorstore, ("indice_reindexado" if n_chunks else "indice_creado"), vectorstore._collection.count()


# ---------------------------------------------------------------------------
# Consulta de punta a punta
# ---------------------------------------------------------------------------
def fuentes_citadas(texto: str, citas: dict) -> list[str]:
    """Traduce las citas [n] de la respuesta al archivo fuente. Si el modelo no citó ningún
    número válido, devuelve todas las fuentes del contexto que se le entregó."""
    numeros = {int(n) for grupo in re.findall(r"\[(\d+(?:\s*,\s*\d+)*)\]", texto)
               for n in re.split(r"\s*,\s*", grupo)} & set(citas)
    return sorted({citas[n] for n in (numeros or citas)})


def responder(pregunta: str, vectorstore, modelo, estado_indice: str = "", simulado: bool = False) -> dict:
    """Recupera, filtra, genera, cita y registra. Nunca deja escapar una excepción:
    si algo falla, se registra el tipo de error (sin contenido) y se devuelve un mensaje claro."""
    token = trace_id_var.set(f"trace-{uuid.uuid4().hex[:8]}")
    trace_id = trace_id_var.get()
    tiempos = {}
    try:
        config = {"callbacks": [HandlerDeTrazabilidad()], "metadata": {"trace_id": trace_id}}
        if estado_indice:
            logger.info(estado_indice, extra={"extra_data": {"evento": estado_indice}})

        inicio = time.perf_counter()
        documentos = vectorstore.as_retriever(search_kwargs={"k": K}).invoke(pregunta, config=config)
        tiempos["recuperacion_ms"] = round((time.perf_counter() - inicio) * 1000, 1)

        inicio = time.perf_counter()
        resultado = procesar_consulta(pregunta, documentos, modelo, config)
        tiempos["generacion_ms"] = round((time.perf_counter() - inicio) * 1000, 1)

        if resultado["bloqueada"]:
            texto, fuentes = CONSULTA_BLOQUEADA, []
        elif resultado["respuesta"] is None:
            texto, fuentes = SIN_CONTEXTO, []
        else:
            fuentes = fuentes_citadas(resultado["respuesta"], resultado["citas"])
            texto = resultado["respuesta"].strip() + "\n\nFuentes: " + ", ".join(fuentes)

        consumo = resultado.get("consumo") or {}
        costo = None
        if consumo.get("input_tokens") is not None:
            precio_entrada, precio_salida = obtener_precios(MODELO)
            costo = calcular_costo(consumo["input_tokens"], consumo.get("output_tokens") or 0,
                                   precio_entrada, precio_salida)
        logger.info("latencia y costo", extra={"extra_data": {
            "evento": "latencia_costo",
            **tiempos,
            "total_ms": round(sum(tiempos.values()), 1),
            "costo_estimado_usd": costo,
            "simulado": simulado,
        }})
        return {"trace_id": trace_id, "respuesta": texto, "fuentes": fuentes,
                "n_descartados": len(resultado["descartados"]), "costo_estimado_usd": costo,
                "latencia_ms": tiempos, "simulado": simulado}
    except Exception as error:
        logger.error("error del servicio", extra={"extra_data": {
            "evento": "error_servicio", "tipo_error": type(error).__name__,
        }})
        return {"trace_id": trace_id, "respuesta": ERROR_SERVICIO, "fuentes": [], "error": type(error).__name__,
                "simulado": simulado}
    finally:
        trace_id_var.reset(token)


# ---------------------------------------------------------------------------
# Punto de supervisión humana (Bloque 32)
# ---------------------------------------------------------------------------
def supervisar_despliegue(decision: bool | None = None, thread_id: str | None = None) -> dict:
    """Propone activar la versión nueva del prompt y PAUSA hasta que una persona decida.
    decision=None -> se pregunta por consola; sin terminal interactiva se rechaza por seguridad."""
    config = {"configurable": {"thread_id": thread_id or f"despliegue-{uuid.uuid4().hex[:8]}"}}
    pausado = app_despliegue.invoke({"huella_nueva": HUELLA_NUEVA, "aprobado": False}, config=config)
    pendiente = pausado["__interrupt__"][0].value
    print("pausado, pendiente de aprobacion:", pendiente)

    if decision is None:
        if sys.stdin.isatty():
            decision = input("¿Aprobar el despliegue? [s/N]: ").strip().lower() in ("s", "si", "sí")
        else:
            print("sin terminal interactiva: se rechaza por defecto (usa --aprobar para aprobar)")
            decision = False
    return app_despliegue.invoke(Command(resume=decision), config=config)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Servicio RAG del Gate 2 (guía de Git/GitHub)")
    parser.add_argument("pregunta", nargs="?", default=PREGUNTA_EJEMPLO)
    parser.add_argument("--simulado", action="store_true", help="embeddings y modelo simulados, sin API")
    parser.add_argument("--reindexar", action="store_true", help="vuelve a indexar el corpus (upsert por id)")
    decision = parser.add_mutually_exclusive_group()
    decision.add_argument("--aprobar", dest="decision", action="store_const", const=True)
    decision.add_argument("--rechazar", dest="decision", action="store_const", const=False)
    args = parser.parse_args(argv)

    if not args.simulado and not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
        print("Falta GEMINI_API_KEY en el archivo .env (o usa --simulado para probar sin API).")
        return 1

    try:
        vectorstore, estado_indice, n_chunks = cargar_indice(args.simulado, args.reindexar)
    except Exception as error:
        print(f"No se pudo abrir ni crear el indice: {type(error).__name__}: {error}")
        return 1
    modo = "SIMULADO (sin API)" if args.simulado else f"real ({MODELO})"
    print(f"--- indice: {estado_indice}, {n_chunks} chunks | modo: {modo} ---")

    resultado = responder(args.pregunta, vectorstore, crear_modelo(args.simulado), estado_indice, args.simulado)
    print("--- respuesta del servicio ---")
    print(resultado["respuesta"])
    print(f"trace_id: {resultado['trace_id']} | costo: {resultado.get('costo_estimado_usd')} USD"
          f" | latencia: {resultado.get('latencia_ms')}")

    print("--- punto de supervision humana ---")
    final = supervisar_despliegue(args.decision)
    print("estado final:", final)

    if "error" in resultado:
        return 1
    print("Proceso terminado sin errores.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
