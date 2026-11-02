## Registro del ensayo de rate limit

- Fecha: 2026-11-02
- Modelo: `gemini-3.6-flash`
- Peticiones enviadas: 40 (dos corridas seguidas, de 10 y 30, sin pausa entre llamadas)
- Petición donde apareció el primer 429: la número 11 del ensayo (número 0 de la segunda corrida)
- Esperas observadas: 2.0–2.2s y 4.0–4.4s (backoff exponencial con jitter, correcto). Con 3 intentos solo hay dos esperas, por eso no aparece la de 8s
- Costo total del ensayo: $0.017916 ($0.011738 + $0.006178)
- Resultado: 15 peticiones con éxito y 25 fallidas tras agotar sus 3 intentos

### Detalle por corrida

| Corrida | Horario | Peticiones | Éxito directo | Éxito tras reintentar | Fallo definitivo | Costo |
|---|---|---|---|---|---|---|
| 1 | hasta 14:18:33 | 10 | 10 | 0 | 0 | $0.011738 |
| 2 | 14:18:47 – 14:23:24 | 30 | 4 | 1 | 25 | $0.006178 |

### Qué se observó

- El backoff se comportó como se diseñó: las esperas crecen y varían por el jitter.
- Solo una petición se recuperó con un reintento (la número 4 de la segunda corrida, tras esperar 2.0s).
- Las esperas suman unos 6s, y eso no alcanzó a cubrir el límite en las otras 25 peticiones.
- Los 25 fallos definitivos terminaron en un `RuntimeError` con mensaje claro, sin excepciones crípticas de `requests`.
- El costo se registró solo en las 5 peticiones completadas de la segunda corrida: la suma de esas 5 coincide con el total de $0.006178.
- Las últimas 15 peticiones fallaron todas, durante unos 2.5 minutos. El ensayo no permite saber qué cuota se agotó, porque el 429 no trajo `Retry-After` y el código no guarda el cuerpo del error.
