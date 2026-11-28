"""
Gate 2 - Verifica el entorno antes de la corrida final. Nunca imprime la clave.
Termina con código 1 si falta algo.

Ejecutar desde la raíz del proyecto:  python src/Gate2/verificar_entorno.py
"""
import os
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PAQUETES = ["langchain-core", "langchain-chroma", "langchain-google-genai", "chromadb",
            "langgraph", "python-dotenv", "pytest"]
VARIABLES = ["GEMINI_API_KEY"]
INDICE_DIR = RAIZ / "vectorstore"

try:
    from dotenv import load_dotenv
    load_dotenv(RAIZ / ".env")
except ImportError:
    pass

problemas = []
print("Python:", sys.version.split()[0])
if sys.version_info < (3, 10):
    problemas.append("usar Python 3.10 o superior")

for paquete in PAQUETES:
    try:
        print(f"{paquete}: {version(paquete)}")
    except PackageNotFoundError:
        print(f"{paquete}: NO instalado")
        problemas.append(f"instalar {paquete} (pip install -r requirements.txt)")

for nombre in VARIABLES:
    estado = "definida" if os.getenv(nombre) else "FALTA"
    print(f"{nombre}: {estado}")
    if estado == "FALTA":
        problemas.append(f"definir {nombre} en el archivo .env")

if INDICE_DIR.is_dir() and any(INDICE_DIR.iterdir()):
    print(f"indice en {INDICE_DIR.name}/: ok")
else:
    print(f"indice en {INDICE_DIR.name}/: NO existe o esta vacio")
    problemas.append("indexar el corpus (python src/Gate2/servicio_rag.py --reindexar)")

print()
if problemas:
    print("Pendiente: " + "; ".join(problemas))
    sys.exit(1)
print("Entorno listo para la corrida final")
