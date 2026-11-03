import json
import time
from collections import Counter
from pathlib import Path
from pipeline_limpieza import procesar_texto
from cliente import consultar_modelo

ARCHIVO_RESULTADOS = Path(__file__).resolve().parent.parent / "docs" / "resultados_metricas.json"
PAUSA = 6  # segundos entre peticiones para no superar la cuota del plan gratuito
SYSTEM_INSTRUCTION = "Responde en una sola frase."

def contar_coincidencias(
    tokens_referencia: list[str],
    tokens_respuesta: list[str],
) -> int:
    """Cuenta las coincidencias entre referencia y respuesta."""
    conteo_referencia = Counter(tokens_referencia)
    conteo_respuesta = Counter(tokens_respuesta)
    interseccion = conteo_referencia & conteo_respuesta
    return sum(interseccion.values())

def calcular_precision_cobertura_f1(
    tokens_referencia: list[str],
    tokens_respuesta: list[str],
) -> dict[str, float]:
    """Calcula precisión, cobertura y F1 de dos listas de tokens."""
    coincidencias = contar_coincidencias(
        tokens_referencia, tokens_respuesta
    )

    if not tokens_respuesta or not tokens_referencia:
        return {"precision": 0.0, "cobertura": 0.0, "f1": 0.0}

    precision = coincidencias / len(tokens_respuesta)
    cobertura = coincidencias / len(tokens_referencia)

    if precision + cobertura == 0:
        f1 = 0.0
    else:
        f1 = 2 * precision * cobertura / (precision + cobertura)

    resultado = {
        "precision": precision,
        "cobertura": cobertura,
        "f1": f1,
    }

    return resultado

def calcular_metricas(texto_referencia, texto_respuesta):
    tokens_referencia = procesar_texto(texto_referencia)
    tokens_respuesta = procesar_texto(texto_respuesta)
    
    return calcular_precision_cobertura_f1(
        tokens_referencia, tokens_respuesta
    )

casos = [

    ("¿Qué es Python?","Python es un lenguaje de programación interpretado."),
    ("¿Cuándo se creó Python?", "Python fue creado en 1991."),
    ("¿Qué es una lista en Python?","Una lista es una colección ordenada y modificable."),
    ("¿Qué es Linux?", "Linux es un núcleo de sistema operativo de código abierto creado por Linus Torvalds."),
    ("¿Cuándo se publicó Linux?", "La primera versión de Linux se publicó en 1991."),
    ("¿Qué es el kernel de Linux?","El kernel es el núcleo del sistema que administra el hardware y los procesos."),
    ("¿Qué es una distribución de Linux?","Una distribución combina el kernel Linux con programas y un gestor de paquetes."),
    ("¿Qué hace el comando ls en Linux?", "El comando ls lista los archivos y directorios."),
    ("¿Qué hace el comando cd en Linux?", "El comando cd cambia el directorio actual."),
    ("¿Qué hace el comando pwd en Linux?", "El comando pwd muestra la ruta del directorio actual."),
    ("¿Qué hace el comando grep en Linux?", "El comando grep busca patrones de texto en archivos."),
    ("¿Qué hace el comando chmod en Linux?", "El comando chmod cambia los permisos de un archivo."),
    ("¿Qué hace el comando chown en Linux?", "El comando chown cambia el propietario de un archivo."),
    ("¿Qué hace el comando sudo en Linux?", "El comando sudo ejecuta un comando con los privilegios de otro usuario, normalmente root."),
    ("¿Qué es el usuario root en Linux?", "Root es el usuario administrador con control total del sistema."),
    ("¿Qué contiene el directorio /etc en Linux?", "El directorio /etc contiene los archivos de configuración del sistema."),
    ("¿Qué contiene el directorio /home en Linux?", "El directorio /home contiene los directorios personales de los usuarios."),
    ("¿Qué es un proceso en Linux?", "Un proceso es un programa en ejecución."),
    ("¿Qué hace el comando ps en Linux?", "El comando ps muestra los procesos en ejecución."),
    ("¿Qué hace el comando kill en Linux?", "El comando kill envía una señal a un proceso, normalmente para terminarlo."),
    ("¿Qué es una tubería en la terminal de Linux?","Una tubería conecta la salida de un comando con la entrada de otro.",),
    ("¿Qué es la shell en Linux?", "La shell es un intérprete de comandos."),
    ("¿Qué es Bash?", "Bash es una shell y un lenguaje de scripting usado en Linux."),
    ("¿Qué es un enlace simbólico en Linux?", "Un enlace simbólico es un archivo que apunta a otro archivo o directorio."),
    ("¿Qué es systemd en Linux?", "Systemd es el sistema de inicio y gestor de servicios."),
    ("¿Qué es cron en Linux?", "Cron ejecuta tareas programadas de forma periódica."),
    ("¿Qué es apt en Linux?", "Apt es el gestor de paquetes de Debian y Ubuntu."),
    ("¿Qué es SSH?", "SSH es un protocolo para conectarse de forma remota y cifrada a otra máquina."),
    ("¿Qué hace el comando tar en Linux?", "El comando tar agrupa varios archivos en uno solo."),
    ("¿Qué hace el comando df en Linux?", "El comando df muestra el espacio disponible en disco."),
]

# Función que consulta el modelo por cada caso y mide su respuesta contra la referencia
def evaluar_casos(casos):
    resultados = []
    for consulta, referencia in casos:
        time.sleep(PAUSA)
        try:
            respuesta = consultar_modelo(consulta, system_instruction=SYSTEM_INSTRUCTION)
        except RuntimeError as error:
            print(f"{consulta} falló: {error}")
            continue
        metricas = calcular_metricas(referencia, respuesta)
        print(consulta, metricas)
        resultados.append({
            "consulta": consulta,
            "respuesta": respuesta,
            **{clave: round(valor, 2) for clave, valor in metricas.items()},
        })
    return resultados

# Función que guarda cada respuesta junto a sus métricas
def guardar_resultados(resultados):
    with open(ARCHIVO_RESULTADOS, "w", encoding="utf-8") as archivo:
        json.dump(resultados, archivo, indent=2, ensure_ascii=False)


# Función que resume todos los resultados en un promedio por métrica
def resumir_metricas(resultados):
    if not resultados:
        return {
            "precision_promedio": 0,
            "cobertura_promedio": 0,
            "f1_promedio": 0,
        }

    n = len(resultados)

    return {
        "precision_promedio": sum(r["precision"] for r in resultados) / n,
        "cobertura_promedio": sum(r["cobertura"] for r in resultados) / n,
        "f1_promedio": sum(r["f1"] for r in resultados) / n,
    }

# Función que ordena los resultados de peor a mejor F1, para leer primero los peores
def obtener_peores_casos(resultados, cantidad=3):
    return sorted(resultados, key=lambda r: r["f1"])[:cantidad]


if __name__ == "__main__":
    resultados = evaluar_casos(casos)
    guardar_resultados(resultados)

    print(resumir_metricas(resultados))
    for caso in obtener_peores_casos(resultados):
        print(caso["consulta"], caso["f1"])
    print(f"Resultados guardados en {ARCHIVO_RESULTADOS}")