import os
import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

# Función para armar la petición a la API de Gemini
def armar_peticion(pregunta, modelo):
	if not pregunta:
		raise ValueError("La pregunta no puede estar vacía")
	api_key = API_KEY
	url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={api_key}"
	body = {"contents": [{"parts": [{"text": pregunta}]}]}
	return url, body

# Función para enviar la petición a la API de Gemini
def enviar_peticion(url, body):
    try:
        respuesta = requests.post(url, json=body)
    except requests.exceptions.ConnectionError:
        raise RuntimeError("No se pudo conectar con el servicio. Intenta de nuevo en unos segundos.")
    
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

# Función para obtener un dato de prueba usando la API de Gemini
def obtener_dato_de_prueba(pregunta, modelo ="gemini-flash-latest"):
    url, body = armar_peticion(pregunta, modelo)
    datos = enviar_peticion(url, body)
    return extraer_texto(datos)

try:
    # Intentamos obtener un dato de prueba usando la API de Gemini
    # Aquí puedes cambiar la pregunta o el modelo según tus necesidades
    print(obtener_dato_de_prueba("¿Cuál es la capital de Francia?")) # Prueba con la pregunta sobre la capital de Francia
except (ValueError, RuntimeError) as error:
    print("No se pudo completar la operación:", error)