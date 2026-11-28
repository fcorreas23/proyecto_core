def puntaje_riesgo(probabilidad, impacto):
    return probabilidad * impacto


def categoria_riesgo(puntaje):
    if puntaje >= 15:
        return "CRITICO"
    if puntaje >= 9:
        return "ALTO"
    if puntaje >= 4:
        return "MEDIO"
    return "BAJO"


def esta_en_el_limite(probabilidad, impacto):
    """True si mover probabilidad o impacto en un punto cambia la categoría."""
    categoria_actual = categoria_riesgo(puntaje_riesgo(probabilidad, impacto))
    vecinos = [
        (probabilidad + 1, impacto), (probabilidad - 1, impacto),
        (probabilidad, impacto + 1), (probabilidad, impacto - 1),
    ]
    for p2, i2 in vecinos:
        if not (1 <= p2 <= 5 and 1 <= i2 <= 5):
            continue
        if categoria_riesgo(puntaje_riesgo(p2, i2)) != categoria_actual:
            return True
    return False


mis_riesgos = [
    {"riesgo": "Agente de envios ejecuta generar_reembolso con un monto inducido por el usuario en la conversacion",
     "probabilidad": 3,  # el usuario controla el texto y el modelo elige los argumentos de la herramienta
     "impacto": 5,       # en un sistema real mueve dinero y un reembolso pagado no se revierte solo
     "mitigacion": "Validacion Pydantic de argumentos + aprobacion previa con timeout de 15 s "
                   "(Unidad 2.4: agente_con_memoria.py, docs/limites_autonomia_agente.md)",
     "supervision": "Aprobacion humana obligatoria antes de cada reembolso; sin respuesta en 15 s se rechaza"},

    {"riesgo": "Inyeccion indirecta via un documento Markdown agregado al corpus e indexado en el vectorstore",
     "probabilidad": 3,  # hoy el corpus es una guia propia, pero se pueden sumar archivos externos
     "impacto": 4,       # podria revelar el prompt de sistema o desviar las respuestas a todos los usuarios
     "mitigacion": "Separacion de roles + delimitacion <contexto> + filtro de patrones por chunk con log "
                   "del descarte (Bloque 31: prevencion_prompt_inyection.py, logging_rag.py)",
     "supervision": "Si el filtro descarta un chunk, auditar_vectorstore() lo lista y una persona revisa "
                    "el archivo fuente antes de volver a indexar"},

    {"riesgo": "Cambio del prompt de sistema desplegado sin revision elimina la instruccion anti-inyeccion o el formato de citas [n]",
     "probabilidad": 3,  # el prompt ya cambio una vez en este proyecto (v1 -> v2)
     "impacto": 4,       # se pierde una capa de defensa sin que nadie lo note
     "mitigacion": "RegistroDePrompts con huella sha256 + diff entre versiones "
                   "(Bloque 32: registro_prompts.py)",
     "supervision": "interrupt() en grafo_supervision.py: una persona aprueba la huella nueva antes de activarla"},

    {"riesgo": "API key de Gemini expuesta al subir .env o credentials.json al repositorio de GitHub",
     "probabilidad": 2,  # ambos archivos estan en .gitignore, pero un git add -f o un rename los saltaria
     "impacto": 5,       # consumo a nombre propio y rotacion obligatoria de la clave
     "mitigacion": ".gitignore excluye .env y credentials.json; .env.example versionado sin valores",
     "supervision": "Revisar git status y el diff antes de cada push; rotar la clave si aparece en un commit"},

    {"riesgo": "Respuesta con una cita [n] que no respalda la afirmacion cuando el contexto recuperado no alcanza",
     "probabilidad": 3,  # con k=3 y chunks de 200 caracteres a veces falta contexto
     "impacto": 3,       # el usuario confia en la cita y ejecuta un comando de Git equivocado
     "mitigacion": "El prompt exige citar y declarar falta de contexto; evaluador_rag.py mide la "
                   "recuperacion contra ids etiquetados (docs/resultados_evaluacion_rag.txt)",
     "supervision": "Revision manual de una muestra de respuestas con sus citas antes de cambiar k o chunk_size"},

    {"riesgo": "Agotar la cuota gratuita de Gemini por reintentos o consultas repetidas",
     "probabilidad": 3,  # ya ocurrio un rate limit (docs/registro_rate_limit.md)
     "impacto": 2,       # el servicio se detiene unas horas; no hay costo ni perdida de datos
     "mitigacion": "registrar_consumo() con tokens por trace_id (Bloque 31: logging_rag.py) + "
                   "registro de latencia y costo por consulta (registro_rag.py)",
     "supervision": None},

    {"riesgo": "Chunks duplicados o desactualizados en el vectorstore despues de reindexar la guia",
     "probabilidad": 2,  # la reindexacion es manual y poco frecuente
     "impacto": 2,       # respuestas repetidas o con informacion vieja, sin exponer datos
     "mitigacion": "ids fijos por chunk que reemplazan en vez de duplicar + verificar_integridad() "
                   "(Bloque 25: rag_indexer.py)",
     "supervision": None},
]

for r in mis_riesgos:
    r["puntaje"] = puntaje_riesgo(r["probabilidad"], r["impacto"])
    r["categoria"] = categoria_riesgo(r["puntaje"])
    r["al_limite"] = esta_en_el_limite(r["probabilidad"], r["impacto"])


if __name__ == "__main__":
    print("=== Matriz de riesgos (ordenada por puntaje) ===")
    for r in sorted(mis_riesgos, key=lambda x: -x["puntaje"]):
        marca = "[AL LIMITE]" if r["al_limite"] else ""
        print(f"{r['categoria']:8} ({r['puntaje']:2}) - {r['riesgo']} {marca}")

    print("\n=== Revisar con otra persona antes de cerrar ===")
    for r in mis_riesgos:
        if r["al_limite"]:
            print("revisar con otra persona:", r["riesgo"])

    print("\n=== Puntos de supervisión de los riesgos ALTO y CRITICO ===")
    for r in sorted(mis_riesgos, key=lambda x: -x["puntaje"]):
        if r["categoria"] in ("ALTO", "CRITICO"):
            print(f"- {r['riesgo']}\n    -> {r['supervision']}")

    # Reglas de la actividad
    assert len(mis_riesgos) >= 5, "la matriz necesita al menos cinco riesgos"
    assert any(r["categoria"] in ("ALTO", "CRITICO") for r in mis_riesgos), "revisa si subestimas algún riesgo"
    assert all(r["supervision"] for r in mis_riesgos if r["categoria"] in ("ALTO", "CRITICO")), \
        "todo riesgo ALTO o CRITICO necesita un punto de supervisión"
    assert sum("Bloque" in r["mitigacion"] for r in mis_riesgos) >= 2, \
        "al menos dos mitigaciones deben apuntar a algo construido, con su número de bloque"
    assert len({r["categoria"] for r in mis_riesgos}) > 1, "todos en la misma categoría: revisa cada fila por separado"
