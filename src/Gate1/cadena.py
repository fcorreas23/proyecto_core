from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate 
from langchain_core.output_parsers import StrOutputParser

load_dotenv()
modelo = ChatGoogleGenerativeAI(model="gemini-3.6-flash") 

""" plantilla = PromptTemplate.from_template(
    "Explica el concepto de {tema} en un párrafo, para alguien que recien comienza en {area}."
) """

plantilla_con_roles = ChatPromptTemplate.from_messages([
    #rol system (instrucciones del sistema)
    ("system", "Eres un experto en el área correspondiente, vas a responder siempre con texto simple para el usuario."),
    #rol human (pregunta del usuario)
    ("human", "Explica el concepto de {tema} en un párrafo, para alguien que recien comienza en {area}")
])

cadena = plantilla_con_roles | modelo | StrOutputParser()

respuesta = cadena.invoke({"tema": "RNA Seq", "area": "Bioinformatica"})

print(respuesta)


""" plantilla_conrol = ChatPromptTemplate.from_messages([
    ("system", "Eres un experto en el área correspondiente, vas a responder siempre con texto simple para el usuario."),
    ("human", "Explica el concepto de {tema} en un párrafo, para alguien que recien comienza en {area}")
]) """