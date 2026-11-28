# Registro del ensayo funcional del Gate 2

**Fecha:** 2026-11-28
**Comando:** `python src/Gate2/servicio_rag.py --simulado` y `python -m pytest test_gate2.py -v`
**Alcance:** indexar → recuperar → filtrar inyección → generar → citar → registrar logs, consumo, latencia y costo → supervisión humana.

## Hallazgos y correcciones

| # | Encontrado | Corregido |
|---|---|---|
| 1 | `prevencion_prompt_inyection.py` y `versionando_prompt_langgraph.py` importaban `from Gate2.log_rag`. Funcionaba ejecutando desde `src/`, pero desde la raíz del proyecto daba `ModuleNotFoundError: No module named 'Gate2'`. | Se cambió a `from log_rag import ...`, igual que el resto de los módulos de `src/Gate2`. |
| 2 | El índice real (`vectorstore/` en la raíz, 147 chunks) no existía. En su lugar había un `src/Gate2/vectorstore` con 5 chunks de demostración, creado por un script con ruta relativa ejecutado desde `src/Gate2`. | `servicio_rag.py` usa rutas absolutas a la raíz del proyecto (`vectorstore/`), así que el índice queda en el mismo lugar sin importar desde dónde se ejecute. |
| 3 | `registro_rag.py` guardaba en `docs/registros_latencia_costo.jsonl` la pregunta y la respuesta completas en texto plano (criterio no compensable de logs). | Ahora guarda `pregunta_len`/`pregunta_hash` y `respuesta_len`/`respuesta_hash`. Las 4 corridas reales existentes se convirtieron al mismo formato, conservando latencia, tokens y costo. |
| 4 | `langgraph` no estaba en `requirements.txt`: en un entorno limpio el punto de supervisión fallaba al importar. | Agregado `langgraph==1.2.24`. |
| 5 | El logger del proyecto usa `propagate=False`, por lo que la prueba de logs de la plantilla (`caplog`) no capturaba ningún registro y pasaba sin verificar nada. | `test_gate2.py` conecta `caplog` y un archivo JSON directamente al logger, y exige que haya registros capturados. Se comprobó que la prueba falla si se loguea la pregunta completa. |
| 6 | Con embeddings simulados, `rag_indexer.indexar_corpus` igual esperaba 61 s entre lotes (pausa pensada para el límite de la API). | La pausa solo se aplica con los embeddings reales de Gemini. |
| 7 | Desacople `d.contenido` vs `d.page_content` (el caso de la guía). | No ocurrió: el filtro de `logging_rag.py` ya trabajaba sobre `Document.page_content`. |
| 8 | En la primera corrida real, Gemini citó `[1, 2, 3]` en vez de `[1]`: `fuentes_citadas` no reconocía ese formato y caía al respaldo de listar todo el contexto. | `fuentes_citadas` ahora entiende listas dentro del corchete. La inconsistencia se midió en 20 respuestas (7 de 18 la tienen) y es la evidencia de `docs/decision_personalizacion.md`. |

## Resultado tras las correcciones

- Modo simulado: el servicio corre de punta a punta sin `Traceback`, la respuesta termina con `Fuentes: Guia_Git_GitHub_3_Usuarios.md`, todos los eventos de la consulta comparten un `trace_id` y ningún log contiene la pregunta ni la respuesta.
- Reindexar el corpus mantiene 147 chunks (los ids fijos reemplazan, no duplican).
- Supervisión: el grafo se pausa con `__interrupt__`; con `--aprobar` activa la versión `87b6ec1a4f9c` y sin decisión en una terminal no interactiva la rechaza.
- `python -m pytest test_gate2.py -v`: 4 passed.
- Corrida real (2026-11-28): índice regenerado con 147 chunks en 67 s, respuesta con `git revert HEAD` y su fuente, latencia total 2,3 s y costo estimado 0,0003 USD.
