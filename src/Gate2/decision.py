"""
Bloque 30 - Método de decisión de personalización aplicado al asistente RAG de Git/GitHub.

Paso 1: responde las cinco preguntas con evidencia del proyecto y puntúa RAG, fine-tuning y PEFT.
Paso 2: genera el esqueleto de docs/decision_personalizacion.md (solo si todavía no existe, para no
        pisar el documento ya completado a mano).
Extra:  análisis de sensibilidad (cambiar una respuesta a la vez) y costo de etiquetado.

Ejecutar desde la raíz del proyecto:  python src/Gate2/decision.py
"""
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DOCUMENTO = RAIZ / "docs" / "decision_personalizacion.md"
MUESTRA = json.loads((RAIZ / "docs" / "muestra_formato_respuestas.json").read_text(encoding="utf-8"))


def recomendar_estrategia(respuestas):
    puntos = {"RAG": 0, "Fine-tuning completo": 0, "PEFT": 0}
    if respuestas["informacion_cambia_seguido"]:
        puntos["RAG"] += 3
    if respuestas["problema_de_formato_o_tono"]:
        puntos["PEFT"] += 2
        puntos["Fine-tuning completo"] += 1
    if respuestas["dataset_grande_y_de_calidad"]:
        puntos["Fine-tuning completo"] += 2
        puntos["PEFT"] += 1
    if respuestas["presupuesto_limitado_o_iterar_rapido"]:
        puntos["RAG"] += 2
        puntos["PEFT"] += 1
    if respuestas["necesita_multiples_variantes"]:
        puntos["PEFT"] += 2
    maximo = max(puntos.values())
    ganadoras = [tecnica for tecnica, p in puntos.items() if p == maximo]
    return puntos, ganadoras


def estimar_costo_de_etiquetar(num_ejemplos, minutos_por_ejemplo, costo_por_hora):
    horas = (num_ejemplos * minutos_por_ejemplo) / 60
    return horas, horas * costo_por_hora


respuestas_mi_caso = {
    # La guía (único documento del corpus) se modificó una sola vez, el 2026-11-19, y no cambió
    # desde entonces (git log -- Guia_Git_GitHub_3_Usuarios.md). Umbral: >= 1 cambio por mes.
    "informacion_cambia_seguido": False,
    # 8 de 20 respuestas reales (40 %) incumplen el formato; umbral 3 de 20 (15 %).
    # Fuente: docs/muestra_formato_respuestas.json (python src/Gate2/muestra_formato.py)
    "problema_de_formato_o_tono": MUESTRA["incumplimientos"] >= 3,
    # 14 ejemplos etiquetados y validados (src/Gate2/dataset_tuning.py), muy lejos de 200.
    "dataset_grande_y_de_calidad": False,
    # Plan gratuito de Gemini (1000 embeddings/día, ya hubo un rate limit: docs/registro_rate_limit.md),
    # sin proyecto de facturación en Vertex AI, y el Gate 2 necesita ver el efecto en menos de un día.
    "presupuesto_limitado_o_iterar_rapido": True,
    # Un solo asistente, un idioma, una guía: no hay variantes por cliente ni por línea de producto.
    "necesita_multiples_variantes": False,
}


def generar_esqueleto_decision(problema, puntos, ganadoras):
    empate = len(ganadoras) > 1
    lineas = ["# Decision de personalizacion", "", "## 1. El problema", problema, "",
              "## 2. Resultado del metodo de decision"]
    for tecnica, p in sorted(puntos.items(), key=lambda x: -x[1]):
        lineas.append(f"- {tecnica}: {p} puntos")
    if empate:
        lineas += ["", f"**Empate entre: {', '.join(ganadoras)}**"]
    lineas += ["", "## 3. Tecnica elegida y por que"]
    if empate:
        lineas.append("[COMPLETAR: el puntaje no resolvio el empate solo -- justifica aqui con criterio propio]")
    else:
        lineas.append(f"[COMPLETAR: por que {ganadoras[0]} responde mejor a este caso]")
    lineas += ["", "## 4. Que necesitarias para ejecutarla",
               "[COMPLETAR: corpus faltante, o cantidad de ejemplos etiquetados que faltan]"]
    return "\n".join(lineas)


if __name__ == "__main__":
    if any(v is None for v in respuestas_mi_caso.values()):
        raise SystemExit("Completa las cinco respuestas con True o False antes de continuar.")

    puntos, ganadoras = recomendar_estrategia(respuestas_mi_caso)
    print("=== Paso 1: método de decisión ===")
    print(puntos)
    print("candidatas:", ganadoras)

    print("\n=== Sensibilidad: cambiar una respuesta a la vez ===")
    for clave in respuestas_mi_caso:
        variante = dict(respuestas_mi_caso, **{clave: not respuestas_mi_caso[clave]})
        puntos_v, ganadoras_v = recomendar_estrategia(variante)
        cambio = "CAMBIA" if set(ganadoras_v) != set(ganadoras) else "igual"
        print(f"{clave} -> {variante[clave]}: {puntos_v} {ganadoras_v} [{cambio}]")

    print("\n=== Costo de etiquetado para llegar a 100 ejemplos (tarifa de referencia del curso: 25 USD/h) ===")
    faltan = 100 - 14
    horas_base, costo_base = estimar_costo_de_etiquetar(faltan, 6, 25)
    horas_rev, costo_rev = estimar_costo_de_etiquetar(faltan * 0.20, 2, 25)
    print(f"etiquetado base: {faltan} ejemplos x 6 min = {horas_base:.2f} h, aprox ${costo_base:.2f}")
    print(f"segunda revision (20 %): {horas_rev:.2f} h, aprox ${costo_rev:.2f}")
    print(f"total: {horas_base + horas_rev:.2f} h ({(horas_base + horas_rev) / 8:.1f} jornadas), "
          f"aprox ${costo_base + costo_rev:.2f}")

    print("\n=== Paso 2: esqueleto del documento ===")
    esqueleto = generar_esqueleto_decision(
        "El asistente RAG de Git/GitHub no entrega sus respuestas con un formato consistente.",
        puntos, ganadoras,
    )
    if DOCUMENTO.exists():
        print(f"{DOCUMENTO.relative_to(RAIZ)} ya existe (completado a mano): no se sobrescribe.")
    else:
        DOCUMENTO.write_text(esqueleto, encoding="utf-8")
        print(esqueleto)
        print(f"\nesqueleto guardado en {DOCUMENTO.relative_to(RAIZ)}")
