from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document


load_dotenv()

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

def indexar_corpus(corpus, persist_directory, chunk_size = 200, chunk_overlap = 30, es_documento=False):
    #Dividir en fragmentos mas pequeños
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )

    if not es_documento:
        chunks = splitter.create_documents(corpus)
    else:
        chunks = splitter.split_documents(corpus)
        

    # Auditar antes de crear embeddings: si algo falla, se detiene aquí
    # sin gastar tokens.
    verificar_integridad(chunks, corpus)

    #Embedding
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")

    #Inicializando el vector store
    vector_store = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=persist_directory
    )
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

def formatear_resultados(resultados):
    lineas = []
    citas = {}

    for i, doc in enumerate(resultados, start=1):
        fuente = doc.metadata.get("fuente", "desconocida")
        lineas.append(f"[{i}] {doc.page_content}")
        citas[i] = fuente

    contexto = "\n\n".join(lineas)
    return contexto, citas


if __name__ == "__main__":
    corpus = [
        "Los pedidos se pueden cancelar dentro de las primeras 24 horas despues de "
        "realizados, sin costo adicional.",
        "Las devoluciones se aceptan hasta 30 dias despues de la entrega, siempre que "
        "el producto este sin usar.",
        "El reembolso se procesa en un plazo de 5 a 10 dias habiles despues de recibir "
        "el producto devuelto.",
        "Los productos en oferta o liquidacion no tienen devolucion, salvo defecto de "
        "fabrica.",
        "El envio de una devolucion corre por cuenta del cliente, excepto cuando el "
        "producto llego danado.",
    ]

    persist_directory = "vectorstore/"
    #indexar_corpus(corpus, persist_directory)
    vector_store = cargar_vectorstore(persist_directory)
    #agregar_documento(vector_store, "Nuevo documento de prueba", "test")

    #datos = vector_store._collection.get()
    #print("Datos en el vector store:", datos["ids"])
    #print("Cantidad de chunks en el vector store:", vector_store._collection.count())

    #pregunta = "¿Cuánto tiempo tengo para cancelar un pedido?"
    #busqueda_semantica(vector_store, pregunta)

    #retriever = vector_store.as_retriever(search_kwargs={"k": 2})

    #resultados_retriever = retriever.invoke(pregunta)
    #print("Resultados del retriever:", resultados_retriever)

    #Instalación adicional si queremos leer pdf, docs, etc
    with open("Guia_Git_GitHub_3_Usuarios.md", "r", encoding="utf-8") as f: #r: read, a: append, w: write
        contenido = f.read()

    documentos = [Document(page_content=contenido, metadata={"fuente": "Guia_Git_GitHub_3_Usuarios.md", "fecha": "2026-11-13"})]

    indexar_corpus(documentos, persist_directory, es_documento=True)

    datos = vector_store._collection.get()
    print("Datos en el vector store:", datos["ids"])
    print("Cantidad de chunks en el vector store:", vector_store._collection.count())
    print("Chunks: ", datos["documents"])