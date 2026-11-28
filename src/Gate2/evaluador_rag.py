from pathlib import Path
import sys
from datetime import date
from rag_indexer import cargar_vectorstore


def precision_at_k(ids_recuperados: list[str], ids_relevantes: set[str]) -> float:
    """
    ids_recuperados los que me trajo el retriever
    De los 'k' chunks que me trajo el retriever, ¿qué fracción realmente sirve?
    Devuelve 0.0 si el retriever no devolvió ningún id
    """
    if not ids_recuperados:
        return 0.0
    
    #Recorro uno por uno cada ID que devolvió el retriever, si acaso existe en ids_relevantes lo agrego a la lista de acertados
    acertados = [i for i in ids_recuperados if i in ids_relevantes] 

    return len(acertados) / len(ids_recuperados)

def recall_at_k(ids_recuperados: list[str], ids_relevantes: set[str]) -> float | None:
    """
    Exhaustividad
    De todos los chunks relevantes que existen en mi corpus, ¿qué fracción logré rescatar?
    Devuelve None si la pregunta no tiene respuesta en corpus (ids_relevantes es vacío)
    """
    if not ids_relevantes:
        return None
    
    acertados = [i for i in ids_recuperados if i in ids_relevantes]
    return len(acertados) / len(ids_relevantes)

def f1_score(precision: float, recall: float | None) -> float:
    """
    Media armónica entre precisión y exhaustividad: equilibrio entre ambos para comparar
    configuraciones distintas de k o chunk_size.
    """
    if recall is None or (precision + recall) == 0:
        return 0.0
    
    return 2 * precision * recall / (precision + recall)

def evaluar_recuperacion(retriever, casos: list[dict], k: int = 3):
    """
    Correr cada caso del conjunto de evaluaciones contra el retriever real de Chroma
    y va a calcular precisión, recall y F1
    """
    resultados = []

    for caso in casos:
        #1.- Consultamos al retriever, cuáles son los chunks que me regresa la invocación. SI GASTA TOKENS
        chunks = retriever.invoke(caso["pregunta"])

        #2.- Extraer los IDs
        ids_recuperados = [c.id for c in chunks]

        #3.- Calculamos las métricas
        p = precision_at_k(ids_recuperados, caso["ids_relevantes"])
        r = recall_at_k(ids_recuperados, caso["ids_relevantes"])
        f1 = f1_score(p, r)

        #4.- Agregar esas métricas a los resultados
        resultados.append({
            "pregunta": caso["pregunta"],
            "ids_recuperados": ids_recuperados,
            "precision": p,
            "recall": r,
            "f1": f1
        })
    
    return resultados

def guardar_reporte(ruta_archivo: str, resultados: list[dict], k: int, chunk_size: int = 200, chunk_overlap: int = 30):
    """Guarda el registro en un .txt para compararlo cuando cambies k o chunk_size."""
    with open(ruta_archivo, "w", encoding="utf-8") as archivo:
        archivo.write(f"Fecha: {date.today()}\n")
        archivo.write(f"Configuracion: k={k}, chunk_size={chunk_size}, chunk_overlap={chunk_overlap}\n\n")

        for r in resultados:
            recall_txt = "n/a" if r["recall"] is None else f"{r['recall']:.2f}"
            archivo.write(f"P={r['precision']:.2f} | R={recall_txt} | F1={r['f1']:.2f} | {r['pregunta']}\n")

        # Promedios: un solo número para comparar configuraciones (k, chunk_size).
        # El recall se promedia solo sobre preguntas que SÍ tienen respuesta.
        prom = promedios(resultados)
        archivo.write(f"\nPROMEDIO | P={prom['precision']:.2f} | R={prom['recall']:.2f} | F1={prom['f1']:.2f}\n")
    print(f"\nReporte guardado en '{ruta_archivo}'")

def promedios(resultados: list[dict]) -> dict:
    """Promedio de cada métrica. Las preguntas sin respuesta en el corpus
    (recall None) no cuentan para recall ni F1, porque ahí no hay nada que rescatar."""
    con_respuesta = [r for r in resultados if r["recall"] is not None]
    return {
        "precision": sum(r["precision"] for r in con_respuesta) / len(con_respuesta),
        "recall": sum(r["recall"] for r in con_respuesta) / len(con_respuesta),
        "f1": sum(r["f1"] for r in con_respuesta) / len(con_respuesta),
    }


# ---------------------------------------------------------------------------
# Conjunto de evaluación sobre Guia_Git_GitHub_3_Usuarios.md
#
# Los ids salen de rag_indexer.generar_ids: "<archivo>_<n>", con n = posición
# del chunk usando chunk_size=200 y chunk_overlap=30. Si cambias esa
# configuración al indexar, los chunks se parten distinto y HAY QUE volver
# a etiquetar estos ids.
# ---------------------------------------------------------------------------
G = "Guia_Git_GitHub_3_Usuarios_"

CASOS_EVALUACION = [
    # Sección 8: conflictos
    {
        "pregunta": "¿Cómo se resuelve un conflicto de merge?",
        "ids_relevantes": {
            G + "40",  # Qué es un conflicto: Git no puede combinar cambios
            G + "41",  # Ejemplo de marcadores <<<<<<< ======= >>>>>>>
            G + "42",  # Pasos: abrir, decidir, borrar marcadores, completar merge
            G + "43",  # git add / commit / push tras resolver
        },
    },
    # Sección 23: deshacer un commit ya compartido
    {
        "pregunta": "¿Cómo deshago un commit que ya compartí con mi equipo?",
        "ids_relevantes": {
            G + "124",  # Si el commit ya fue compartido, usar git revert
            G + "125",  # git revert HEAD
            G + "127",  # Evitar reset y push --force en commits compartidos
            G + "140",  # Tabla: deshacer un commit compartido -> git revert HEAD
        },
    },
    # Sección 22: stash
    {
        "pregunta": "¿Cómo guardo temporalmente mis cambios para cambiar de rama sin perderlos?",
        "ids_relevantes": {
            G + "117",  # git stash push -m / list / pop
            G + "118",  # Qué hacen stash apply y stash pop
            G + "120",  # stash push -u, apply, drop
            G + "139",  # Tabla: guardar cambios temporalmente
        },
    },
    # Sección 9: fetch vs pull
    {
        "pregunta": "¿Qué diferencia hay entre git fetch y git pull?",
        "ids_relevantes": {
            G + "51",  # git fetch vs git pull
            G + "61",  # Tabla de comandos: pull origin main / fetch origin
        },
    },
    # Sección 6: Pull Request
    {
        "pregunta": "¿Qué significan base y compare al abrir un Pull Request?",
        "ids_relevantes": {
            G + "31",  # Pasos: base: main y compare: feature/modelo
            G + "35",  # Definición de base y compare
        },
    },
    # Sección 24: reflog
    {
        "pregunta": "¿Cómo recupero un commit que perdí después de un reset?",
        "ids_relevantes": {
            G + "128",  # git reflog + crear rama desde el hash
            G + "129",  # Qué muestra reflog y sus límites
            G + "140",  # Tabla: buscar commits perdidos -> git reflog
        },
    },
    # Pregunta SIN respuesta en el corpus: ids_relevantes vacío -> recall n/a.
    # Sirve para ver qué trae el retriever cuando no hay nada útil.
    {
        "pregunta": "¿Cuánto cuesta una licencia de GitHub Enterprise?",
        "ids_relevantes": set(),
    },
]


if __name__ == "__main__":
    CARPETA_DB = "vectorstore/"
    K = 3

    vs = cargar_vectorstore(CARPETA_DB)

    # 1. El índice no puede estar vacío (pasa si la reindexación falló).
    total = vs._collection.count()
    if total == 0:
        sys.exit(f"'{CARPETA_DB}' está vacío. Corre primero: python src/Gate2/rag_indexer.py")

    # 2. Los ids etiquetados deben existir en el índice. Si no, el índice se
    #    armó con otro corpus o con otro chunk_size y las métricas darían 0
    #    sin que sea culpa del retriever. (Esta consulta NO gasta tokens.)
    etiquetados = set().union(*(c["ids_relevantes"] for c in CASOS_EVALUACION))
    existentes = set(vs._collection.get(ids=list(etiquetados))["ids"])
    faltantes = etiquetados - existentes
    if faltantes:
        sys.exit(f"Estos ids etiquetados no están en el índice: {sorted(faltantes)}\n"
                 "Reindexa la guía con chunk_size=200 y chunk_overlap=30.")
    print(f"Índice OK: {total} chunks, los {len(etiquetados)} ids etiquetados existen.")

    # 3. Evaluar. Cada pregunta gasta 1 embedding (cuota gratuita: 100/min, 1000/día).
    retriever = vs.as_retriever(search_kwargs={"k": K})
    resultados = evaluar_recuperacion(retriever, CASOS_EVALUACION, K)

    for r in resultados:
        recall_txt = "n/a" if r["recall"] is None else f"{r['recall']:.2f}"
        print(f"\nP={r['precision']:.2f} | R={recall_txt} | F1={r['f1']:.2f} | {r['pregunta']}")
        print("   recuperados:", r["ids_recuperados"])

    prom = promedios(resultados)
    print(f"\nPROMEDIO | P={prom['precision']:.2f} | R={prom['recall']:.2f} | F1={prom['f1']:.2f}")

    guardar_reporte(Path(__file__).resolve().parents[2] / "docs" / "resultados_evaluacion_rag.txt", resultados, K)

    """
    Precisión: Fórmula: Verdaderos Positivos / (Verdaderos Positivos + Falsos Positivos)

    Exhaustividad (recall):
    Fórmula: Verdaderos Positivos / (Verdaderos Positivos + Falsos Negativos)

    Ojo: con k=3 y 4 chunks relevantes, el recall máximo posible es 3/4 = 0.75.
    """

