import json
import sys
import time
from pathlib import Path
from consumir_api import armar_peticion, enviar_peticion, extraer_texto, parsear_respuesta_json

# Python solo busca módulos en src/; se agrega la raíz del proyecto para poder importar prompts/
RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
sys.path.append(str(RAIZ_PROYECTO))
from prompts.banco import BANCO_DE_PROMPTS

MODELO = "gemini-3.5-flash-lite"
INTENTOS = 3
PAUSA =  3 # segundos entre peticiones para no superar la cuota del plan gratuito
ARCHIVO_REGISTRO = RAIZ_PROYECTO / "prompts" / "registro_resultados.json"

# Tipos de Python que corresponden a cada tipo del response_schema
TIPOS = {"STRING": str, "NUMBER": (int, float), "INTEGER": int, "BOOLEAN": bool, "ARRAY": list, "OBJECT": dict}

# Función que revisa que la respuesta traiga las claves esperadas y, si hay esquema, con el tipo correcto
def validar_estructura(datos, prompt):
    faltantes = [clave for clave in prompt["claves_esperadas"] if clave not in datos]
    if faltantes:
        raise ValueError(f"La respuesta no tiene la estructura esperada. Faltan: {', '.join(faltantes)}")
    propiedades = prompt.get("response_schema", {}).get("properties", {})
    for clave, definicion in propiedades.items():
        tipo = TIPOS[definicion["type"]]
        # bool es subclase de int en Python, así que un true no debe contar como número
        if not isinstance(datos[clave], tipo) or (isinstance(datos[clave], bool) and definicion["type"] != "BOOLEAN"):
            raise ValueError(f"La clave '{clave}' no es de tipo {definicion['type']}.")

# Función que ejecuta cada prompt del banco INTENTOS veces y cuenta cuántas respuestas fueron válidas
def probar_banco():
    registro = {"modelo": MODELO, "fecha": time.strftime("%Y-%m-%d"), "prompts": {}}
    for prompt in BANCO_DE_PROMPTS:
        exitos = 0
        detalle = []
        for intento in range(INTENTOS):
            texto = None
            datos = None
            try:
                url, body = armar_peticion(
                    prompt["ejemplo_usuario"],
                    MODELO,
                    prompt["system_instruction"],
                    prompt.get("response_schema"),
                )
                respuesta = enviar_peticion(url, body)
                texto = extraer_texto(respuesta)
                datos = parsear_respuesta_json(texto)
                validar_estructura(datos, prompt)
                exitos += 1
                detalle.append({"intento": intento + 1, "valido": True, "respuesta": datos})
            except (ValueError, RuntimeError) as error:
                print(f"  intento {intento + 1} falló: {error}")
                # Se guarda el JSON si se pudo leer, si no el texto crudo, o None si el servicio no respondió
                detalle.append({
                    "intento": intento + 1,
                    "valido": False,
                    "motivo": str(error),
                    "respuesta": datos if datos is not None else texto
                })
            time.sleep(PAUSA)
        print(f"{prompt['nombre']}: {exitos}/{INTENTOS} respuestas válidas")
        registro["prompts"][prompt["nombre"]] = {
            "usa_response_schema": "response_schema" in prompt,
            "exitos": exitos,
            "fallos": INTENTOS - exitos,
            "intentos": INTENTOS,
            "detalle_intentos": detalle
        }
    return registro

if __name__ == "__main__":
    registro = probar_banco()
    with open(ARCHIVO_REGISTRO, "w", encoding="utf-8") as archivo:
        json.dump(registro, archivo, indent=2, ensure_ascii=False)
    print(f"\nRegistro guardado en {ARCHIVO_REGISTRO}")
