"""
La huella viene del Paso 1 (python src/Gate2/registro_prompts.py) y se escribe como texto,
para que este paso sea independiente del anterior.

Ejecutar desde la raíz del proyecto:  python src/Gate2/grafo_supervision.py
"""
from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

HUELLA_ACTIVA = "acfac0e1f779"   # v1: prompt original de la cadena RAG (log_rag.py)
HUELLA_NUEVA = "87b6ec1a4f9c"    # v2: prompt con instrucción anti-inyección (Bloque 31)


class EstadoDespliegue(TypedDict):
    huella_nueva: str
    aprobado: bool


def proponer(estado: EstadoDespliegue):
    # Registra la intención de despliegue ANTES de pedir la aprobación
    print("propuesta: reemplazar", HUELLA_ACTIVA, "por", estado["huella_nueva"])
    return {}


def supervisar(estado: EstadoDespliegue):
    # interrupt() congela el grafo y guarda el estado en el checkpointer hasta recibir
    # Command(resume=True/False) con el mismo thread_id
    decision = interrupt({
        "motivo": "aprobar nueva version del prompt de sistema del RAG en produccion",
        "huella_actual": HUELLA_ACTIVA,
        "huella_propuesta": estado["huella_nueva"],
    })
    return {"aprobado": decision}


def aplicar(estado: EstadoDespliegue):
    if estado["aprobado"]:
        print("version", estado["huella_nueva"], "activada")
    else:
        print("version", estado["huella_nueva"], "rechazada, se mantiene la anterior", HUELLA_ACTIVA)
    return {}


grafo = StateGraph(EstadoDespliegue)
grafo.add_node("proponer", proponer)
grafo.add_node("supervisar", supervisar)
grafo.add_node("aplicar", aplicar)
grafo.add_edge(START, "proponer")
grafo.add_edge("proponer", "supervisar")
grafo.add_edge("supervisar", "aplicar")
grafo.add_edge("aplicar", END)
app_despliegue = grafo.compile(checkpointer=InMemorySaver())


if __name__ == "__main__":
    print("=== Camino de aprobación (thread despliegue-prompt-1) ===")
    config = {"configurable": {"thread_id": "despliegue-prompt-1"}}
    resultado = app_despliegue.invoke({"huella_nueva": HUELLA_NUEVA, "aprobado": False}, config=config)
    print("1) tras invocar:", resultado)
    assert "__interrupt__" in resultado, "el grafo debe quedar detenido esperando aprobación"
    print("2) pendiente:", app_despliegue.get_state(config).interrupts[0].value)

    resultado = app_despliegue.invoke(Command(resume=True), config=config)
    print("3) tras aprobar:", resultado)
    assert "__interrupt__" not in resultado and resultado["aprobado"] is True

    print("\n=== Camino de rechazo (thread nuevo: despliegue-prompt-2) ===")
    config2 = {"configurable": {"thread_id": "despliegue-prompt-2"}}
    resultado = app_despliegue.invoke({"huella_nueva": HUELLA_NUEVA, "aprobado": False}, config=config2)
    assert "__interrupt__" in resultado
    resultado = app_despliegue.invoke(Command(resume=False), config=config2)
    print("4) tras rechazar:", resultado)
    assert resultado["aprobado"] is False
