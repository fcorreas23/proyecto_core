from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate 
from langchain_core.output_parsers import StrOutputParser

load_dotenv()
modelo = ChatGoogleGenerativeAI(model="gemini-3.6-flash") 

plantilla_extraccion = PromptTemplate.from_template("Lee el siguiente texto y devuelve solo sus 3 puntos clave, uno por línea, sin desarrollarlos: \n {texto}")
respuesta = plantilla_extraccion | modelo | StrOutputParser()

texto = "La bioinformática, en relación con la genética y la genómica, es una subdisciplina científica que implica el uso de ciencias informáticas para recopilar, almacenar y analizar y diseminar datos e información biológicos, como secuencias de ADN y aminoácidos o anotaciones sobre esas secuencias. Los científicos y el personal clínico usan bases de datos que organizan y catalogan esa información biológica para aumentar el entendimiento de la salud y la enfermedad y, en ciertos casos, se usan para proveer mejor atención médica. \n La Bioinformática es un campo de las ciencias computacionales que lleva a cabo el análisis de secuencias de moléculas biológicas. Normalmente se aplica a los genes, al ADN, al ARN, o a las proteínas, y resulta especialmente útil para comparar secuencias de genes y proteínas entre distintos organismos, pudiendo ver las relaciones evolutivas entre organismos, y intentando averiguar cuál es la función de dichos genes y proteínas. Podríamos decir que la Bioinformática se encarga de la parte lingüística de la genética. De la misma manera que los lingüistas estudian los patrones en el lenguaje, los bioinformáticos estudian los patrones en las secuencias de ADN o de proteínas.  "

plantilla_simplificacion = PromptTemplate.from_template("Reescribe estos puntos en lenguaje simple, sin jerga técnica para alguien sin conocimientos previos: \n{puntos}")

paso_simplificacion = plantilla_simplificacion | modelo | StrOutputParser()

plantilla_formato = PromptTemplate.from_template("Convierte este texto en una lista de viñetas markdown de máximo 3 líneas, sin introducción: \n{texto_simple}")

cadena_tres_pasos = (
    plantilla_extraccion
    | modelo
    | StrOutputParser()
    | (lambda puntos: {"puntos": puntos})
    | plantilla_simplificacion
    | modelo
    | StrOutputParser()
    | (lambda simple: {"texto_simple": simple})
    | plantilla_formato
    | modelo
    | StrOutputParser()
)

resultado = cadena_tres_pasos.invoke({"texto": texto})
print(resultado)



