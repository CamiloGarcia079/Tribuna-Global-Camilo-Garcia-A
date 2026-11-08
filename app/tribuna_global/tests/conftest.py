"""Configuración común de las pruebas: ruta de importación y un modelo FALSO.

Las pruebas NO llaman a ninguna API: usan FakeModelo, que imita lo único que
necesita analisis.py (with_structured_output e invoke).
"""
import sys
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import Runnable, RunnableLambda

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from modelos import AnalisisOpinion  # noqa: E402


class FakeModelo(Runnable):
    """Chat model de mentira.

    estructurado(texto_humano) -> AnalisisOpinion | dict | None   (o lanza una excepción)
    json_texto(texto_humano)   -> str con la respuesta «manual» en JSON
    """

    def __init__(self, estructurado=None, json_texto=None):
        self.estructurado = estructurado
        self.json_texto = json_texto
        self.llamadas_estructuradas = 0
        self.llamadas_json = 0
        self.ultimo_prompt = None

    @property
    def llamadas(self):
        return self.llamadas_estructuradas + self.llamadas_json

    def invoke(self, entrada, config=None, **kwargs):  # ruta JSON manual
        self.llamadas_json += 1
        self.ultimo_prompt = entrada.to_messages()
        if self.json_texto is None:
            raise RuntimeError("sin respuesta JSON configurada")
        return AIMessage(content=self.json_texto(self.ultimo_prompt[-1].content))

    def with_structured_output(self, esquema, **kwargs):  # ruta estructurada
        def _ejecutar(valor):
            self.llamadas_estructuradas += 1
            self.ultimo_prompt = valor.to_messages()
            return self.estructurado(self.ultimo_prompt[-1].content)

        return RunnableLambda(_ejecutar)


def clasificador_simple(texto_humano: str) -> AnalisisOpinion:
    """Reglas mínimas que imitan al modelo real para las pruebas."""
    t = texto_humano.lower()
    if "paris" in t or "capital" in t or "ignora las reglas" in t:
        return AnalisisOpinion(es_pertinente=False, sentimiento=None, razon="El texto no es una opinión sobre el jugador.")
    if "pero" in t:
        return AnalisisOpinion(es_pertinente=True, sentimiento="mixto", razon="Combina elogio y crítica.")
    if "decepcion" in t or "falló" in t:
        return AnalisisOpinion(es_pertinente=True, sentimiento="negativo", razon="Expresa una crítica.")
    if "extraordinari" in t or "excelente" in t:
        return AnalisisOpinion(es_pertinente=True, sentimiento="positivo", razon="Expresa admiración.")
    return AnalisisOpinion(es_pertinente=True, sentimiento="neutro", razon="Describe al jugador sin valorarlo.")


@pytest.fixture
def modelo_ok():
    return FakeModelo(estructurado=clasificador_simple)
