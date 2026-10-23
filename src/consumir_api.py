import os
import requests
import time
import json
import re
from dotenv import load_dotenv

modelos = [
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


load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

# Función para armar la petición a la API de Gemini
def armar_peticion(pregunta_usuario, modelo, system_instruction=None, response_schema=None):
    if not pregunta_usuario:
        raise ValueError("La pregunta no puede estar vacía")
    api_key = API_KEY
    if not api_key:
        raise ValueError("La API key no está configurada")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={api_key}"
    body = {"contents": [{"parts": [{"text": pregunta_usuario.strip()}]}]}
    # Si se proporciona una instrucción del sistema, se agrega al cuerpo de la petición
    if system_instruction:
        body["systemInstruction"] = {"parts": [{"text": system_instruction.strip()}]}
    # el modelo responde un texto JSON que cumple esa estructura
    if response_schema:
        body["generationConfig"] = {
            "responseMimeType": "application/json",
            "responseSchema": response_schema
        }
    return url, body

# Función para enviar la petición a la API de Gemini
def enviar_peticion(url, body):
    try:
        respuesta = requests.post(url, json=body, timeout=30)
        if respuesta.status_code != 200:
            raise RuntimeError(f"Error en la respuesta del servicio: {respuesta.status_code}")
    except requests.exceptions.ConnectionError:
        raise RuntimeError("No se pudo conectar con el servicio. Intenta de nuevo en unos segundos.")
    except requests.exceptions.Timeout:
        raise RuntimeError("El servicio tardó demasiado en responder. Intenta de nuevo en unos segundos.")
    
    try:
        return respuesta.json()
    except requests.exceptions.JSONDecodeError:
        raise RuntimeError("La respuesta del servicio no llegó en el formato esperado.")

# Función para extraer el texto de la respuesta de la API de Gemini
def extraer_texto(datos):
    try:
        return datos["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise RuntimeError("La respuesta no trae el texto generado en el lugar esperado.")

# Función para calcular el costo estimado a partir del uso de tokens de la respuesta
def calcular_costo(datos, precio_entrada, precio_salida):
    try:
        uso = datos["usageMetadata"]
        tokens_entrada = uso["promptTokenCount"]
        tokens_salida = uso["candidatesTokenCount"]
        tokens_razonamiento = uso.get("thoughtsTokenCount", 0)  # los modelos sin razonamiento no envían este campo
    except KeyError:
        raise RuntimeError("La respuesta no trae la información de uso de tokens.")
    costo_total = (tokens_entrada * precio_entrada) + ( (tokens_salida + tokens_razonamiento) * precio_salida )
    return costo_total

# Función para buscar los precios de un modelo en la lista de modelos
def obtener_precios(modelo):
    for m in modelos:
        if m["nombre"] == modelo:
            return m["precio_entrada"], m["precio_salida"]
    raise ValueError(f"El modelo {modelo} no está en la lista de modelos")

# Función que consulta un modelo y devuelve el texto, el tiempo de respuesta y el costo
def consultar_modelo(pregunta, modelo, system_instruction=None, response_schema=None):
    precio_entrada, precio_salida = obtener_precios(modelo)
    url, body = armar_peticion(pregunta, modelo, system_instruction, response_schema)

    inicio = time.perf_counter()
    datos = enviar_peticion(url, body)
    segundos = time.perf_counter() - inicio

    texto = extraer_texto(datos)
    costo = calcular_costo(datos, precio_entrada, precio_salida)
    return texto, segundos, costo

# Función para convertir el texto del modelo en un diccionario, limpiando los bloques ```json si vienen
def parsear_respuesta_json(texto):
    limpio = re.sub(r"^```(?:json)?\s*|\s*```$", "", texto.strip())
    try:
        datos = json.loads(limpio)
    except json.JSONDecodeError:
        raise ValueError("El texto proporcionado no es un JSON válido.")
    if not isinstance(datos, dict):
        raise ValueError("La respuesta no tiene la estructura esperada.")
    return datos

# Solo se ejecuta al correr este archivo directamente, no al importarlo
if __name__ == "__main__":
    try:
        # Aquí puedes cambiar la pregunta o el modelo según tus necesidades
        """
        system_instruction = "Eres un asistente útil que responde preguntas de geografía."
        response_schema = {
                    "type": "object",
                    "properties": {
                        "respuesta": {"type": "string"},
                        "confianza": {"type": "number"}
                    },
                    "required": ["respuesta", "confianza"]
                }
        """
        
        texto, segundos, costo = consultar_modelo("¿Cuál es la capital de Francia?", "gemini-3.1-flash-lite")
        print(texto)
        print(f"Tiempo de respuesta: {segundos:.2f} segundos")
        print(f"Costo de la petición: ${costo:.6f} USD")
    except (ValueError, RuntimeError) as error:
        print("No se pudo completar la operación:", error)