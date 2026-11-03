# Límites de la métrica de evaluación

## Qué mide

Coincidencia exacta de palabras entre una respuesta generada y una referencia, contando repeticiones (precisión, cobertura y F1). No mide si la respuesta es correcta.

## Modos de falla conocidos

Casos de `docs/resultados_metricas.json`. Los dos últimos se probaron alterando a propósito una respuesta real.

- **Sinónimos y paráfrasis puntúan bajo.** "¿Qué es el usuario root?": F1 0.29 con una respuesta correcta, porque "superusuario" y "privilegios ilimitados" no coinciden con "administrador con control total".
- **Otra forma de la misma palabra no cuenta.** "¿Qué es cron?": F1 0.19, el más bajo de los 30; "programar" no coincide con "programadas". Tampoco se quitan palabras comunes, así que "de" sí suma como coincidencia.
- **El detalle correcto se castiga.** "¿Qué es un proceso?": cobertura 1.0 pero F1 0.37, porque agrega "PID" y "memoria", que no están en la referencia.
- **El F1 depende del largo de la respuesta.** Con los mismos 30 casos, agregar "Responde en una sola frase." subió el F1 promedio de 0.06 a 0.48. El contenido no mejoró tanto: bajó el largo, de una mediana de 361 a 22.5 palabras. La cobertura incluso bajó, de 0.92 a 0.79.
- **Un dato equivocado casi no se nota.** "¿Cuándo se creó Python?": cambiar 1991 por 1989 baja el F1 de 0.59 a 0.47, por encima de 13 de las 30 respuestas, entre ellas las de tar y root, que sí son correctas.
- **Una negación casi no cambia el puntaje.** "¿Qué hace pwd?": escribir "no muestra" invierte el sentido y el F1 solo baja de 0.64 a 0.62.

## Muestra revisada

- **2026-11-02:** 10 casos de 30, los 5 con menor F1 (0.19–0.37) y los 5 con mayor F1 (0.59–0.80), con `gemini-3.5-flash-lite` y la instrucción "Responde en una sola frase.". Detalle en `docs/revision_manual.json`.
- **Resultado:** 8 casos sin observaciones, 1 parcialmente completo (cron, F1 0.19) y 1 con corrección factual parcial (Python, F1 0.59). Ninguno tiene contradicciones. En esta muestra, un F1 bajo no indicó una respuesta incorrecta.
- **Alcance:** los 20 casos del medio no se revisaron. Las referencias se escribieron a mano y son preguntas de definición sobre Python y Linux, así que estos resultados no aplican a otros temas.

## Recomendación de uso

Usa F1 solo para comparar versiones del cliente con el mismo set de casos y respuestas de largo parecido; nunca como nota de calidad de una respuesta, y lee siempre a mano cualquier respuesta con fechas, cifras o nombres propios, o con una negación, sea cual sea su F1.
