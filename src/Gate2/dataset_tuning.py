"""
Bloque 29 - Dataset validado para personalización con PEFT, sobre el asistente RAG de Git/GitHub.

Problema de COMPORTAMIENTO (no de conocimiento): en 20 respuestas reales del asistente, 8 no
cumplieron el formato pedido (docs/muestra_formato_respuestas.json). La falla dominante (7 de 18)
es citar varias fuentes en un solo corchete, "[1, 3]", cuando el prompt pide "[1]"; además una
respuesta omitió el comando. Al modelo no le falta información (la trae el RAG): le falta
consistencia en la forma de entregarla.

Tarea: a partir del contexto recuperado y la pregunta, responder SIEMPRE con este JSON:
  {"tipo": "con_comando" | "conceptual" | "fuera_de_alcance",
   "respuesta": texto con citas de un solo número por corchete, [1],
   "comando": el comando git principal, o null si la pregunta no pide uno,
   "citas": lista de los números citados en "respuesta" (vacía si está fuera de alcance)}

Los contextos son fragmentos reales de Guia_Git_GitHub_3_Usuarios.md.

Ejecutar desde la raíz del proyecto:  python src/Gate2/dataset_tuning.py
"""
import json
import re
import time
from collections import Counter

from google import genai
from google.genai import types


def contexto(*fragmentos: str) -> str:
    return "\n".join(f"[{i}] {f}" for i, f in enumerate(fragmentos, start=1))


def entrada(pregunta: str, *fragmentos: str) -> str:
    return f"Contexto:\n{contexto(*fragmentos)}\n\nPregunta: {pregunta}"


# ---------------------------------------------------------------------------
# Paso 1: ejemplos (entrada, salida exacta que el modelo debe aprender)
# ---------------------------------------------------------------------------
ejemplos_raw = [
    # --- con_comando: la pregunta pide cómo hacer algo ---
    (entrada("¿Cómo creo una rama nueva para mi tarea?",
             "Primero se actualiza la rama principal. Luego se crea una rama nueva para cada tarea: "
             "git switch main, git pull origin main, git switch -c feature/modelo.",
             "Para publicar por primera vez la rama en GitHub: git push -u origin feature/modelo."),
     {"tipo": "con_comando",
      "respuesta": "Actualiza main con git pull origin main y crea tu rama con git switch -c feature/modelo [1]. "
                   "Para publicarla por primera vez usa git push -u origin feature/modelo [2].",
      "comando": "git switch -c feature/modelo", "citas": [1, 2]}),

    (entrada("¿Cómo deshago un commit que ya compartí con mi equipo?",
             "Si el commit ya fue compartido con tu equipo, es preferible crear un commit inverso con git revert: "
             "git revert HEAD.",
             "Evita git reset y git push --force sobre commits compartidos. git revert conserva la historia "
             "de trabajo y suele ser más apropiado para ramas colaborativas."),
     {"tipo": "con_comando",
      "respuesta": "Crea un commit inverso con git revert HEAD [1]. No uses git reset ni git push --force "
                   "sobre commits compartidos, porque git revert conserva la historia [2].",
      "comando": "git revert HEAD", "citas": [1, 2]}),

    (entrada("¿Cómo guardo mis cambios un rato para cambiar de rama sin perderlos?",
             "git stash push -m \"Trabajo parcial del modelo\", git stash list, git switch main.",
             "git stash guarda temporalmente cambios rastreados. git stash pop lo elimina si se aplica correctamente."),
     {"tipo": "con_comando",
      "respuesta": "Guárdalos con git stash push -m \"Trabajo parcial del modelo\" y luego cambia de rama [1]. "
                   "Al volver, recupéralos con git stash pop [2].",
      "comando": "git stash push -m \"Trabajo parcial del modelo\"", "citas": [1, 2]}),

    (entrada("Perdí un commit después de hacer reset, ¿cómo lo recupero?",
             "git reflog muestra movimientos locales recientes de HEAD y otras referencias. Puede ayudarte a "
             "localizar commits retirados por un reset, mientras sigan disponibles.",
             "git reflog, git switch -c recuperacion HASH_DEL_COMMIT."),
     {"tipo": "con_comando",
      "respuesta": "Busca el hash del commit con git reflog [1] y crea una rama desde él con "
                   "git switch -c recuperacion HASH_DEL_COMMIT [2].",
      "comando": "git reflog", "citas": [1, 2]}),

    (entrada("¿Cómo vuelvo a la rama en la que estaba antes?",
             "git branch --show-current, git switch main, git switch feature/modelo, git switch -.",
             "git switch - vuelve a la referencia desde la que cambiaste."),
     {"tipo": "con_comando",
      "respuesta": "Usa git switch -, que vuelve a la referencia desde la que cambiaste [2].",
      "comando": "git switch -", "citas": [2]}),

    # --- conceptual: la pregunta pide entender algo, no ejecutar un comando ---
    (entrada("¿Qué es un conflicto de merge?",
             "Sucede cuando Git no puede combinar automáticamente ciertos cambios. Por ejemplo, dos personas "
             "editaron de forma incompatible la misma línea de config.py.",
             "Para resolver un conflicto durante un merge: abre el archivo en conflicto, decide la versión "
             "correcta o combina ambas y borra los marcadores."),
     {"tipo": "conceptual",
      "respuesta": "Es cuando Git no puede combinar automáticamente dos cambios, por ejemplo dos personas que "
                   "editaron la misma línea de un archivo [1].",
      "comando": None, "citas": [1]}),

    (entrada("¿Cuáles son los tres estados de un archivo en Git?",
             "Working directory: archivos que editas. Staging area: cambios preparados con git add. "
             "Repositorio local: commits creados con git commit.",
             "archivo editado --git add--> preparado --git commit--> historial; historial local --git push--> GitHub."),
     {"tipo": "conceptual",
      "respuesta": "Working directory, donde editas; staging area, con los cambios preparados con git add; y "
                   "repositorio local, con los commits [1]. Con git push el historial llega a GitHub [2].",
      "comando": None, "citas": [1, 2]}),

    (entrada("¿Cuál es la diferencia entre git reset y git revert?",
             "Si el commit es solamente local, reset puede servir para rehacerlo: git reset --soft HEAD~1 retira "
             "el commit y deja los cambios preparados.",
             "Si el commit ya fue compartido con tu equipo, es preferible crear un commit inverso con git revert."),
     {"tipo": "conceptual",
      "respuesta": "git reset retira commits y sirve cuando el commit es solo local [1]. git revert crea un "
                   "commit inverso y es lo preferible si el commit ya se compartió [2].",
      "comando": None, "citas": [1, 2]}),

    (entrada("¿Para qué sirve la opción -u al hacer push?",
             "Para publicar por primera vez la rama en GitHub: git push -u origin feature/modelo.",
             "La opción -u configura el seguimiento de la rama remota; después, normalmente basta con git push."),
     {"tipo": "conceptual",
      "respuesta": "Configura el seguimiento de la rama remota, para que después baste con git push [2].",
      "comando": None, "citas": [2]}),

    (entrada("¿Qué diferencia hay entre git stash apply y git stash pop?",
             "git stash guarda temporalmente cambios rastreados. git stash apply recupera sin borrar el stash; "
             "git stash pop lo elimina si se aplica correctamente.",
             "git stash push -u -m \"Trabajo pendiente\", git stash apply, git stash drop stash@{0}."),
     {"tipo": "conceptual",
      "respuesta": "git stash apply recupera los cambios sin borrar el stash, mientras que git stash pop lo "
                   "elimina si se aplica correctamente [1].",
      "comando": None, "citas": [1]}),

    # --- fuera_de_alcance: la guía no cubre la pregunta ---
    (entrada("¿Cuánto cuesta una licencia de GitHub Enterprise?",
             "Abre el repositorio en GitHub y selecciona Pull requests, New pull request.",
             "Crear un Pull Request por tarea y pedir revisión a otro integrante."),
     {"tipo": "fuera_de_alcance",
      "respuesta": "La guía no incluye información sobre precios de licencias de GitHub, así que no puedo responderlo.",
      "comando": None, "citas": []}),

    (entrada("¿Cómo configuro GitHub Actions para desplegar en AWS?",
             "git push publica esos commits en GitHub.",
             "Mantener el archivo README.md y las instrucciones de ejecución al día."),
     {"tipo": "fuera_de_alcance",
      "respuesta": "La guía no cubre GitHub Actions ni despliegues en AWS, así que no puedo responderlo con esta fuente.",
      "comando": None, "citas": []}),

    (entrada("¿Cómo migro un repositorio de SVN a Git?",
             "Primero se actualiza la rama principal. Luego se crea una rama nueva para cada tarea.",
             "git status muestra qué cambió."),
     {"tipo": "fuera_de_alcance",
      "respuesta": "La guía no trata la migración desde SVN, así que no puedo responderlo con esta fuente.",
      "comando": None, "citas": []}),

    (entrada("¿Qué es mejor, GitLab o GitHub?",
             "Git es el sistema de control de versiones; GitHub es la plataforma donde se aloja el repositorio remoto.",
             "Crear un Pull Request por tarea y pedir revisión a otro integrante."),
     {"tipo": "fuera_de_alcance",
      "respuesta": "La guía no compara plataformas como GitLab y GitHub, así que no puedo responderlo con esta fuente.",
      "comando": None, "citas": []}),
]

examples = [
    types.TuningExample(text_input=texto, output=json.dumps(salida, ensure_ascii=False))
    for texto, salida in ejemplos_raw
]


# ---------------------------------------------------------------------------
# Paso 2: balance entre categorías
# ---------------------------------------------------------------------------
def chequear_balance(ejemplos_raw: list[tuple[str, dict]], clave: str) -> Counter:
    return Counter(salida[clave] for _, salida in ejemplos_raw)


# ---------------------------------------------------------------------------
# Paso 3: validación antes de enviar nada
# ---------------------------------------------------------------------------
CLAVES = ("tipo", "respuesta", "comando", "citas")
TIPOS = {"con_comando", "conceptual", "fuera_de_alcance"}
PATRON_CORCHETE = re.compile(r"\[([^\]]*)\]")


def validar_dataset(examples: list[types.TuningExample], claves_esperadas: tuple[str, ...]) -> list[str]:
    """Validación estructural de la lección: vacíos, duplicados, JSON válido y claves."""
    problemas = []
    vistos = set()
    for i, ej in enumerate(examples):
        if not ej.text_input or not ej.text_input.strip():
            problemas.append(f"ejemplo {i}: text_input vacio")
        if not ej.output or not ej.output.strip():
            problemas.append(f"ejemplo {i}: output vacio")
            continue
        if ej.text_input in vistos:
            problemas.append(f"ejemplo {i}: text_input duplicado")
        vistos.add(ej.text_input)
        try:
            salida = json.loads(ej.output)
        except json.JSONDecodeError:
            problemas.append(f"ejemplo {i}: output no es JSON valido")
            continue
        for clave in claves_esperadas:
            if clave not in salida:
                problemas.append(f'ejemplo {i}: output no tiene la clave "{clave}"')
    return problemas


def validar_formato(examples: list[types.TuningExample]) -> list[str]:
    """Reglas propias del formato que queremos enseñar: si un output las rompe, el modelo
    aprendería exactamente el error que se busca corregir."""
    problemas = []
    for i, ej in enumerate(examples):
        try:
            salida = json.loads(ej.output)
        except (json.JSONDecodeError, TypeError):
            continue  # ya lo reporta validar_dataset
        if not all(c in salida for c in CLAVES):
            continue
        n_fragmentos = len(re.findall(r"^\[\d+\]", ej.text_input, re.MULTILINE))
        corchetes = PATRON_CORCHETE.findall(salida["respuesta"])
        if salida["tipo"] not in TIPOS:
            problemas.append(f'ejemplo {i}: tipo "{salida["tipo"]}" no permitido')
        if any(not c.strip().isdigit() for c in corchetes):
            problemas.append(f"ejemplo {i}: cita con formato distinto de [n]")
        citados = sorted({int(c) for c in corchetes if c.strip().isdigit()})
        if citados != sorted(salida["citas"]):
            problemas.append(f'ejemplo {i}: "citas" no coincide con las citas de la respuesta')
        if any(not 1 <= n <= n_fragmentos for n in citados):
            problemas.append(f"ejemplo {i}: cita un fragmento que no está en el contexto")
        if salida["tipo"] == "fuera_de_alcance" and salida["citas"]:
            problemas.append(f"ejemplo {i}: fuera_de_alcance no debe citar fuentes")
        if salida["tipo"] != "fuera_de_alcance" and not salida["citas"]:
            problemas.append(f"ejemplo {i}: respuesta sin citas")
        if (salida["tipo"] == "con_comando") != (salida["comando"] is not None):
            problemas.append(f'ejemplo {i}: "comando" debe venir solo cuando tipo es con_comando')
    return problemas


def validar_todo(examples: list[types.TuningExample]) -> list[str]:
    return validar_dataset(examples, claves_esperadas=CLAVES) + validar_formato(examples)


# ---------------------------------------------------------------------------
# Paso 4 (opcional): seguir el trabajo de tuning si se envía
# ---------------------------------------------------------------------------
def esperar_a_que_termine(client: genai.Client, nombre_trabajo: str, intervalo_segundos: int = 30) -> types.TuningJob:
    estados_finales = {
        types.JobState.JOB_STATE_SUCCEEDED,
        types.JobState.JOB_STATE_FAILED,
        types.JobState.JOB_STATE_CANCELLED,
        types.JobState.JOB_STATE_PARTIALLY_SUCCEEDED,
    }
    while True:
        trabajo = client.tunings.get(name=nombre_trabajo)
        print(f"estado actual: {trabajo.state}")
        if trabajo.state in estados_finales:
            return trabajo
        time.sleep(intervalo_segundos)


if __name__ == "__main__":
    print(len(examples), "ejemplos construidos")
    print(examples[0].output, "\n")

    print("=== Balance por tipo ===")
    balance = chequear_balance(ejemplos_raw, "tipo")
    for categoria, cuenta in balance.most_common():
        print(f"{categoria}: {cuenta}")
    assert max(balance.values()) / min(balance.values()) <= 2, "una categoría domina sobre las demás"

    print("\n=== Validación ===")
    problemas = validar_todo(examples)
    print(f"{len(examples)} ejemplos, {len(problemas)} problemas encontrados")
    for p in problemas:
        print(" -", p)
    assert not problemas, "corrige el dataset antes de enviarlo"
    assert len(examples) >= 10

    print("\n=== El validador detecta errores puestos a propósito ===")
    roto = json.loads(examples[1].output)
    roto["respuesta"] = roto["respuesta"].replace("[1]", "[1, 2]")       # el error real medido
    sin_clave = json.loads(examples[5].output)
    del sin_clave["citas"]
    casos_rotos = [
        types.TuningExample(text_input=examples[1].text_input, output=json.dumps(roto, ensure_ascii=False)),
        types.TuningExample(text_input=examples[5].text_input, output=json.dumps(sin_clave, ensure_ascii=False)),
        types.TuningExample(text_input=examples[0].text_input, output=examples[0].output),  # duplicado
    ]
    detectados = validar_todo(examples[:1] + casos_rotos)
    for p in detectados:
        print(" -", p)
    assert any("formato distinto de [n]" in p for p in detectados)
    assert any('no tiene la clave "citas"' in p for p in detectados)
    assert any("duplicado" in p for p in detectados)
    print("OK: el validador encuentra los tres errores")

    # Paso 4: el envío no se ejecuta. El tuning de la API de Gemini requiere Vertex AI y un bucket
    # de GCS (como en laboratorio_dataset.py); ver docs/decision_personalizacion.md, sección 4.
