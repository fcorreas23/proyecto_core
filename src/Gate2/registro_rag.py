from pathlib import Path
import time #Latencia
import json #Registrar en jsonl la info
from contextlib import contextmanager #administrador de contexto: ejecuta antes, durante y después de hacerse una acción
from datetime import datetime, timezone
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI #Modelo para instanciar gemini

from log_rag import generar_huella
from rag_indexer import cargar_vectorstore, formatear_contexto

load_dotenv()

# Precios POR TOKEN (USD) de cada modelo.
# Ej: 0.00000075 por token = 0.75 USD por millón de tokens.
MODELOS = [
    {
        "nombre": "gemini-3.8-flash",
        "precio_entrada": 0.00000075,
        "precio_salida": 0.00000375
    },
    {
        "nombre": "gemini-3.6-flash",
        "precio_entrada": 0.00000075,
        "precio_salida": 0.00000375
    },
    {
        "nombre": "gemini-3.5-flash-lite",
        "precio_entrada": 0.0000003,
        "precio_salida": 0.0000025
    },
    {
        "nombre": "gemini-3.1-flash-lite",
        "precio_entrada": 0.00000025,
        "precio_salida": 0.0000015
    }
]

MODELO_POR_DEFECTO = "gemini-3.5-flash-lite"

#Plantilla que me obligue a usar SOLO el contexto recuperado y también a citar [1], [2]
PROMPT_TEMPLATE = """Responde la pregunta usando SOLO el contexto de abajo. Cita la \
fuente de cada afirmacion con su numero entre corchetes, como [1]. Si el contexto no \
alcanza para responder, dilo explicitamente en vez de inventar.

Contexto:
{contexto}

Pregunta: {pregunta}

Respuesta:

""" #contexto = el resultado de la búsqueda de vs, formateado con formatear_contexto, pregunta = la consulta del usuario final

def aprox_tokens(texto: str) -> int:
    return len(texto) // 4

#Latencia
@contextmanager #Administrador de contexto
def medir(tiempos: dict, etapa: str):
    """
    Cronometrar bloques de código (sin "ensuciar" la lógica)
    Uso:
        with medir(tiempos, "nombre_etapa"): #ej: "embedding_y_consulta"
            #Codigo que quiero medir
            retriever = vs.as_retriever....
            chunks = ....
    """
    #1.- ANTES del bloque with
    inicio = time.perf_counter() #empiezo a contar el tiempo

    #2.- PAUSA (yield): le cede el control al código que puse en el bloque de código dentro del with
    yield

    #3.- DESPUÉS del bloque with: cuando el código termina, vuelvo aquí y detengo el tiempo
    tiempos[etapa] = time.perf_counter() - inicio #Tiempo total en el que se ejecutó esa etapa/tarea

def obtener_precios(nombre_modelo: str) -> tuple[float, float]:
    """Busca en MODELOS el precio por token de entrada y de salida del modelo."""
    for m in MODELOS:
        if m["nombre"] == nombre_modelo:
            return m["precio_entrada"], m["precio_salida"]
    raise ValueError(f"El modelo '{nombre_modelo}' no está en la lista MODELOS")

#Calculo de costos (tokens_entrada, tokens_salida, precio por token de entrada y salida)
def calcular_costo(tokens_entrada: int, tokens_salida: int, precio_entrada: float, precio_salida: float) -> float:
    """
    Calcula el costo monetario real de la consulta con contexto de mi RAG.
    Los precios son POR TOKEN (como en MODELOS), no por millón.
    """
    costo_entrada = tokens_entrada * precio_entrada
    costo_salida = tokens_salida * precio_salida

    return round(costo_entrada + costo_salida, 8)

#Registrar consulta
def registrar_consulta(vectorstore, pregunta: str, k: int = 3, modelo: str = MODELO_POR_DEFECTO) -> tuple[dict, str]:
    """
    Ejecutar de punta a punta el proceso completo con RAG. (Recuperación + Prompt con contexto + Generación con Gemini),
    Medir la latencia de cada etapa y extraer los tokens consumidos (reales) y el costo de esto
    Devuelve (registro, respuesta): el registro NO guarda el texto de la pregunta ni de la
    respuesta (solo longitud y huella, Bloque 31); el texto se devuelve aparte para mostrarlo.
    """
    tiempos = {} #Es donde voy a almacenar la latencia de cada etapa

    precio_entrada, precio_salida = obtener_precios(modelo) #falla antes de gastar tokens si el modelo no existe
    chat_model = ChatGoogleGenerativeAI(model=modelo)

    #Etapa 1: Embed de la pregunta (llamada a la API) + búsqueda vectorial en Chroma (local)
    with medir(tiempos, "embed_y_busqueda"):
        retriever = vectorstore.as_retriever(search_kwargs={"k": k})
        chunks = retriever.invoke(pregunta) #busqueda vectorial con Chroma

    #Etapa 2: Armado del prompt (agregando el contexto/chunks formateados) - Acción Local
    with medir(tiempos, "armado_prompt"):
        contexto, citas = formatear_contexto(chunks)
        prompt = PROMPT_TEMPLATE.format(contexto=contexto, pregunta=pregunta)

    #Etapa 3: Generación de la respuesta con Gemini
    with medir(tiempos, "generacion"):
        respuesta = chat_model.invoke(prompt)

    #respuesta tiene usage_metadata -> tokens se gastaron.
    #respuesta.usage_metadata["input_tokens"], respuesta.usage_metadata["output_tokens"]
    tokens_reales = dict(respuesta.usage_metadata) if respuesta.usage_metadata else None

    costo_usd = None

    if tokens_reales:
        costo_usd = calcular_costo(
            tokens_entrada = tokens_reales.get("input_tokens", 0),
            tokens_salida = tokens_reales.get("output_tokens", 0), #output_tokens YA INCLUYE tokens de razonamiento
            precio_entrada = precio_entrada,
            precio_salida = precio_salida
        )

    #Factor crecimiento: comparación de cuánto creció el texto de entrada vs la pregunta solita
    factor_crecimiento = round(len(prompt) / len(pregunta), 1)

    #Construir el diccionario con toda la info que obtuvimos
    registro = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "modelo": modelo,
        "pregunta_len": len(pregunta),
        "pregunta_hash": generar_huella(pregunta),
        "k": k,
        # .text en vez de .content: en los modelos Gemini 3 .content puede venir
        # como lista de bloques; .text siempre es el texto plano.
        "respuesta_len": len(respuesta.text),
        "respuesta_hash": generar_huella(respuesta.text),
        "citas_disponibles": citas,
        "ids_recuperados": [c.id for c in chunks], #ids predecibles: Guia_Git_GitHub_3_Usuarios_N
        "tiempo_ms": {etapa: round(seg * 1000, 2) for etapa, seg in tiempos.items()},
        "tiempo_total_ms": round(sum(tiempos.values()) * 1000, 2),
        "factor_crecimiento": f"{factor_crecimiento}x",
        "tokens": tokens_reales,
        # Si el modelo no devolvió usage_metadata, el costo queda en None
        # (antes f"{None:.6f}" hacía fallar el script).
        "costo_estimado_usd": None if costo_usd is None else f"{costo_usd:.8f}"
    }

    return registro, respuesta.text

def guardar_registro_jsonl(registro: dict, ruta_archivo=Path(__file__).resolve().parents[2] / "docs" / "registros_latencia_costo.jsonl"):
    """
    Guarda cada corrida/registro generado y lo agrega a un json
    """
    with open(ruta_archivo, "a", encoding="utf-8") as f: #agrego al final del archivo
        f.write(json.dumps(registro, ensure_ascii=False)+"\n")

    print(f"Registro guardado en {ruta_archivo}")

def imprimir_resumen(registro: dict, pregunta: str, respuesta: str):
    """Muestra lo más importante del registro en pocas líneas."""
    tokens = registro["tokens"] or {}
    print("=" * 80)
    print(f"Modelo:    {registro['modelo']}")
    print(f"Pregunta:  {pregunta}")
    print(f"Chunks:    {registro['ids_recuperados']}")
    print(f"Tiempos:   {registro['tiempo_ms']}  (total {registro['tiempo_total_ms']} ms)")
    print(f"Tokens:    entrada={tokens.get('input_tokens')}  salida={tokens.get('output_tokens')}  total={tokens.get('total_tokens')}")
    print(f"Costo:     {registro['costo_estimado_usd']} USD   |   Factor crecimiento: {registro['factor_crecimiento']}")
    print(f"Respuesta: {respuesta}")

if __name__ == "__main__":
    # Ejecutar desde la raíz del proyecto:  python src/Gate2/registro_rag.py
    CARPETA_DB = "vectorstore/"
    K = 3
    vs = cargar_vectorstore(CARPETA_DB)

    if vs._collection.count() == 0:
        raise SystemExit(f"'{CARPETA_DB}' está vacío. Corre primero: python src/Gate2/rag_indexer.py")

    # Preguntas sobre Guia_Git_GitHub_3_Usuarios.md.
    # Cada una gasta 1 embedding + 1 llamada al modelo.
    preguntas = [
        "¿Cómo se resuelve un conflicto de merge?",
        "¿Cómo deshago un commit que ya compartí con mi equipo?",
    ]

    for pregunta in preguntas:
        registro, respuesta = registrar_consulta(vs, pregunta, K, modelo=MODELO_POR_DEFECTO)
        imprimir_resumen(registro, pregunta, respuesta)
        guardar_registro_jsonl(registro)

    # Comparar costo y latencia de la MISMA pregunta con todos los modelos.
    # Descomenta para usarlo (gasta 1 embedding + 1 llamada por modelo):
    # for m in MODELOS:
    #     registro, respuesta = registrar_consulta(vs, preguntas[0], K, modelo=m["nombre"])
    #     imprimir_resumen(registro, preguntas[0], respuesta)
    #     guardar_registro_jsonl(registro)

    # Prueba sin llamar al modelo: cuánto crece el prompt con el contexto RAG.
    # tiempos = {}
    # with medir(tiempos, "embed_y_busqueda"):
    #     retriever = vs.as_retriever(search_kwargs={"k": K})
    #     chunks = retriever.invoke(preguntas[0])
    # contexto, citas = formatear_contexto(chunks)
    # prompt_con_rag = PROMPT_TEMPLATE.format(contexto=contexto, pregunta=preguntas[0])
    # print(f"Pregunta sola. Caracteres: {len(preguntas[0])}. Tokens Aprox: {aprox_tokens(preguntas[0])}")
    # print(f"Prompt con RAG. Caracteres: {len(prompt_con_rag)}. Tokens Aprox: {aprox_tokens(prompt_con_rag)}")
    # print("Factor de crecimiento:", round(len(prompt_con_rag) / len(preguntas[0]), 1), "x")
    # print("Tiempos:", tiempos)

    """
    #Flujo normal:
    #Etapa 1: Embed y la busqueda vectorial (Consulta a mi VS)
    retriever = vectorstore.as_retriever(search_kwargs={"k": k})
    chunks = retriever.invoke(pregunta) #busqueda vectorial con Chroma

    #Etapa 2: Armado del prompt (agregando el contexto/chunks formateados) - Acción Local
    contexto, citas = formatear_contexto(chunks)
    prompt = PROMPT_TEMPLATE.format(contexto=contexto, pregunta=pregunta)

    #Etapa 3: Generación de la respuesta con Gemini
    respuesta = chat_model.invoke(prompt)
    """
