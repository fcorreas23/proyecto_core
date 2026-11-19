"""
Recuperación semántica + prompt dinámico con citas.

Sobre el índice creado por rag_indexer.py (vectorstore/):
1. Recupera los k chunks más relevantes para una pregunta.
2. Arma un prompt numerado que obliga al modelo a citar sus fuentes [N].
3. Guarda un mapa número -> archivo (citas) para reconstruir la cita después.

Ejecutar desde la raíz del proyecto:  python src/recuperacion.py
"""
import re

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

load_dotenv()

MODELO = "gemini-3.6-flash"

PROMPT_TEMPLATE = """Responde la pregunta usando SOLO el contexto de abajo. Cita la \
fuente de cada afirmacion con su numero entre corchetes, como [1]. Si el contexto no \
alcanza para responder, dilo explicitamente en vez de inventar.

Contexto:
{contexto}

Pregunta: {pregunta}

Respuesta:"""


def formatear_contexto(chunks_recuperados):
    """Arma un bloque de contexto numerado para el prompt, y un mapa
    numero -> fuente para reconstruir la cita despues."""
    lineas = []
    citas = {}
    for i, doc in enumerate(chunks_recuperados, start=1):
        # Si el chunk se indexó sin metadata, aparece "desconocida".
        fuente = doc.metadata.get("fuente", "desconocida")
        lineas.append(f"[{i}] {doc.page_content}")
        citas[i] = fuente
    contexto = "\n\n".join(lineas)
    return contexto, citas


def construir_prompt(pregunta, persist_directory, k=3):
    """Recupera los k chunks mas relevantes para la pregunta y arma
    el prompt dinamico con contexto numerado, listo para pasarle al modelo."""
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
    vectorstore = Chroma(
        persist_directory=persist_directory,
        embedding_function=embeddings
    )
    retriever = vectorstore.as_retriever(search_kwargs={"k": k})

    # La pregunta se convierte en embedding (llamada real a la API) y se
    # buscan los k chunks más cercanos por significado.
    chunks_recuperados = retriever.invoke(pregunta)
    contexto, citas = formatear_contexto(chunks_recuperados)
    prompt = PROMPT_TEMPLATE.format(contexto=contexto, pregunta=pregunta)
    return prompt, citas, chunks_recuperados


def verificar_prompt(prompt, citas, pregunta, k):
    """Comprueba las 4 condiciones que la actividad exige siempre."""
    # 1. citas tiene exactamente k entradas, con claves 1..k
    assert list(citas.keys()) == list(range(1, k + 1)), f"Claves de citas inesperadas: {list(citas)}"

    # 2. Ninguna fuente "desconocida" (si aparece, faltó metadata al indexar)
    assert "desconocida" not in citas.values(), "Hay chunks sin metadata 'fuente': reindexa"

    # 3. La pregunta aparece exacta, sin recortar, en la línea "Pregunta: ..."
    assert f"\nPregunta: {pregunta}\n" in prompt, "La pregunta no aparece exacta en el prompt"

    # 4. Bloques [N] numerados desde 1, consecutivos, uno por chunk.
    #    Solo miramos la sección de contexto, para no confundir otros corchetes.
    contexto = prompt.split("Contexto:\n", 1)[1].split("\n\nPregunta: ", 1)[0]
    numeros = [int(n) for n in re.findall(r"^\[(\d+)\] ", contexto, flags=re.M)]
    assert numeros == list(range(1, len(citas) + 1)), f"Numeración del contexto incorrecta: {numeros}"


def responder(prompt):
    """Envía el prompt al modelo y devuelve el texto de la respuesta."""
    # gemini-3.6-flash usa parámetros de muestreo fijos: temperature se ignora.
    modelo = ChatGoogleGenerativeAI(model=MODELO)
    return modelo.invoke(prompt).text


if __name__ == "__main__":
    persist_directory = "vectorstore/"
    k = 3

    # Dos preguntas que el corpus SÍ responde (deben traer chunks distintos)
    # y una que NO responde (el modelo debe decir que no tiene información).
    preguntas = [
        "¿Cómo se resuelve un conflicto de merge?",
        "¿Qué diferencia hay entre git reset y git revert?",
        "¿Cuánto cuesta una licencia de GitHub Enterprise?",
    ]

    ids_por_pregunta = {}
    for pregunta in preguntas:
        prompt, citas, chunks = construir_prompt(pregunta, persist_directory, k=k)
        verificar_prompt(prompt, citas, pregunta, k)

        ids_por_pregunta[pregunta] = [doc.id for doc in chunks]

        print("=" * 80)
        print(prompt)
        print("\nCitas:", citas)
        print("Ids recuperados:", ids_por_pregunta[pregunta])
        print("\nRespuesta del modelo:\n" + responder(prompt))

    # Escenario 1: la recuperación debe cambiar según la pregunta.
    print("=" * 80)
    conjuntos = [tuple(ids) for ids in ids_por_pregunta.values()]
    if len(set(conjuntos)) == len(conjuntos):
        print("OK: cada pregunta recuperó chunks distintos (recuperación semántica).")
    else:
        print("ATENCIÓN: hay preguntas que recuperaron exactamente los mismos chunks.")

    # Ejemplo de cómo luce el diccionario citas.
    chunks_ejemplo = [
        Document(
            page_content="El cliente reintenta hasta 3 veces ante un TimeoutError.",
            metadata={"fuente": "doc0.md"},
        ),
        Document(
            page_content="El costo de cada llamada se calcula a partir de totalTokenCount.",
            metadata={"fuente": "doc2.md"},
        ),
    ]
    contexto_ejemplo, citas_ejemplo = formatear_contexto(chunks_ejemplo)
    print(citas_ejemplo)
