"""Modelos de datos, constantes y errores de Tribuna Global.

Aquí vive todo lo que comparten los otros módulos:
  - el contrato de salida del modelo (AnalisisOpinion),
  - las reglas de validación (categorías, largo del texto),
  - las excepciones propias, para distinguir un fallo de ENTRADA,
    de CLASIFICACIÓN y de ALMACENAMIENTO (Actividad 7).
"""
from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------- constantes
VERSION_PROMPT = "1.0"  # se guarda en cada registro; súbela si cambias el prompt
MIN_CARACTERES = 5
MAX_CARACTERES = 1000

# Orden fijo: se usa en filtros, recuentos y validaciones.
SENTIMIENTOS = ("positivo", "negativo", "neutro", "mixto")


# ------------------------------------------------------------------ contrato
class AnalisisOpinion(BaseModel):
    """Lo ÚNICO que genera el modelo (Actividad 4).

    El UUID, la fecha, el jugador y los metadatos los pone el programa.
    """

    es_pertinente: bool = Field(
        description="Indica si el texto constituye una opinión sobre el jugador seleccionado"
    )
    sentimiento: Literal["positivo", "negativo", "neutro", "mixto"] | None = Field(
        description="Categoría de la opinión; null cuando no es pertinente"
    )
    razon: str = Field(min_length=1, max_length=300)


# ------------------------------------------------------------------- errores
class ErrorTribuna(Exception):
    """Base de todos los errores controlados de la aplicación."""


class ErrorEntrada(ErrorTribuna):
    """La opinión del usuario no cumple las reglas (vacía, muy corta o muy larga)."""


class ErrorClasificacion(ErrorTribuna):
    """El modelo no respondió, respondió algo inválido o no hay clave configurada."""


class ErrorAlmacenamiento(ErrorTribuna):
    """No se pudo leer, validar o escribir un archivo JSON."""


class ErrorCatalogo(ErrorAlmacenamiento):
    """El catálogo jugadores.json es inválido (por ejemplo, ids repetidos)."""
