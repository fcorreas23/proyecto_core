from pathlib import Path
import contextvars
import hashlib
import json
import logging
from logging.handlers import RotatingFileHandler
import sys
import uuid

from dotenv import load_dotenv
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnableParallel, RunnablePassthrough
from langchain_google_genai import ChatGoogleGenerativeAI

from rag_indexer import cargar_vectorstore, formatear_contexto

load_dotenv()

MODELO = "gemini-3.5-flash-lite"
ARCHIVO_LOGS = Path(__file__).resolve().parents[2] / "docs" / "rag_logs.jsonl"

"""
Contextvars: crea una variable de contexto.
Parecido a una variable global con la diferencia principal
que aisla el valor de cada hilo/tarea asincrónica
"""
trace_id_var = contextvars.ContextVar("trace_id", default=None)

#Transforma el evento de log en un objeto de JSON de una sola línea
class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "msg": record.getMessage(),
            "trace_id": trace_id_var.get(), #extrae de manera automática con el hilo/tarea activo
        }
        #Si se envía info adicional (extra_data) la agregamos
        #El tamaño del query, cuantos docs, cantidad de prompt, respuesta, chars respuesta
        if hasattr(record, "extra_data"):
            payload.update(record.extra_data)
        return json.dumps(payload, ensure_ascii=False)

#Configuración de mi logger
logger = logging.getLogger("rag_pipeline")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout) #Imprima los eventos que se están registrando
handler.setFormatter(JsonFormatter()) #Establezco el formato
archivo_handler = RotatingFileHandler(
    ARCHIVO_LOGS,
    maxBytes=1_000_000, #Al llegar a ~1 MB rota el archivo
    backupCount=3,      #Guarda rag_logs.jsonl.1, .2 y .3; el más viejo se descarta
    encoding="utf-8",
)
archivo_handler.setFormatter(JsonFormatter())
logger.handlers = [handler, archivo_handler]
logger.propagate = False #Evita que los logs se dupliquen en el logger raíz

#No queremos guardar la información en crudo, sino que buscamos "esconderla"
#Genera una huella (hash sha 256 truncado) para poder detectar duplicados o cambios en mis documentos
def generar_huella(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:12]


#FUNCIONAMIENTO: BaseCallbackHandler -> cuando la cadena comience, cuando retriever comience, cuando retr termine, cuando el modelo comience, cuando el modelo termine
#Heredo de BaseCallbackHandler, ya tiene definidos mis métodos que detectan una acción/evento de Langchain y sobreescribimos esos eventos para registrar el log de lo que está sucediendo
class HandlerDeTrazabilidad(BaseCallbackHandler):
    #CICLO DE VIDA: cadena principal
    def on_chain_start(self, serialized, inputs, *, run_id, parent_run_id=None, **kwargs):
        if parent_run_id is None: #Es la cadena principal
            logger.info("inicio_cadena", extra={"extra_data": {"root_run_id": str(run_id)}})

    def on_chain_end(self, outputs, *, run_id, parent_run_id=None, **kwargs):
        if parent_run_id is None:
            logger.info("fin_cadena", extra={"extra_data": {"root_run_id": str(run_id)}})

    def on_chain_error(self, error, *, run_id, parent_run_id=None, **kwargs):
        if parent_run_id is None:
            logger.error(
                "error_cadena",
                extra={"extra_data": {"root_run_id": str(run_id), "error": repr(error)}},
            )

    #CICLO DE VIDA: retriever
    #on_retriever_start: Se dispara ANTES de que el retriever haga la búsqueda vectorial
    def on_retriever_start(self, serialized, query, *, run_id, parent_run_id=None, metadata=None, **kwargs):
        #query: el texto exacto con el que se está haciendo la búsqueda semántica
        #metadata: diccionario que pasamos en config
        logger.info(
            "retriever_start",
            extra={
                "extra_data": {
                    "run_id": str(run_id),
                    "parent_run_id": str(parent_run_id),
                    "query_len": len(query),
                    "query_hash": generar_huella(query),
                    "meta_trace": (metadata or {}).get("trace_id"),
                }
            },
        )

    #on_retriever_end: Se dispara INMEDIATAMENTE DESPUES de recibir los chunks
    def on_retriever_end(self, documents, *, run_id, parent_run_id=None, **kwargs):
        #documents: la lista de objetos Document que recuperamos de la base vectorial. CHUNKS
        logger.info(
            "retriever_end",
            extra={
                "extra_data": {
                    "run_id": str(run_id), #Mismo run_id que retriever_start: permite emparejarlos
                    "n_documents": len(documents),
                    "huellas_docs": [generar_huella(d.page_content) for d in documents],
                    #El nombre del archivo no es sensible y ayuda a saber de dónde salió cada chunk
                    "fuentes": [d.metadata.get("fuente", "desconocida") for d in documents],
                }
            },
        )

    def on_retriever_error(self, error, *, run_id, parent_run_id=None, **kwargs):
        logger.error("retriever_error", extra={"extra_data": {"run_id": str(run_id), "error": repr(error)}})

    #CICLO DE VIDA DE MODELO
    #on_chat_model_start: dispara ANTES de enviar los mensajes (System + Human)
    def on_chat_model_start(self, serialized, messages, *, run_id, parent_run_id=None, **kwargs):
        #messages: lista de conversaciones; cada una es una lista de mensajes (System, Human)
        logger.info(
            "llm_start",
            extra={
                "extra_data": {
                    "run_id": str(run_id),
                    "parent_run_id": str(parent_run_id),
                    "modelo": (kwargs.get("invocation_params") or {}).get("model"),
                    "n_mensajes": sum(len(conversacion) for conversacion in messages),
                }
            },
        )

    #on_llm_end: dispara cuando TERMINA el modelo de generar la respuesta
    def on_llm_end(self, response, *, run_id, parent_run_id=None, **kwargs):
        #response: Respuesta/texto generado de mi API
        texto_salida = response.generations[0][0].text #Navegar a la estructura interna para sacar el texto generado
        logger.info(
            "llm_end",
            extra={
                "extra_data": {
                    "run_id": str(run_id),
                    "chars_respuesta": len(texto_salida),
                    "respuesta_hash": generar_huella(texto_salida),
                }
            },
        )

    def on_llm_error(self, error, *, run_id, parent_run_id=None, **kwargs):
        logger.error("llm_error", extra={"extra_data": {"run_id": str(run_id), "error": repr(error)}})


def construir_cadena(vectorstore, k: int = 3):
    """
    1.- En paralelo: busca los chunks en el vectorstore y pasa la pregunta original INTACTA
    2.- Formatea los chunks como contexto numerado [1], [2], ... y lo inyecta al prompt
    3.- Mando el prompt al modelo
    4.- Parseo el texto
    Se conservan los chunks en la salida ("docs") para poder devolver las citas.
    """
    retriever = vectorstore.as_retriever(search_kwargs={"k": k})
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Eres un asistente experto en Git y GitHub. Responde usando solo el contexto. "
                   "Cita la fuente de cada afirmacion con su numero entre corchetes, como [1]. "
                   "Si el contexto no alcanza para responder, dilo explicitamente en vez de inventar."),
        ("human", "Contexto:\n{contexto}\n\nPregunta: {pregunta}"),
    ])
    modelo = ChatGoogleGenerativeAI(model=MODELO)

    preparar_prompt = RunnableLambda(
        lambda x: {"contexto": formatear_contexto(x["docs"])[0], "pregunta": x["pregunta"]}
    )

    return RunnableParallel(
        docs=retriever,
        pregunta=RunnablePassthrough(),
    ).assign(respuesta=preparar_prompt | prompt | modelo | StrOutputParser())


def ejecutar_consulta(vectorstore, pregunta: str, k: int = 3):
    """Ejecuta la consulta con trazabilidad. Devuelve (respuesta, citas)."""
    token = trace_id_var.set(f"trace-{uuid.uuid4().hex[:8]}")
    try:
        cadena = construir_cadena(vectorstore, k)
        handler = HandlerDeTrazabilidad() #Invoco a la cadena, PASANDOLE el handler. Detectar los eventos mientras se ejecuta la cadena
        resultado = cadena.invoke(
            pregunta,
            config={
                "callbacks": [handler],
                "metadata": {"trace_id": trace_id_var.get()},
            },
        )
        _, citas = formatear_contexto(resultado["docs"])
        return resultado["respuesta"], citas
    finally:
        trace_id_var.reset(token) #BORRO el trace_id para futuras consultas


if __name__ == "__main__":
    # Ejecutar desde la raíz del proyecto:  python src/Gate2/logging_rag.py
    CARPETA_DB = "vectorstore"
    K = 3
    vs = cargar_vectorstore(CARPETA_DB)

    if vs._collection.count() == 0:
        raise SystemExit(f"'{CARPETA_DB}' está vacío. Corre primero: python src/Gate2/rag_indexer.py")

    # Preguntas sobre Guia_Git_GitHub_3_Usuarios.md.
    # Cada una gasta 1 embedding + 1 llamada al modelo.
    preguntas = [
        "¿Cómo se resuelve un conflicto de merge?",
        "¿Cómo se crea una nueva rama en Git?",
        "¿Cómo se hace un merge en Git?",
    ]

    for pregunta in preguntas:
        respuesta, citas = ejecutar_consulta(vs, pregunta, K)
        print(f"\nPregunta: {pregunta}\nRespuesta:\n{respuesta}\nCitas: {citas}\n")
