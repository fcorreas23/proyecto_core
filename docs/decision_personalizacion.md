# Decisión de personalización: asistente RAG de Git/GitHub

## 1. El problema

El asistente responde con contenido correcto de la guía del equipo, pero no entrega las respuestas con un formato consistente. En una muestra de 20 respuestas reales, revisadas con 5 criterios fijos definidos antes de verlas, **8 (40 %) incumplen el formato** ([`muestra_formato_respuestas.json`](muestra_formato_respuestas.json)):

| Criterio | Fallas |
|---|---|
| C2: cada cita usa un solo número por corchete, `[1]`, como pide el prompt | **7 de 18** (escribe `[1, 3]` o `[1, 2, 3]`) |
| C1: cita al menos una fuente cuando la guía cubre la pregunta | 1 de 18 |
| C4: incluye el comando cuando la pregunta pide cómo hacer algo | 1 de 12 |
| C3: solo cita fragmentos que existen en el contexto | 0 de 18 |
| C5: declara que no sabe cuando la pregunta está fuera de la guía | 0 de 2 |

La falla de C2 no es cosmética: el servicio extrae las fuentes de las citas `[n]`, y con `[1, 2, 3]` dejaba de reconocerlas. Al modelo no le falta información, porque el contexto recuperado la trae. Lo que le falta es consistencia en la forma de entregarla.

## 2. Resultado del método de decisión

Respuestas con su evidencia (`python src/Gate2/decision.py`):

| Pregunta | Respuesta | Evidencia |
|---|---|---|
| ¿La información cambia seguido? | False | La guía se modificó una sola vez (2026-11-19) y no cambió desde entonces |
| ¿Problema de formato o tono? | True | 8 de 20 respuestas incumplen (umbral: 3 de 20) |
| ¿Dataset grande y de calidad? | False | 14 ejemplos etiquetados y validados, de 200 necesarios |
| ¿Presupuesto limitado o iterar rápido? | True | Plan gratuito de Gemini, sin facturación en Vertex AI, y el efecto se necesita en menos de un día |
| ¿Varias variantes del modelo? | False | Un solo asistente, un idioma, una guía |

**Puntaje: PEFT 3, RAG 2, fine-tuning completo 1. Gana PEFT, sin empate.**

Análisis de sensibilidad (cambiando una respuesta a la vez): solo dos respuestas cambian el resultado. Si la información cambiara seguido, ganaría RAG (5 a 3). Si **no** hubiera problema de formato, también ganaría RAG (2 a 1). Esa segunda es la respuesta más frágil: sin el criterio C2, las fallas bajan a 2 de 20, por debajo del umbral. Por eso el plan de la sección 3 vuelve a medirla antes de gastar en entrenamiento.

## 3. Técnica elegida y por qué

**Elijo PEFT para el formato de salida, sobre el RAG que ya está construido.** El problema medido es de comportamiento (cómo se citan las fuentes y si aparece el comando), que es lo que un adapter aprende. Fine-tuning completo queda descartado: con 14 ejemplos sobreajustaría, y cuesta más de entrenar para el mismo resultado.

RAG no se reemplaza. El método solo premia a RAG cuando la información cambia seguido, y la guía no cambia; pero el modelo base no conoce la guía de este equipo, y es el RAG el que le entrega ese contenido en cada consulta. El método no tiene una pregunta para "al modelo le falta conocimiento estable", así que la dejo explícita aquí. Es la combinación que describe el Bloque 29 para el bot de atención al cliente: RAG para el conocimiento y PEFT para el comportamiento.

Orden de ejecución: cada intento de tuning tarda de minutos a horas y el presupuesto alcanza para dos como máximo. Por eso, antes del primero, ajusto el prompt de sistema para prohibir explícitamente `[1, 2]`, lo que no cuesta nada y se itera al instante. Después vuelvo a medir con las mismas 20 preguntas. Si quedan 3 o más incumplimientos, entreno el adapter. Si no, PEFT queda aplazado y el método se vuelve a correr con la nueva evidencia.

Dos hallazgos de la muestra no se resuelven con personalización. La pregunta sobre los tres estados de un archivo falló porque el retriever no trajo la sección de la guía que la responde, y eso es un problema de recuperación (`k`, `chunk_size`). En la de volver a la rama anterior, el modelo respondió `git switch` en vez de `git switch -`, y los criterios automáticos no lo detectaron: es una limitación de la revisión, no del formato.

## 4. Qué necesitaría para ejecutarla

- **Ejemplos:** hoy tengo **14** etiquetados y validados (5 `con_comando`, 5 `conceptual`, 4 `fuera_de_alcance`), en [`src/Gate2/dataset_tuning.py`](../src/Gate2/dataset_tuning.py). Mi objetivo es **100**, unos 33 por tipo, así que **faltan 86**: 28 `con_comando`, 28 `conceptual` y 30 `fuera_de_alcance`.
- **Costo de etiquetado:** 86 ejemplos × 6 minutos (cada uno lleva un contexto real de la guía) = **8,6 horas**. Una segunda revisión del 20 % de los ejemplos, a 2 minutos cada uno, suma 0,57 horas. Total: **9,2 horas (1,1 jornadas), unos 229 USD** a la tarifa de referencia del curso, 25 USD/h.
- **Infraestructura:** un proyecto de Google Cloud con facturación y Vertex AI habilitado, y un bucket de GCS para el `.jsonl` de entrenamiento (como en `laboratorio_dataset.py`). Modelo base `gemini-2.5-flash`, modo `TUNING_MODE_PEFT_ADAPTER`, `ADAPTER_SIZE_FOUR`, 5 épocas. Hoy no tengo ninguno de los dos.
- **Intentos:** **2 como máximo**. Después de cada uno reviso `total_truncated_example_count` (tiene que ser 0) y los tokens facturables que informa la API.
- **Criterio de éxito:** menos de 3 incumplimientos en 20, medido con el mismo `python src/Gate2/muestra_formato.py`.
- **Cambio en el servicio:** `servicio_rag.py` tendría que leer la salida JSON del modelo (`respuesta`, `comando`, `citas`) en vez de buscar las citas con una expresión regular.
- **Corpus:** no falta nada que indexar. La guía completa ya está en el índice (147 chunks).
