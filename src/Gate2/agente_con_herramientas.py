from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_classic.agents import (
    AgentExecutor,
    create_tool_calling_agent,
)
from langchain_core.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
)

load_dotenv()
modelo = ChatGoogleGenerativeAI(model="gemini-3.6-flash")


# --- Herramientas propias: biblioteca ---

CATALOGO = {
    "LIB001": "disponible, en la estantería B-12",
    "LIB002": "prestado, se devuelve el 20 de noviembre",
    "LIB003": "en reparación, sin fecha estimada",
}


@tool
def consultar_disponibilidad_libro(codigo_libro: str) -> str:
    """Consulta si un libro de la biblioteca está
    disponible a partir de su código (por ejemplo
    'LIB001'). Usar solo cuando el usuario pregunta
    por la disponibilidad o ubicación de un libro
    específico."""
    try:
        estado = CATALOGO[codigo_libro.strip().upper()]
        return f"El libro {codigo_libro} está {estado}."
    except KeyError:
        return (
            f"No se encontró ningún libro con el "
            f"código {codigo_libro}."
        )


@tool
def calcular_multa_atraso(dias_atraso: int, cantidad_libros: int) -> str:
    """Calcula la multa por devolver libros con
    atraso, según los días de atraso y la cantidad
    de libros. Usar solo cuando el usuario pregunta
    cuánto debe pagar por una devolución tardía."""
    try:
        dias = int(dias_atraso)
        libros = int(cantidad_libros)
        if dias < 0 or libros <= 0:
            raise ValueError(
                "los días no pueden ser negativos y "
                "debe haber al menos un libro"
            )
        multa = dias * libros * 250
        return f"La multa por atraso es de ${multa:.2f}."
    except (ValueError, TypeError) as e:
        return f"No se pudo calcular la multa: {e}."


herramientas = [consultar_disponibilidad_libro, calcular_multa_atraso]

prompt_agente = ChatPromptTemplate.from_messages([
    (
        "system",
        "Eres el asistente de una biblioteca. Usa las "
        "herramientas solo cuando la pregunta requiera "
        "consultar un libro o calcular una multa. Para "
        "preguntas generales responde directamente.",
    ),
    ("human", "{entrada}"),
    MessagesPlaceholder("agent_scratchpad"),
])

agente = create_tool_calling_agent(modelo, herramientas, prompt_agente)

ejecutor_agente = AgentExecutor(
    agent=agente,
    tools=herramientas,
    verbose=True,
    return_intermediate_steps=True,
)


def texto_respuesta(salida) -> str:
    """Gemini puede devolver el output como lista de
    bloques; esta función lo normaliza a texto."""
    if isinstance(salida, list):
        return "".join(
            b.get("text", "") if isinstance(b, dict) else str(b)
            for b in salida
        )
    return str(salida)


# --- Verificación de la elección de herramienta ---

def verificar_herramienta(entrada: str, esperada: str) -> None:
    resultado = ejecutor_agente.invoke({"entrada": entrada})
    pasos = resultado["intermediate_steps"]
    assert pasos, f"El agente no usó ninguna herramienta para: {entrada}"
    herramienta_usada = pasos[0][0].tool
    assert herramienta_usada == esperada, (
        f"Se esperaba {esperada} y se usó {herramienta_usada}"
    )
    print("Respuesta final:", texto_respuesta(resultado["output"]))


def test_agente_no_usa_herramienta_para_pregunta_general() -> None:
    resultado = ejecutor_agente.invoke(
        {"entrada": "¿Cuál es el horario de atención de la biblioteca?"}
    )
    assert resultado["intermediate_steps"] == []
    print("Respuesta final:", texto_respuesta(resultado["output"]))


if __name__ == "__main__":
    verificar_herramienta(
        "¿Está disponible el libro LIB001?",
        "consultar_disponibilidad_libro",
    )
    verificar_herramienta(
        "Devolví 2 libros con 3 días de atraso, ¿cuánto debo pagar?",
        "calcular_multa_atraso",
    )
    # Código inexistente: la herramienta maneja el error sin romper el agente
    verificar_herramienta(
        "¿Dónde está el libro LIB999?",
        "consultar_disponibilidad_libro",
    )
    test_agente_no_usa_herramienta_para_pregunta_general()
    print("\nTodas las verificaciones pasaron.")
