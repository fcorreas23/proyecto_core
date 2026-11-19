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
    huerfanos = [
        i for i, chunk in enumerate(chunks)
        if not any(chunk.page_content in texto for texto in corpus)
    ]
    if huerfanos:
        raise ValueError(f"Chunks que no provienen del corpus en los índices: {huerfanos}")

    print(f"Integridad OK | Chunks: {len(chunks)}")

def indexar_corpus(corpus, persist_directory, chunk_size = 200, chunk_overlap = 30):
    #Dividir en fragmentos mas pequeños
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
    chunks = splitter.create_documents(corpus)

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
    agregar_documento(vector_store, "Nuevo documento de prueba", "test")

    datos = vector_store._collection.get()
    print("Datos en el vector store:", datos["ids"])
    print("Cantidad de chunks en el vector store:", vector_store._collection.count())