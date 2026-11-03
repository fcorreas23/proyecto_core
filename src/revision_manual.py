import json
from pathlib import Path

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
ARCHIVO_RESULTADOS = RAIZ_PROYECTO / "docs" / "resultados_metricas.json"
ARCHIVO_REVISION = RAIZ_PROYECTO / "docs" / "revision_manual.json"
CASOS_POR_EXTREMO = 5

REVISIONES = {
    "¿Qué es cron en Linux?": {
        "correccion_factual": "si",
        "completitud": "parcialmente",
        "contradiccion": "no",
        "nota": "habla de horarios específicos, pero no dice que la ejecución sea periódica; 'programar' no coincide con 'programadas'",
    },
    "¿Qué hace el comando tar en Linux?": {
        "correccion_factual": "si",
        "completitud": "si",
        "contradiccion": "no",
        "nota": "'empaquetar en un único archivo' equivale a 'agrupa en uno solo'; la métrica no reconoce la paráfrasis",
    },
    "¿Qué es el usuario root en Linux?": {
        "correccion_factual": "si",
        "completitud": "si",
        "contradiccion": "no",
        "nota": "'superusuario' y 'privilegios ilimitados' equivalen a 'administrador con control total'; ninguno coincide como token",
    },
    "¿Qué hace el comando chown en Linux?": {
        "correccion_factual": "si",
        "completitud": "si",
        "contradiccion": "no",
        "nota": "correcta; agrega el grupo y los directorios, y ese detalle extra baja la precisión",
    },
    "¿Qué es un proceso en Linux?": {
        "correccion_factual": "si",
        "completitud": "si",
        "contradiccion": "no",
        "nota": "cobertura 1.0 con F1 bajo: 'PID' y 'memoria' son información correcta que la métrica castiga por no estar en la referencia",
    },
    "¿Cuándo se creó Python?": {
        "correccion_factual": "parcialmente",
        "completitud": "si",
        "contradiccion": "no",
        "nota": "el año coincide; 'febrero' no está en la referencia y corresponde a la primera publicación, no a la creación",
    },
    "¿Qué hace el comando grep en Linux?": {
        "correccion_factual": "si",
        "completitud": "si",
        "contradiccion": "no",
        "nota": "correcta y casi literal; F1 alto bien justificado",
    },
    "¿Qué es un enlace simbólico en Linux?": {
        "correccion_factual": "si",
        "completitud": "si",
        "contradiccion": "no",
        "nota": "correcta; 'acceso directo' agrega una analogía válida",
    },
    "¿Qué hace el comando pwd en Linux?": {
        "correccion_factual": "si",
        "completitud": "si",
        "contradiccion": "no",
        "nota": "correcta y casi literal; F1 alto bien justificado",
    },
    "¿Qué contiene el directorio /etc en Linux?": {
        "correccion_factual": "si",
        "completitud": "si",
        "contradiccion": "no",
        "nota": "correcta; agrega los programas instalados, lo que es cierto",
    },
}

# Función que elige los casos con F1 más bajo y más alto para revisarlos a mano
def obtener_muestra(resultados):
    ordenados = sorted(resultados, key=lambda r: r["f1"])
    return ordenados[:CASOS_POR_EXTREMO] + ordenados[-CASOS_POR_EXTREMO:]

# Función que une cada caso de la muestra con su revisión manual
def armar_revision(resultados):
    return [
        {"consulta": caso["consulta"], "f1": caso["f1"], **REVISIONES[caso["consulta"]]}
        for caso in obtener_muestra(resultados)
    ]


if __name__ == "__main__":
    with open(ARCHIVO_RESULTADOS, encoding="utf-8") as archivo:
        resultados = json.load(archivo)

    revision_manual = armar_revision(resultados)

    with open(ARCHIVO_REVISION, "w", encoding="utf-8") as archivo:
        json.dump(revision_manual, archivo, indent=2, ensure_ascii=False)

    print(f"{len(revision_manual)} casos guardados en {ARCHIVO_REVISION}")
