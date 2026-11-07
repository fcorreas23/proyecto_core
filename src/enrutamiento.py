"""
Flujo completo de cadena_robusta.invoke({"mensaje": ...}):

  1. {"mensaje": "..."}
        |  RunnablePassthrough.assign(categoria=paso_clasificacion)
        |  (el modelo clasifica el mensaje y el resultado se agrega como llave nueva)
        v
  2. {"mensaje": "...", "categoria": "queja"}
        |  bifurcacion (RunnableBranch)
        |  (revisa x["categoria"] y elige UNA de las tres cadenas)
        v
  3. Respuesta final en texto, generada por la cadena elegida

  Si cualquier paso lanza una excepción (rate limit, credencial inválida, sin conexión),
  with_fallbacks ejecuta respuesta_generica en su lugar.

En total se hacen 2 llamadas al modelo: una para clasificar y otra para responder.

Las piezas se arman con funciones que las reciben como parámetros, para poder
reemplazarlas por mocks en test/test_enrutamiento.py. El modelo real solo se crea
al ejecutar este archivo directamente, así importarlo en las pruebas no llama a la API.
"""
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableBranch, RunnablePassthrough, RunnableLambda
from langchain_core.callbacks import BaseCallbackHandler
import logging

logger = logging.getLogger(__name__)

# ================= CONSTANTES =================

MENSAJE_ERROR = "No pudimos procesar tu mensaje en este momento. Intenta de nuevo más tarde"

# En cada plantilla, {mensaje} se reemplaza por el valor de la llave "mensaje" del diccionario de entrada
PLANTILLA_CLASIFICACION = PromptTemplate.from_template(
    "Clasifica el siguiente mensaje de soporte en una sola "
    "palabra: pregunta, queja o sugerencia. Responde solo "
    "con esa palabra.\n\n{mensaje}"
)

# Las tres rutas tienen la misma forma (plantilla | modelo | parser) y solo cambia la instrucción.
# Ruta por defecto: se usa para "pregunta" y para cualquier categoría no reconocida
PLANTILLA_PREGUNTA = PromptTemplate.from_template(
    "Responde esta pregunta técnica con precisión:\n\n{mensaje}"
)

PLANTILLA_QUEJA = PromptTemplate.from_template(
    "Responde a esta queja con empatía, reconociendo el "
    "problema antes de ofrecer una solución:\n\n{mensaje}"
)

PLANTILLA_SUGERENCIA = PromptTemplate.from_template(
    "Agradece esta sugerencia y explica cómo se evaluará "
    "dentro del producto:\n\n{mensaje}"
)

# ================= CLASIFICACIÓN =================

""" Recibe {"mensaje": ...} y devuelve solo el texto de la categoría, por ejemplo "queja". La lambda quita espacios y pasa a minúsculas para que "Queja" o " queja\n" se comparen igual que "queja". Ojo: no quita la puntuación, así que "Queja." quedaría como "queja." """
def construir_paso_clasificacion(modelo):
    return (
        PLANTILLA_CLASIFICACION
        | modelo
        | StrOutputParser()
        | (lambda texto: texto.strip().lower())
    )

# ================= CADENA COMPLETA =================

# RunnableBranch evalúa las condiciones en orden y ejecuta la ruta de la primera que
# devuelva True. Si ninguna se cumple, ejecuta el último elemento (cadena_pregunta).
# Una ruta que no se pasa como argumento queda como RunnablePassthrough(): en las
# pruebas basta con pasar la ruta que se quiere verificar.
def construir_cadena_con_enrutamiento(
    paso_clasificacion,
    cadena_queja=None,
    cadena_sugerencia=None,
    cadena_pregunta=None,
):
    cadena_queja = cadena_queja or RunnablePassthrough()
    cadena_sugerencia = cadena_sugerencia or RunnablePassthrough()
    cadena_pregunta = cadena_pregunta or RunnablePassthrough()
    bifurcacion = RunnableBranch(
        (lambda x: x["categoria"] == "queja", cadena_queja),
        (lambda x: x["categoria"] == "sugerencia", cadena_sugerencia),
        cadena_pregunta,
    )
    return (
        RunnablePassthrough.assign(categoria=paso_clasificacion)
        | bifurcacion
    )

# ================= FALLBACK =================

# Registra en el log cada error de la cadena antes de que el fallback lo reemplace.
# on_chain_error se dispara una vez por cada runnable que contiene al paso que falló
# (el paso, la secuencia, el assign...), así que el mismo error llega varias veces.
# Cuando el aviso viene del padre del runnable anterior, es el mismo error subiendo
# de nivel y no se registra: solo queda el del paso donde se originó.
class CapturadorError(BaseCallbackHandler):
    def __init__(self):
        self.padre_del_ultimo_error = None

    def on_chain_error(self, error: BaseException, *, run_id, parent_run_id=None, **kwargs):
        es_el_mismo_error_subiendo = run_id == self.padre_del_ultimo_error
        self.padre_del_ultimo_error = parent_run_id
        if es_el_mismo_error_subiendo:
            return
        logger.warning("Error capturado antes del fallback: [%s] -> %s", type(error).__name__, error)

# Cadena de respaldo: no llama al modelo, así que funciona aunque el LLM esté caído.
# Con exception_key="error" recibe {"mensaje": ..., "error": <excepción original>}.
respuesta_generica = RunnableLambda(
    lambda x: "Gracias por tu mensaje. Un miembro de nuestro equipo se pondrá en contacto contigo pronto."
)

# El capturador se conecta a la cadena principal y no al respaldo, para registrar solo
# los errores que activan el fallback. Solo reacciona a excepciones: una respuesta
# vacía del modelo no lanza ninguna, así que no activa el fallback.
def construir_cadena_robusta(cadena, respaldo=respuesta_generica):
    cadena_con_capturador = cadena.with_config(callbacks=[CapturadorError()])
    return cadena_con_capturador.with_fallbacks([respaldo], exception_key="error")

# Fallback propio de la ruta de queja: si esa ruta falla, responde con el respaldo sin
# depender del fallback general de la cadena completa.
def construir_cadena_queja_segura(cadena_queja):
    return cadena_queja.with_fallbacks([respuesta_generica])

# Última red de seguridad: si también falla el respaldo (o la entrada no es válida),
# registra el error en el log y devuelve un mensaje fijo en vez de romper el programa.
def procesar_mensaje_seguro(cadena, mensaje):
    try:
        return cadena.invoke({"mensaje": mensaje})
    except Exception as error:
        logger.error("Error procesando mensaje: %s", error)
        return MENSAJE_ERROR


if __name__ == "__main__":
    # Los mensajes de nivel WARNING o superior se agregan (filemode="a") a error.
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        filename="error.log",
        filemode="a",
        encoding="utf-8",
        force=True
    )

    # Carga la API key desde .env y crea el modelo que usan todos los pasos
    load_dotenv()
    modelo = ChatGoogleGenerativeAI(model="gemini-3.6-flash")

    cadena_con_enrutamiento = construir_cadena_con_enrutamiento(
        paso_clasificacion=construir_paso_clasificacion(modelo),
        cadena_queja=construir_cadena_queja_segura(PLANTILLA_QUEJA | modelo | StrOutputParser()),
        cadena_sugerencia=PLANTILLA_SUGERENCIA | modelo | StrOutputParser(),
        cadena_pregunta=PLANTILLA_PREGUNTA | modelo | StrOutputParser(),
    )
    cadena_robusta = construir_cadena_robusta(cadena_con_enrutamiento)

    mensaje = "No me funciona la aplicación de RNA Seq, no puedo cargar mis datos."
    print(procesar_mensaje_seguro(cadena_robusta, mensaje))
