import hashlib
import json
import os
import queue
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

# === Configuración ===
load_dotenv()
MODELO = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
ARCHIVO_TRAZAS = Path(__file__).resolve().parents[2] / "docs" / "trazas_agente.jsonl"

# === Datos de ejemplo (no es una base de datos persistente) ===
ESTADOS = {
    "AR12345": {
        "actual": "En tránsito, entrega estimada de 2 días",
        "historial": ["Recibido en depósito", "En tránsito"],
    },
    "AR12346": {
        "actual": "Entregado",
        "historial": ["Recibido en depósito", "En tránsito", "Entregado"],
    },
}

# === Auditoría y supervisión humana ===
registro_aprobaciones: list[dict[str, Any]] = []


def esperar_aprobacion(mensaje: str, tiempo_limite_segundos: int = 15) -> bool:
    """Solicita autorización por consola; si no hay respuesta, rechaza.

    Nota: un input() en un hilo puede continuar bloqueado tras el timeout.
    Este mecanismo es solo una demostración, no un sistema de aprobación web.
    """
    cola_respuesta: queue.Queue[str] = queue.Queue(maxsize=1)

    def pedir_entrada() -> None:
        try:
            texto = input(mensaje)
            cola_respuesta.put_nowait(texto.strip().lower())
        except (EOFError, KeyboardInterrupt):
            cola_respuesta.put_nowait("")

    hilo = threading.Thread(target=pedir_entrada, daemon=True)
    hilo.start()

    try:
        return cola_respuesta.get(timeout=tiempo_limite_segundos) == "s"
    except queue.Empty:
        print("Tiempo de espera agotado: solicitud denegada.")
        return False


def registrar_aprobacion(herramienta: str, argumentos: dict, aprobado: bool) -> None:
    registro_aprobaciones.append(
        {
            "herramienta": herramienta,
            "argumentos": argumentos,
            "aprobado": aprobado,
            "fecha_hora": datetime.now(timezone.utc).isoformat(),
        }
    )


# === Esquemas de validación ===
class ArgumentosConsultaEnvio(BaseModel):
    numero_seguimiento: str = Field(
        min_length=1,
        description="Número de seguimiento, por ejemplo AR12345.",
    )
    incluir_historial: bool = Field(
        default=False,
        description="True para incluir los estados históricos del envío.",
    )


class ArgumentosCostoEnvio(BaseModel):
    peso_kg: float = Field(gt=0, description="Peso en kilogramos, mayor que cero.")
    distancia_km: float = Field(ge=0, description="Distancia en kilómetros, no negativa.")


class ArgumentosReembolso(BaseModel):
    numero_pedido: str = Field(min_length=1, description="Identificador del pedido.")
    monto: float = Field(gt=0, description="Monto solicitado, mayor que cero.")


# === Herramientas ===
@tool(args_schema=ArgumentosConsultaEnvio)
def consultar_estado_envio_detallado(
    numero_seguimiento: str, incluir_historial: bool = False
) -> str:
    """Consulta el estado de un envío y, si se solicita, su historial."""
    envio = ESTADOS.get(numero_seguimiento.upper())
    if envio is None:
        return f"No se encontró un envío con el número {numero_seguimiento}."
    if not incluir_historial:
        return envio["actual"]
    historial = ", ".join(envio["historial"])
    return f"{envio['actual']} (historial: {historial})"


@tool(args_schema=ArgumentosCostoEnvio)
def calcular_costo_envio(peso_kg: float, distancia_km: float) -> str:
    """Calcula el costo estimado de un envío usando peso y distancia."""
    costo = 500 + peso_kg * 120 + distancia_km * 3
    return f"El costo estimado es de ${costo:.2f}"


@tool(args_schema=ArgumentosReembolso)
def generar_reembolso(numero_pedido: str, monto: float) -> str:
    """SIMULA un reembolso; solicita aprobación humana antes de confirmar la simulación."""
    mensaje = (
        "\n[SUPERVISIÓN HUMANA] "
        f"¿Autoriza simular el reembolso de ${monto:.2f} "
        f"para el pedido {numero_pedido}? (s/n): "
    )
    aprobado = esperar_aprobacion(mensaje, tiempo_limite_segundos=15)
    registrar_aprobacion(
        herramienta="generar_reembolso",
        argumentos={"numero_pedido": numero_pedido, "monto": monto},
        aprobado=aprobado,
    )
    if not aprobado:
        return "Reembolso no aprobado o cancelado por tiempo de espera."
    return (
        f"Simulación aprobada: reembolso de ${monto:.2f} "
        f"para el pedido {numero_pedido}. No se transfirió dinero real."
    )


herramientas = [
    consultar_estado_envio_detallado,
    calcular_costo_envio,
    generar_reembolso,
]

# === Historial de chat por sesión (solo RAM) ===
historiales: dict[str, InMemoryChatMessageHistory] = {}


def obtener_historial(session_id: str) -> InMemoryChatMessageHistory:
    if session_id not in historiales:
        historiales[session_id] = InMemoryChatMessageHistory()
    return historiales[session_id]


# === Normalización de respuestas ===
def normalizar_salida(resultado: dict) -> dict:
    """Convierte bloques de texto del modelo a un string para guardar en memoria."""
    salida = resultado.get("output", "")
    if isinstance(salida, list):
        salida = " ".join(
            bloque.get("text", "")
            for bloque in salida
            if isinstance(bloque, dict)
            and bloque.get("type") == "text"
            and isinstance(bloque.get("text"), str)
        )
    elif not isinstance(salida, str):
        salida = str(salida)
    return {**resultado, "output": salida}


# === Registro de trazabilidad ===
def huella(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:12]


def registrar_traza(session_id: str, entrada: str, resultado: dict) -> None:
    """Guarda herramientas llamadas y respuesta final, una línea JSON por turno.
    El texto del usuario y la respuesta del modelo no se guardan tal cual (Bloque 31): solo su
    longitud y su huella. Herramienta, argumentos y observación sí, porque son los datos
    estructurados que se auditan (monto, pedido, aprobado o no)."""
    acciones = []
    for accion, observacion in resultado.get("intermediate_steps", []):
        acciones.append(
            {
                "herramienta": accion.tool,
                "argumentos": accion.tool_input,
                "observacion": observacion,
            }
        )

    registro = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "entrada_len": len(entrada),
        "entrada_hash": huella(entrada),
        "acciones": acciones,
        "respuesta_len": len(resultado.get("output", "")),
        "respuesta_hash": huella(resultado.get("output", "")),
    }
    with ARCHIVO_TRAZAS.open("a", encoding="utf-8") as archivo:
        archivo.write(json.dumps(registro, ensure_ascii=False, default=str) + "\n")


# === Creación del agente ===
def crear_agente():
    if not os.getenv("GOOGLE_API_KEY") and not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError(
            "Falta GOOGLE_API_KEY o GEMINI_API_KEY en el archivo .env."
        )

    modelo = ChatGoogleGenerativeAI(model=MODELO, temperature=0)
    prompt_agente = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Eres un asistente de logística. Usa las herramientas disponibles "
                "para consultar envíos, calcular costos y simular reembolsos. "
                "No inventes estados ni precios. "
                "Los reembolsos son únicamente simulaciones y requieren aprobación humana.",
            ),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{entrada}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )
    agente = create_tool_calling_agent(modelo, herramientas, prompt_agente)
    ejecutor_agente = AgentExecutor(
        agent=agente,
        tools=herramientas,
        verbose=True,
        return_intermediate_steps=True,
        max_iterations=5,
        handle_parsing_errors=True,
    )
    cadena_agente = ejecutor_agente | RunnableLambda(normalizar_salida)
    return RunnableWithMessageHistory(
        cadena_agente,
        obtener_historial,
        input_messages_key="entrada",
        history_messages_key="chat_history",
        output_messages_key="output",
    )


# === Ejecución de pruebas ===
def preguntar(agente_con_memoria, session_id: str, pregunta: str) -> None:
    config = {"configurable": {"session_id": session_id}}
    print(f"\nUsuario ({session_id}): {pregunta}")
    resultado = agente_con_memoria.invoke({"entrada": pregunta}, config=config)
    print("Agente:", resultado["output"])
    registrar_traza(session_id, pregunta, resultado)


def main() -> None:
    agente_con_memoria = crear_agente()

    # Prueba 1: primer turno del cliente
    preguntar(
        agente_con_memoria,
        "cliente_246",
        "¿Cuánto me cuesta enviar un paquete de 2.5 kg a 50 km?",
    )

    # Prueba 2: mismo cliente; debe recordar peso y distancia
    preguntar(
        agente_con_memoria,
        "cliente_246",
        "¿Y cuánto costaría si pesara el doble?",
    )

    # Prueba 3: otro cliente, con una memoria independiente
    preguntar(
        agente_con_memoria,
        "cliente_456",
        "¿Cuál es el estado del envío AR12345, con su historial?",
    )

    # Prueba 4 opcional: descomentar para probar aprobación humana
    # preguntar(
    #     agente_con_memoria,
    #     "cliente_123",
    #     "Mi pedido PED123 llegó roto. Solicito un reembolso de 25000 pesos.",
    # )

    print("\n=== HISTORIAL DE cliente_246 ===")
    for mensaje in obtener_historial("cliente_246").messages:
        print(f"{mensaje.type}: {mensaje.content}")

    print(f"\nTrazas guardadas en: {ARCHIVO_TRAZAS.resolve()}")
    print("Aprobaciones registradas en esta ejecución:", registro_aprobaciones)


if __name__ == "__main__":
    main()
