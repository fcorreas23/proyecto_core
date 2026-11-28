"""
Bloque 30 - Evidencia para la pregunta "problema_de_formato_o_tono" del método de decisión.

Toma 20 respuestas reales del flujo RAG (índice real + Gemini) y las revisa con una lista FIJA
de criterios, definida antes de ver las respuestas:

  C1 cita_presente   - si la pregunta está cubierta por la guía, cita al menos una fuente [n]
  C2 formato_cita    - cada cita usa el formato pedido en el prompt: un número por corchete, [1]
                       (no "[1, 2]", "[1-3]" ni "[fuente]"): es lo que parsea el servicio
  C3 citas_validas   - todo número citado existe en el contexto entregado (1..k)
  C4 incluye_comando - si la pregunta pide cómo hacer algo, la respuesta trae el comando git
  C5 declara_limite  - si la pregunta NO está cubierta por la guía, lo dice en vez de inventar

Una respuesta "incumple" si falla cualquiera de los criterios que le aplican.
Umbral del curso: 3 o más incumplimientos en 20 (15 %) -> problema_de_formato_o_tono = True.

Costo: 20 embeddings + 20 llamadas al modelo.
Resultado: docs/muestra_formato_respuestas.json (sin el texto de las respuestas, solo huellas).

Ejecutar desde la raíz del proyecto:  python src/Gate2/muestra_formato.py
"""
import json
import logging
import re
import time
from datetime import date
from pathlib import Path

from log_rag import generar_huella, logger
from logging_rag import consulta_real
from rag_indexer import cargar_vectorstore

RAIZ = Path(__file__).resolve().parents[2]
ARCHIVO_RESULTADO = RAIZ / "docs" / "muestra_formato_respuestas.json"
K = 3
PAUSA_S = 5  # margen para el límite de peticiones por minuto del plan gratuito

# (pregunta, cubierta_por_la_guia, requiere_comando)
MUESTRA = [
    ("¿Cómo creo una rama nueva y me cambio a ella?", True, True),
    ("¿Cómo subo mis commits al repositorio remoto?", True, True),
    ("¿Qué hago antes de empezar a trabajar cada día?", True, True),
    ("¿Cómo actualizo mi rama después de que se hizo un merge en main?", True, True),
    ("¿Cómo se resuelve un conflicto de merge?", True, False),
    ("¿Qué es un Pull Request y para qué sirve?", True, False),
    ("¿Cómo veo qué archivos modifiqué antes de hacer commit?", True, True),
    ("¿Cómo veo el historial de commits de forma resumida?", True, True),
    ("¿Cómo descarto los cambios de un archivo que todavía no agregué con add?", True, True),
    ("¿Cómo guardo temporalmente mis cambios para cambiar de rama sin perderlos?", True, True),
    ("¿Cómo deshago un commit que ya compartí con mi equipo?", True, True),
    ("¿Cuál es la diferencia entre git reset y git revert?", True, False),
    ("¿Cómo recupero un commit que perdí después de un reset?", True, True),
    ("¿Cómo comparo mi rama con main antes de abrir un Pull Request?", True, True),
    ("¿Cuáles son los tres estados de un archivo en Git?", True, False),
    ("¿Cómo debería escribir un buen mensaje de commit?", True, False),
    ("¿Qué reglas de colaboración se recomiendan para el equipo?", True, False),
    ("¿Cómo vuelvo a la rama en la que estaba antes?", True, True),
    ("¿Cuánto cuesta una licencia de GitHub Enterprise?", False, False),
    ("¿Cómo configuro un pipeline de GitHub Actions para desplegar en AWS?", False, False),
]

PATRON_GRUPO_CITA = re.compile(r"\[([^\]]*\d[^\]]*)\]")      # cualquier corchete que contenga un número
PATRON_CITA_SIMPLE = re.compile(r"^\s*\d+\s*$")             # el formato pedido: [n]
PATRON_COMANDO = re.compile(r"\bgit\s+[a-z-]+")
PATRON_LIMITE = re.compile(
    r"no (?:tengo|encuentro|hay|se (?:menciona|encuentra|incluye)|contiene|alcanza|incluye|menciona|"
    r"proporciona|permite|cubre|aborda|especifica)|insuficiente|fuera del (?:alcance|contexto)",
    re.IGNORECASE,
)


def evaluar(texto: str, cubierta: bool, requiere_comando: bool, n_citas: int) -> dict:
    grupos = PATRON_GRUPO_CITA.findall(texto)
    numeros = [int(n) for g in grupos for n in re.findall(r"\d+", g)]
    criterios = {}
    if cubierta:
        criterios["C1_cita_presente"] = bool(grupos)
        criterios["C2_formato_cita"] = all(PATRON_CITA_SIMPLE.match(g) for g in grupos)
        criterios["C3_citas_validas"] = all(1 <= n <= n_citas for n in numeros)
        if requiere_comando:
            criterios["C4_incluye_comando"] = bool(PATRON_COMANDO.search(texto))
    else:
        criterios["C5_declara_limite"] = bool(PATRON_LIMITE.search(texto))
    return criterios


if __name__ == "__main__":
    vs = cargar_vectorstore(str(RAIZ / "vectorstore"))
    if vs._collection.count() == 0:
        raise SystemExit("El índice está vacío. Corre primero: python src/Gate2/servicio_rag.py --reindexar")

    # Los logs JSON siguen yendo a docs/rag_logs.jsonl; en consola solo se muestra la revisión.
    logger.handlers = [h for h in logger.handlers if not isinstance(h, logging.StreamHandler)
                       or isinstance(h, logging.FileHandler)]

    filas = []
    for i, (pregunta, cubierta, requiere_comando) in enumerate(MUESTRA, start=1):
        if i > 1:
            time.sleep(PAUSA_S)
        resultado = consulta_real(vs, pregunta, K)
        texto = resultado["respuesta"] or ""
        criterios = evaluar(texto, cubierta, requiere_comando, len(resultado["citas"]))
        cumple = all(criterios.values())
        filas.append({
            "pregunta": pregunta, "cubierta_por_la_guia": cubierta, "requiere_comando": requiere_comando,
            "criterios": criterios, "cumple": cumple,
            "respuesta_len": len(texto), "respuesta_hash": generar_huella(texto),
        })
        fallas = [c for c, ok in criterios.items() if not ok]
        print(f"\n[{i:2}] {'OK  ' if cumple else 'FALLA'} {pregunta}  {fallas or ''}")
        print("     " + texto.replace("\n", "\n     ")[:600])

    incumplimientos = sum(not f["cumple"] for f in filas)
    por_criterio = {}
    for f in filas:
        for c, ok in f["criterios"].items():
            por_criterio.setdefault(c, [0, 0])
            por_criterio[c][0] += (not ok)
            por_criterio[c][1] += 1
    resumen = {
        "fecha": str(date.today()), "k": K, "n_respuestas": len(filas),
        "incumplimientos": incumplimientos,
        "porcentaje": round(100 * incumplimientos / len(filas), 1),
        "problema_de_formato_o_tono": incumplimientos >= 3,
        "fallas_por_criterio": {c: f"{m} de {t}" for c, (m, t) in por_criterio.items()},
        "respuestas": filas,
    }
    ARCHIVO_RESULTADO.write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{incumplimientos} de {len(filas)} respuestas incumplen ({resumen['porcentaje']} %)")
    print("fallas por criterio:", resumen["fallas_por_criterio"])
    print("problema_de_formato_o_tono =", resumen["problema_de_formato_o_tono"])
    print("guardado en", ARCHIVO_RESULTADO.relative_to(RAIZ))
