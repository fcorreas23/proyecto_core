# Proyecto Core — Servicio RAG (Gate 2)

Asistente que responde preguntas sobre Git y GitHub usando como única fuente la guía
[`Guia_Git_GitHub_3_Usuarios.md`](Guia_Git_GitHub_3_Usuarios.md). Cada respuesta cita el archivo
del que salió la información, cada consulta deja una traza JSON auditable (sin guardar el texto de
la pregunta ni de la respuesta), y desplegar una versión nueva del prompt de sistema requiere
aprobación humana.

Funciona con Gemini (embeddings `gemini-embedding-001` y modelo `gemini-3.5-flash-lite`) o en
**modo simulado**, sin API key ni costo.

## 1. Instalación

Requiere Python 3.10 o superior.

```bash
git clone https://github.com/fcorreas23/proyecto_core.git
cd proyecto_core

python3 -m venv .venv
source .venv/bin/activate          # Windows (PowerShell): .venv\Scripts\Activate.ps1
pip install -r requirements.txt

cp .env.example .env               # Windows (PowerShell): Copy-Item .env.example .env
```

Abre `.env` y completa `GEMINI_API_KEY`. El archivo está en `.gitignore`: nunca lo subas
(`git check-ignore .env` debe imprimir `.env`).

Todos los comandos de este README se ejecutan **desde la raíz del proyecto**.

## 2. Verificar el entorno

```bash
python src/Gate2/verificar_entorno.py
```

Muestra la versión de cada dependencia, si `GEMINI_API_KEY` está definida (nunca la imprime) y si el
índice existe. Termina con `Entorno listo para la corrida final` o con una línea `Pendiente:` que dice
qué falta.

## 3. Indexar el corpus

```bash
python src/Gate2/servicio_rag.py --reindexar
```

Divide la guía en 147 chunks (200 caracteres, solapamiento 30) y los guarda en `vectorstore/`. Tarda
unos 2 minutos: el plan gratuito permite 100 embeddings por minuto, así que se indexa en dos lotes.
Cada chunk tiene un id fijo (`Guia_Git_GitHub_3_Usuarios_<n>`), por lo que volver a indexar reemplaza
los chunks en vez de duplicarlos.

No hace falta repetirlo: el índice queda persistido y el servicio lo reutiliza. Si la carpeta está
vacía, la primera consulta lo crea automáticamente.

## 4. Hacer una consulta

```bash
python src/Gate2/servicio_rag.py "¿Cómo deshago un commit que ya compartí con mi equipo?"
```

| Opción | Qué hace |
|---|---|
| *(sin pregunta)* | Usa una pregunta de ejemplo. |
| `--simulado` | Embeddings y modelo simulados: no llama a la API (índice aparte en `vectorstore_simulado/`). |
| `--reindexar` | Vuelve a indexar el corpus antes de responder. |
| `--aprobar` / `--rechazar` | Decisión del punto de supervisión sin preguntar por consola. |

La salida tiene tres partes:

1. **Logs JSON**, uno por etapa, todos con el mismo `trace_id`: recuperación, filtro de inyección,
   llamada al modelo, tokens consumidos, latencia y costo estimado. También se guardan en
   `docs/rag_logs.jsonl`.
2. **La respuesta**, con citas `[n]` y una línea final `Fuentes: <archivo>`.
3. **El punto de supervisión humana**: el grafo propone activar la versión nueva del prompt, se
   pausa y pregunta `¿Aprobar el despliegue? [s/N]`. Sin terminal interactiva, y sin `--aprobar`,
   rechaza por seguridad.

Si la API falla (cuota, conexión, clave), el servicio no se cae: registra el tipo de error y
responde con un mensaje claro.

## 5. Pruebas

```bash
python -m pytest test/test_gate2.py -v    # los 4 criterios no compensables del Gate 2 (sin API)
python -m pytest                          # todas las pruebas de la carpeta test/
```

`test/test_gate2.py` verifica, sobre el servicio real en modo simulado: que el pipeline responde sin
excepciones, que la respuesta cita su fuente, que un correo incluido en la pregunta no aparece en
ningún log, y que el grafo de supervisión se pausa y retoma con la decisión (aprobación y rechazo).

## 6. Dónde está cada pieza de la rúbrica

| Dimensión | Código | Evidencia |
|---|---|---|
| Pipeline RAG funcional (25 %) | `src/Gate2/servicio_rag.py`, `rag_indexer.py` | `docs/registro_ensayo_gate2.md`, `test/test_gate2.py` |
| Recuperación y citación (15 %) | `rag_indexer.py` (`formatear_contexto`), `evaluador_rag.py` | `docs/resultados_evaluacion_rag.txt` (P=0.67, R=0.69, F1=0.66) |
| Costo y latencia (10 %) | `registro_rag.py`, evento `latencia_costo` del servicio | `docs/registros_latencia_costo.jsonl` (corridas reales) |
| Personalización justificada (15 %) | `dataset_tuning.py`, `decision.py`, `muestra_formato.py` | `docs/decision_personalizacion.md`, `docs/muestra_formato_respuestas.json` |
| Observabilidad y trazabilidad (15 %) | `log_rag.py`, `logging_rag.py` | `docs/rag_logs.jsonl` |
| Seguridad, versionado y gobernanza (20 %) | `prevencion_prompt_inyection.py`, `registro_prompts.py`, `grafo_supervision.py`, `matriz_riesgos.py` | `python src/Gate2/matriz_riesgos.py` |

Autoevaluación con el promedio ponderado: `python src/Gate2/rubrica_gate2.py`.

## Estructura

- `src/Gate1/`: miniaplicación del Gate 1 (cliente de la API, pipeline de texto, banco de prompts).
  Se ejecuta con `python src/Gate1/consumir_api.py`.
- `src/Gate2/`: servicio RAG y sus piezas (indexación, recuperación, evaluación, logging, seguridad,
  versionado, supervisión, agentes de la Unidad 2.4).
- `test/`: pruebas automáticas. `test/test_gate2.py` verifica los criterios no compensables del Gate 2.
- `docs/`: decisiones de arquitectura, resultados de evaluación, registros de latencia y costo, logs
  y el registro del ensayo.
- `prompts/`: banco de prompts del Gate 1.
- `requirements.txt`, `.env.example`, `.gitignore`.
