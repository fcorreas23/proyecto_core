import os
import requests
from dotenv import load_dotenv

load_dotenv()

def obtener_dato_de_prueba(pregunta):
    api_key = os.getenv("GEMINI_API_KEY")
    modelo = "gemini-flash-latest"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={api_key}"
    body = {"contents": [{"parts": [{"text": pregunta}]}]}
    response = requests.post(url, json=body)
    data = response.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]

print(obtener_dato_de_prueba("¿Cuál es la capital de Francia?"))