"""
Gate 2 - Autoevaluación con la rúbrica: promedio ponderado + criterios no compensables.

PROPUESTA DE PUNTAJES: revisa cada número y ajústalo con tu propia estimación honesta.

Ejecutar desde la raíz del proyecto:  python src/Gate2/rubrica_gate2.py
"""

pesos = {
    "pipeline_funcional": 0.25, "recuperacion_citacion": 0.15,
    "costo_latencia": 0.10, "personalizacion": 0.15,
    "observabilidad": 0.15, "seguridad_gobernanza": 0.20,
}

mi_puntaje = {
    # servicio_rag.py corre de punta a punta, simulado y real (índice de 147 chunks regenerado, 2026-11-28)
    "pipeline_funcional": 90,
    # citas [n] -> archivo fuente en cada respuesta; P=0.67 R=0.69 F1=0.66 (docs/resultados_evaluacion_rag.txt)
    "recuperacion_citacion": 75,
    # 4 corridas reales con latencia/tokens/costo (docs/registros_latencia_costo.jsonl) + costo por consulta en el servicio
    "costo_latencia": 85,
    # decisión con evidencia medida (8/20 respuestas fallan formato), sensibilidad y costos (Bloque 30) +
    # dataset de 14 ejemplos validado (Bloque 29); el tuning no se ejecutó (requiere Vertex AI)
    "personalizacion": 80,
    # logs JSON con trace_id en cada etapa, consumo por consulta, registro del ensayo (Bloque 31)
    "observabilidad": 90,
    # filtro de inyección + huellas en logs + versionado + supervisión + matriz de riesgos (Bloques 31-32)
    "seguridad_gobernanza": 90,
}

# Verificados con: python -m pytest test/test_gate2.py -v  (4 passed)
no_compensables = {
    "pipeline_corre_de_punta_a_punta": True,
    "respuestas_citan_fuente": True,
    "logs_sin_contenido_crudo": True,
    "supervision_humana_funciona": True,
}


def promedio_ponderado(puntajes, pesos):
    return sum(puntajes[d] * pesos[d] for d in pesos)


def evaluar_gate(puntajes, no_compensables_ok, umbral=80):
    promedio = promedio_ponderado(puntajes, pesos)
    return promedio, promedio >= umbral and no_compensables_ok


if __name__ == "__main__":
    assert abs(sum(pesos.values()) - 1.0) < 1e-9, "los pesos deben sumar 1.0"
    todos_ok = all(no_compensables.values())
    promedio, aprueba = evaluar_gate(mi_puntaje, todos_ok)

    for dimension, peso in pesos.items():
        print(f"{dimension:24} {mi_puntaje[dimension]:3} x {peso:.2f} = {mi_puntaje[dimension] * peso:5.2f}")
    print(f"\npromedio: {promedio:.1f}, no compensables OK? {todos_ok} -> aprueba? {aprueba}")
    for criterio, ok in no_compensables.items():
        if not ok:
            print("  falla no compensable:", criterio)
