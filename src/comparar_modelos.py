import statistics
import time
from consumir_api import consultar_modelo, modelos

PROMPT = "Eres un agronomo que trabaja con cerezos en Chile, un agricultor de la región de O'Higgins te pide recomendaciones sobre cual variedad de cerezo plantar en su huerto. Considera el clima, el suelo y la resistencia a enfermedades. Utiliza tu conocimiento experto para dar la mejor recomendación corta y precisa. "
RUN = 4
PAUSA = 5  # segundos entre peticiones para no superar la cuota del plan gratuito
ARCHIVO_RESPUESTAS = "respuestas_comparacion.md"

# Función que hace la misma pregunta RUN veces a cada modelo y guarda cada resultado
def comparar_modelos():
    resultados = []
    for modelo in modelos:
        nombre = modelo["nombre"]
        for i in range(RUN):
            try:
                texto, segundos, costo = consultar_modelo(PROMPT, nombre)
                resultados.append({
                    "modelo": nombre,
                    "intento": i + 1,
                    "texto": texto,
                    "tiempo": segundos,
                    "costo": costo
                })
            except (ValueError, RuntimeError) as error:
                resultados.append({
                    "modelo": nombre,
                    "intento": i + 1,
                    "error": str(error)
                })
            print(f"{nombre} intento {i + 1}/{RUN}: {'error' if 'error' in resultados[-1] else 'ok'}")
            time.sleep(PAUSA)
    return resultados

# Función que agrupa los resultados por modelo y calcula las métricas de la tabla
def resumir(resultados):
    resumen = []
    for modelo in modelos:
        nombre = modelo["nombre"]
        del_modelo = [r for r in resultados if r["modelo"] == nombre]
        exitosos = [r for r in del_modelo if "error" not in r]
        errores = [r["error"] for r in del_modelo if "error" in r]
        fila = {"modelo": nombre, "exitosos": len(exitosos), "errores": errores}
        if exitosos:
            tiempos = [r["tiempo"] for r in exitosos]
            costos = [r["costo"] for r in exitosos]
            fila["tiempo_promedio"] = statistics.mean(tiempos)
            fila["tiempo_mediana"] = statistics.median(tiempos)
            fila["tiempo_min"] = min(tiempos)
            fila["tiempo_max"] = max(tiempos)
            fila["costo_promedio"] = statistics.mean(costos)
            fila["largo_promedio"] = statistics.mean(len(r["texto"].split()) for r in exitosos)
        resumen.append(fila)
    return resumen

# Función que arma la tabla comparativa en formato Markdown
def tabla_markdown(resumen):
    lineas = [
        "| Modelo | Éxitos | Latencia prom. (s) | Mediana (s) | Mín – máx (s) | Costo prom. (USD) | Palabras prom. |",
        "|---|---|---|---|---|---|---|",
    ]
    for f in resumen:
        if f["exitosos"]:
            lineas.append(
                f"| `{f['modelo']}` | {f['exitosos']}/{RUN} | {f['tiempo_promedio']:.2f} | {f['tiempo_mediana']:.2f} "
                f"| {f['tiempo_min']:.2f} – {f['tiempo_max']:.2f} | {f['costo_promedio']:.6f} | {f['largo_promedio']:.0f} |"
            )
        else:
            lineas.append(f"| `{f['modelo']}` | 0/{RUN} | – | – | – | – | – |")
    return "\n".join(lineas)

# Función que guarda todas las respuestas en un archivo para evaluar la calidad
def guardar_respuestas(resultados, tabla):
    with open(ARCHIVO_RESPUESTAS, "w", encoding="utf-8") as archivo:
        archivo.write(f"# Comparación de modelos\n\nPregunta: {PROMPT}\n\n{tabla}\n")
        for r in resultados:
            archivo.write(f"\n## {r['modelo']} – intento {r['intento']}\n\n")
            if "error" in r:
                archivo.write(f"**Error:** {r['error']}\n")
            else:
                archivo.write(f"_{r['tiempo']:.2f} s · {r['costo']:.6f} USD_\n\n{r['texto']}\n")

if __name__ == "__main__":
    resultados = comparar_modelos()
    resumen = resumir(resultados)
    tabla = tabla_markdown(resumen)
    print()
    print(tabla)
    for f in resumen:
        for error in f["errores"]:
            print(f"{f['modelo']}: {error}")
    guardar_respuestas(resultados, tabla)
    print(f"\nRespuestas completas guardadas en {ARCHIVO_RESPUESTAS}")
