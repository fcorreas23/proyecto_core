import shutil
import time
from pathlib import Path

from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document


load_dotenv()

# Límite del plan gratuito: 100 embeddings por minuto.
TAMANO_LOTE = 90
ESPERA_ENTRE_LOTES = 61  # segundos
MAX_REINTENTOS = 4       # intentos por lote si la API responde 429

def verificar_integridad(chunks, corpus):
    """
    Auditar localmente los chunks antes de gastar tokens en embeddings.
    - Chunks vacíos      -> error (detiene la ejecución)
    - Chunks duplicados  -> advertencia
    - Chunks que no salen del corpus -> error
    """
    # 1. Chunks vacíos
    # Guardamos el ÍNDICE de cada chunk que queda vacío tras quitar espacios/saltos,
    vacios = [i for i, chunk in enumerate(chunks) if not chunk.page_content.strip()]
    if vacios:
        # raise detiene todo: no se llega a llamar a la API de embeddings.
        raise ValueError(f"Se detectaron chunks vacíos en los índices: {vacios}")

    # 2. Chunks duplicados
    contenidos = [chunk.page_content for chunk in chunks]
    if len(contenidos) != len(set(contenidos)):
        cantidad = len(contenidos) - len(set(contenidos))
        print(f"Advertencia: {cantidad} chunk(s) duplicado(s).")

    # 3. Origen de cada chunk
    # El corpus puede venir como lista de strings o como lista de Document
    # (cuando es_documento=True). Sacamos el texto plano de cada uno para
    # poder buscar el chunk dentro; si no, "in" se compararía contra el
    # objeto Document y nunca encontraría nada.
    textos_corpus = [
        texto.page_content if isinstance(texto, Document) else texto
        for texto in corpus
    ]
    huerfanos = [
        i for i, chunk in enumerate(chunks)
        if not any(chunk.page_content in texto for texto in textos_corpus)
    ]
    if huerfanos:
        raise ValueError(f"Chunks que no provienen del corpus en los índices: {huerfanos}")

    print(f"Integridad OK | Chunks: {len(chunks)}")

def cargar_documentos(rutas):
    """Lee cada archivo y lo convierte en un Document con metadata "fuente".
    Esa clave es la que después usa formatear_contexto para armar las citas."""
    documentos = []
    for ruta in rutas:
        with open(ruta, "r", encoding="utf-8") as f:
            documentos.append(Document(page_content=f.read(), metadata={"fuente": ruta}))
    return documentos

def generar_ids(chunks):
    """IDs predecibles por chunk: <archivo_sin_extension>_<n>, donde n cuenta
    los chunks DE ESE archivo (guia_0, guia_1, ..., limites_metrica_0, ...).
    Se necesita uno por CHUNK, no por documento: un archivo largo se parte en
    muchos chunks y cada uno necesita su propio id."""
    contadores = {}
    ids = []
    for chunk in chunks:
        base = Path(chunk.metadata.get("fuente", "chunk")).stem
        n = contadores.get(base, 0)
        ids.append(f"{base}_{n}")
        contadores[base] = n + 1
    return ids

def indexar_corpus(corpus, persist_directory, chunk_size = 200, chunk_overlap = 30, es_documento=False, metadatas=None):
    #Dividir en fragmentos mas pequeños
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )

    if not es_documento:
        # Lista de strings: la metadata se pasa aparte (una por texto).
        chunks = splitter.create_documents(corpus, metadatas=metadatas)
    else:
        # Lista de Document: split_documents copia la metadata de cada
        # Document (su "fuente") a todos los chunks que salen de él.
        chunks = splitter.split_documents(corpus)

    # Auditar antes de crear embeddings: si algo falla, se detiene aquí
    # sin gastar tokens.
    verificar_integridad(chunks, corpus)

    ids = generar_ids(chunks)

    #Embedding
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")

    #Inicializando el vector store (vacío) y agregando por lotes
    vector_store = Chroma(
        persist_directory=persist_directory,
        embedding_function=embeddings
    )

    # El plan gratuito de Gemini permite 100 embeddings por minuto. Con más
    # chunks que eso, from_documents falla con 429 RESOURCE_EXHAUSTED.
    # Por eso agregamos en lotes y esperamos un minuto entre lote y lote.
    for inicio in range(0, len(chunks), TAMANO_LOTE):
        if inicio > 0:
            print(f"Esperando {ESPERA_ENTRE_LOTES}s por el límite de la API...")
            time.sleep(ESPERA_ENTRE_LOTES)
        fin = inicio + TAMANO_LOTE

        # Reintentos: si la cuota del minuto ya estaba gastada (por ejemplo,
        # porque corriste otro script justo antes), la API responde 429.
        # En vez de caernos, esperamos y repetimos el MISMO lote.
        for intento in range(1, MAX_REINTENTOS + 1):
            try:
                # ids=: sin esto Chroma inventa UUIDs aleatorios. Con ids fijos,
                # repetir un lote reemplaza los chunks en vez de duplicarlos.
                vector_store.add_documents(documents=chunks[inicio:fin], ids=ids[inicio:fin])
                break
            except Exception as error:
                mensaje = str(error)
                # La cuota DIARIA (1000 embeddings/día) no se recupera esperando
                # un minuto: no tiene sentido reintentar, se corta aquí.
                if "per day" in mensaje:
                    raise RuntimeError(
                        "Se agotó la cuota DIARIA de embeddings del plan gratuito "
                        "(1000/día). Vuelve a intentarlo mañana o usa otra API key."
                    ) from error
                if "RESOURCE_EXHAUSTED" not in mensaje or intento == MAX_REINTENTOS:
                    raise  # otro tipo de error, o se acabaron los reintentos
                print(f"Cuota agotada (429). Reintento {intento}/{MAX_REINTENTOS - 1} en {ESPERA_ENTRE_LOTES}s...")
                time.sleep(ESPERA_ENTRE_LOTES)

        print(f"Indexados {min(fin, len(chunks))}/{len(chunks)} chunks")

    return vector_store

def cargar_vectorstore(persist_directory):
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
    return Chroma(persist_directory=persist_directory, embedding_function=embeddings)

def eliminar_vector_por_id(vector_store , vector_id):
    vector_store._collection.delete(ids=[vector_id])

def agregar_documento(vector_store, documento, prefijo_id, chunk_size = 200, chunk_overlap = 30):

    # create_documents espera una LISTA de textos. Si llega un string suelto,
    # lo recorrería letra por letra, así que lo envolvemos en una lista.
    if isinstance(documento, str):
        documento = [documento]

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
    chunks = splitter.create_documents(documento)

    # Misma auditoría antes de agregar al vector store.
    verificar_integridad(chunks, documento)

    # IDs reales para Chroma: "prefijo_0", "prefijo_1", ...
    # Antes se guardaban en chunk.metadata["id"], pero eso es solo un dato extra;
    # Chroma les asignaba un UUID aleatorio y eliminar_vector_por_id no los encontraba.
    ids = [f"{prefijo_id}_{i}" for i in range(len(chunks))]

    try:
        # Al pasar ids=, Chroma usa esos IDs. Si un ID ya existe, el chunk se
        # reemplaza en vez de duplicarse.
        vector_store.add_documents(documents=chunks, ids=ids)
        print(f"Agregados {len(chunks)} chunks con el prefijo {prefijo_id}")
    except Exception as error:
        print("Error al agregar el documento:", error)

    return ids

"""
Realiza la búsqueda semántica (por significado, NO POR PALABRA EXACTA) en el vector store.
Devuelve una lista con los resultados semejantes
"""
def busqueda_semantica(vector_store, query, top_k=2):
    results = vector_store.similarity_search(query, k=top_k)

    print(f"Resultados de la búsqueda semántica para la query '{query}':")
    for i, result in enumerate(results):
        print(f"{i+1}. {result.page_content}")
    return results

def formatear_contexto(resultados):
    lineas = []
    citas = {}

    for i, doc in enumerate(resultados, start=1):
        fuente = doc.metadata.get("fuente", "desconocida")
        lineas.append(f"[{i}] {doc.page_content}")
        citas[i] = fuente

    contexto = "\n\n".join(lineas)
    return contexto, citas

def inspeccionar_chunks(vector_store):
    # include debe pedir también "documents": si no, datos["documents"] es None
    # y el zip de abajo falla.
    datos = vector_store._collection.get(limit=3, include=["metadatas", "documents"])
    total = vector_store._collection.count()
    print("Inspección de chunks en el vector store (total:", total, "):")
    for i, (id, texto, metadata) in enumerate(zip(datos["ids"], datos["documents"], datos["metadatas"]), start=1):
        print(f"{i}. ID: {id}, Metadata: {metadata}")
        resumen = texto[:75] + "..." if len(texto) > 75 else texto
        print(f"   Texto: {resumen}")
    


if __name__ == "__main__":
    # Ejecutar desde la raíz del proyecto:  python src/rag_indexer.py
    persist_directory = "vectorstore/"

    # Corpus: cada archivo queda como "fuente" en la metadata de sus chunks.
    archivos_corpus = [
        "Guia_Git_GitHub_3_Usuarios.md",
    ]

    # Con ids fijos, volver a indexar REEMPLAZA los chunks existentes en vez
    # de duplicarlos. Descomenta esto solo si cambias el corpus o el
    # chunk_size y quieres borrar chunks viejos que ya no existen.
    # shutil.rmtree(persist_directory, ignore_errors=True)

    documentos = cargar_documentos(archivos_corpus)
    vector_store = indexar_corpus(documentos, persist_directory, es_documento=True)

    inspeccionar_chunks(vector_store)

    # -----------------------------------------------------------------------
    # Pruebas anteriores.
    # -----------------------------------------------------------------------

    # Corpus de ejemplo (políticas de pedidos), sin archivo de origen:
    # corpus = [
    #     "Los pedidos se pueden cancelar dentro de las primeras 24 horas despues de "
    #     "realizados, sin costo adicional.",
    #     "Las devoluciones se aceptan hasta 30 dias despues de la entrega, siempre que "
    #     "el producto este sin usar.",
    #     "El reembolso se procesa en un plazo de 5 a 10 dias habiles despues de recibir "
    #     "el producto devuelto.",
    #     "Los productos en oferta o liquidacion no tienen devolucion, salvo defecto de "
    #     "fabrica.",
    #     "El envio de una devolucion corre por cuenta del cliente, excepto cuando el "
    #     "producto llego danado.",
    # ]
    # indexar_corpus(corpus, persist_directory)

    # Cargar un índice ya existente (sin gastar embeddings) y agregar un documento:
    # vector_store = cargar_vectorstore(persist_directory)
    # agregar_documento(vector_store, "Nuevo documento de prueba", "test")

    # Ver ids y cantidad de chunks guardados:
    # datos = vector_store._collection.get()
    # print("Datos en el vector store:", datos["ids"])
    # print("Cantidad de chunks en el vector store:", vector_store._collection.count())

    # Búsqueda semántica y retriever:
    # pregunta = "¿Cómo se resuelve un conflicto de merge?"
    # busqueda_semantica(vector_store, pregunta)
    # retriever = vector_store.as_retriever(search_kwargs={"k": 3})
    # resultados_retriever = retriever.invoke(pregunta)
    # print("Resultados del retriever:", resultados_retriever)

    # Contexto numerado y citas:
    # contexto_ejemplo, citas_ejemplo = formatear_contexto(resultados_retriever)
    # print("Contexto formateado de ejemplo:\n", contexto_ejemplo)
    # print("Citas de ejemplo:", citas_ejemplo)
