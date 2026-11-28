"""
Bloque 32 - Paso 1: registro de versiones del prompt de sistema del RAG de Git/GitHub.

Reutiliza RegistroDePrompts y diff_prompts de versionando_prompt_langgraph.py (lección del
Bloque 32) con los dos prompts REALES que tuvo el proyecto:
  v1 -> el de la cadena RAG original con trazabilidad (log_rag.py)
  v2 -> el actual, con la instrucción anti-inyección del Bloque 31 (prevencion_prompt_inyection.py)

Ejecutar desde la raíz del proyecto:  python src/Gate2/registro_prompts.py
La huella que imprime "ultima" es la que se copia en grafo_supervision.py (Paso 2).
"""
from versionando_prompt_langgraph import RegistroDePrompts, diff_prompts
from prevencion_prompt_inyection import PROMPT_SYSTEM

NOMBRE_PROMPT = "prompt_sistema_rag_git"
AUTOR = "Francisco Correa"

# Snapshot del texto tal como estaba en log_rag.py (construir_cadena). Se copia literal a
# propósito: una versión registrada es histórica y no debe cambiar si el código cambia.
PROMPT_V1 = (
    "Eres un asistente experto en Git y GitHub. Responde usando solo el contexto. "
    "Cita la fuente de cada afirmacion con su numero entre corchetes, como [1]. "
    "Si el contexto no alcanza para responder, dilo explicitamente en vez de inventar."
)

registro = RegistroDePrompts()
registro.registrar(
    NOMBRE_PROMPT, PROMPT_V1, AUTOR,
    "version original de la cadena RAG con trazabilidad (log_rag.py)",
)
registro.registrar(
    NOMBRE_PROMPT, PROMPT_SYSTEM, AUTOR,
    "delimita el contexto con <contexto> y agrega instruccion anti-inyeccion (Bloque 31)",
)

if __name__ == "__main__":
    for v in registro.versiones:
        print(v["huella"], "-", v["fecha"], "-", v["nota"])

    ultima = registro.ultima(NOMBRE_PROMPT)
    print("ultima:", ultima["huella"])

    v1, v2 = registro.versiones
    assert v1["huella"] != v2["huella"], "dos versiones distintas deben tener huellas distintas"
    assert ultima["huella"] == v2["huella"], "ultima() debe devolver la version mas reciente"

    print("\nDiff entre versiones:")
    for linea in diff_prompts(v1["texto"], v2["texto"]):
        print(linea)
