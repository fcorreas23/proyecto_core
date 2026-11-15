## Catálogo de herramientas del agente

Cada herramienta, clasificada por riesgo y nivel de supervisión.

| Herramienta                        | Descripción                                                        | Nivel de riesgo | Supervisión requerida                                  |
|------------------------------------|--------------------------------------------------------------------|-----------------|--------------------------------------------------------|
| `consultar_estado_envio_detallado` | Consulta el estado actual de un envío y, opcionalmente, su historial. | 🟢 Bajo         | Ninguna (solo muestreo semanal de trazas)              |
| `calcular_costo_envio`             | Calcula el costo estimado de un envío según peso y distancia.     | 🟢 Bajo         | Ninguna (solo muestreo semanal de trazas)              |
| `generar_reembolso`                | Simula un reembolso a un cliente por un pedido.                   | 🔴 Alto         | **Aprobación previa** (humana, obligatoria, timeout 15 s) |

Este agente no tiene herramientas de riesgo **medio** (escritura reversible), por lo
que ninguna usa "revisión posterior". El detalle y la justificación de cada nivel
están en la sección siguiente.

## Herramientas y nivel de riesgo

- `consultar_estado_envio_detallado`: **bajo**. Solo lee el diccionario `ESTADOS`
  y no modifica nada. Si el número no existe, devuelve un texto ("No se encontró
  un envío…") en lugar de lanzar una excepción.
- `calcular_costo_envio`: **bajo**. Es un cálculo puro (`500 + peso_kg*120 +
  distancia_km*3`) sin efectos externos. Los argumentos se validan con Pydantic
  (`peso_kg > 0`, `distancia_km >= 0`). Lo peor que puede pasar es que informe un
  precio equivocado al cliente, pero no ejecuta ninguna acción.
- `generar_reembolso`: **alto** (escritura irreversible con impacto económico).
  En un sistema real movería dinero, y un reembolso pagado no se revierte de forma
  automática. Hoy solo es una simulación, pero se clasifica por la acción que
  representa y no por la implementación de juguete. Por eso requiere aprobación
  humana.

No hay ninguna herramienta de escritura reversible (por ejemplo, cambiar la dirección
de entrega). Si se agrega una, debe clasificarse como riesgo **medio**.

## Herramientas que requieren aprobación humana

- `generar_reembolso`: es la única acción con consecuencia económica e irreversible.
  Si el modelo se equivoca de pedido o de monto, el error cuesta dinero. Por eso la
  decisión final la toma una persona y no el modelo.

Las dos herramientas de riesgo bajo **no** piden aprobación. Pedirla para consultas
y cálculos solo agregaría ruido y acostumbraría a quien aprueba a decir "sí" sin leer.

## Revisión de trazas

- **Frecuencia:**
  - **Cada** interacción que invoque `generar_reembolso` se revisa el mismo día,
    haya sido aprobada o no.
  - Muestreo **semanal** de las interacciones de riesgo bajo, o cada 50
    interacciones, lo que ocurra primero.
- **Chequeo rápido antes de leer a mano:**

  ```
  wc -l trazas_agente.jsonl
  grep -c '"herramienta": "generar_reembolso"' trazas_agente.jsonl
  ```

  Resultado actual: `5 trazas_agente.jsonl` y `2`.

- **Qué se busca (patrones del Bloque 23 aplicados a este agente):**
  1. **Reembolso sin pedido explícito:** `generar_reembolso` aparece en
     `acciones` aunque la `entrada` del usuario no pidió un reembolso.
  2. **Monto distinto al pedido:** el `monto` de `argumentos` no coincide con la
     cifra que escribió el usuario, o está fuera de lo razonable.
  3. **Pedido inexistente:** reembolsos sobre números de pedido que no existen.
     Hoy la herramienta no lo detecta (ver limitaciones).
  4. **Respuesta que contradice la observación:** la `respuesta_final` dice que el
     reembolso se hizo, pero la observación dice "no aprobado", o el precio o el
     estado informados no coinciden con lo que devolvió la herramienta.
  5. **Respuesta sin herramienta:** `acciones` vacío en una pregunta de costo o de
     estado, lo que significa que el modelo inventó el dato.
  6. **Reintentos en bucle:** la misma herramienta repetida varias veces en un
     turno, cerca de `max_iterations=5`.
  7. **Memoria cruzada:** datos de un `session_id` que aparecen en la respuesta
     de otro.

### Evidencia real en `trazas_agente.jsonl`

| session_id  | Entrada (resumida)                         | Herramienta                        | Riesgo | Resultado         |
|-------------|--------------------------------------------|------------------------------------|--------|-------------------|
| cliente_246 | Costo de 2.5 kg a 50 km                    | `calcular_costo_envio`             | bajo   | ok                |
| cliente_246 | "¿Y si pesara el doble?" (usa la memoria)  | `calcular_costo_envio`             | bajo   | ok                |
| cliente_456 | Estado de AR12345 con historial            | `consultar_estado_envio_detallado` | bajo   | ok                |
| cliente_123 | Reembolso de 25000 por PED123 roto         | `generar_reembolso`                | alto   | aprobado (`s`)    |
| cliente_789 | Reembolso de 80000 por PED999              | `generar_reembolso`                | alto   | rechazado (`n`)   |

En el caso rechazado, la respuesta final informó correctamente que el reembolso no
se aprobó (no hubo patrón 4).

