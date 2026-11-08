"""Almacenamiento en JSON: catálogo, opiniones y consultas (Actividades 1, 5 y 6).

Principios:
  * Las rutas se construyen desde la ubicación de ESTE archivo, así funciona
    sin importar desde qué carpeta se lance Streamlit.
  * Un archivo dañado NUNCA se reemplaza en silencio: se informa y se conserva.
  * La escritura es atómica: se escribe un archivo temporal en la misma carpeta
    y luego se reemplaza el original (os.replace). Si algo falla a la mitad, el
    archivo viejo queda intacto.
  * Guardar es idempotente: el mismo id de registro no se guarda dos veces.
  * Consultar NO llama al modelo.
"""
import json
import os
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from modelos import (
    SENTIMIENTOS,
    VERSION_PROMPT,
    AnalisisOpinion,
    ErrorAlmacenamiento,
    ErrorCatalogo,
    ErrorClasificacion,
)

BASE_DIR = Path(__file__).resolve().parent
# TRIBUNA_DATOS permite apuntar a otra carpeta (la usan las pruebas automáticas).
DIR_DATOS = Path(os.getenv("TRIBUNA_DATOS") or BASE_DIR / "datos")
RUTA_JUGADORES = DIR_DATOS / "jugadores.json"
RUTA_OPINIONES = DIR_DATOS / "opiniones.json"

VERSION_ESQUEMA = 1
CAMPOS_REGISTRO = (
    "id",
    "fecha_utc",
    "jugador_id",
    "jugador_nombre",
    "opinion_original",
    "sentimiento",
    "razon",
    "modelo",
    "version_prompt",
)

# Streamlit atiende cada sesión en un hilo distinto. Este candado evita que dos
# guardados del mismo proceso se pisen entre sí (leer -> añadir -> escribir).
_CANDADO = threading.Lock()


def estructura_vacia() -> dict:
    """El diccionario con el que arranca opiniones.json."""
    return {"version": VERSION_ESQUEMA, "opiniones": []}


# ---------------------------------------------------------------- utilidades
def _leer_json(ruta: Path):
    """Lee un JSON y traduce los fallos comunes a ErrorAlmacenamiento."""
    ruta = Path(ruta)
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        raise ErrorAlmacenamiento(
            f"El archivo «{ruta.name}» no contiene JSON válido "
            f"(línea {exc.lineno}, columna {exc.colno}). "
            "Se conservó tal cual; corrígelo o restáuralo antes de continuar."
        ) from exc
    except UnicodeDecodeError as exc:
        raise ErrorAlmacenamiento(
            f"El archivo «{ruta.name}» no está codificado en UTF-8."
        ) from exc
    except OSError as exc:
        raise ErrorAlmacenamiento(
            f"No se pudo leer «{ruta.name}»: {exc.strerror or exc}."
        ) from exc


def _escribir_atomico(ruta: Path, datos: dict) -> None:
    """Escribe `datos` en `ruta` sin dejar nunca un archivo a medias."""
    ruta = Path(ruta)
    tmp = None
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        # El temporal va en la MISMA carpeta: os.replace solo es atómico dentro
        # de un mismo sistema de archivos.
        fd, tmp = tempfile.mkstemp(dir=ruta.parent, prefix=f".{ruta.name}.", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        # mkstemp crea el archivo con permisos 0600; conservamos los del original
        # (o 0644 si es nuevo) para que no quede ilegible fuera del contenedor.
        if ruta.exists():
            os.chmod(tmp, ruta.stat().st_mode & 0o777)
        else:
            os.chmod(tmp, 0o644)
        os.replace(tmp, ruta)
        tmp = None
    except (OSError, TypeError, ValueError) as exc:
        raise ErrorAlmacenamiento(
            f"No se pudo escribir «{ruta.name}»: {getattr(exc, 'strerror', None) or exc}."
        ) from exc
    finally:
        if tmp is not None:
            try:
                os.unlink(tmp)
            except OSError:
                pass


# ------------------------------------------------------- catálogo (Actividad 1)
def cargar_jugadores(ruta: Path = None) -> list[dict]:
    """Lee y valida el catálogo. Devuelve la lista de jugadores.

    Comprueba la estructura y que NO existan identificadores repetidos.
    """
    ruta = Path(ruta or RUTA_JUGADORES)
    try:
        datos = _leer_json(ruta)
    except ErrorAlmacenamiento as exc:
        raise ErrorCatalogo(str(exc)) from exc.__cause__

    if not isinstance(datos, dict) or not isinstance(datos.get("jugadores"), list):
        raise ErrorCatalogo("El catálogo debe ser un objeto con la clave «jugadores» (lista).")

    jugadores, vistos, repetidos = [], set(), []
    for i, j in enumerate(datos["jugadores"], start=1):
        if not isinstance(j, dict):
            raise ErrorCatalogo(f"El jugador #{i} no es un objeto.")
        for campo in ("id", "nombre", "pais"):
            valor = j.get(campo)
            if not isinstance(valor, str) or not valor.strip():
                raise ErrorCatalogo(f"El jugador #{i} no tiene «{campo}» válido.")
        if j["id"] in vistos:
            repetidos.append(j["id"])
        vistos.add(j["id"])
        jugadores.append({"id": j["id"], "nombre": j["nombre"], "pais": j["pais"]})

    if repetidos:
        raise ErrorCatalogo(f"Identificadores repetidos en el catálogo: {sorted(set(repetidos))}.")
    if not jugadores:
        raise ErrorCatalogo("El catálogo no contiene jugadores.")
    return jugadores


# ----------------------------------------------------- opiniones (Actividad 5)
def _validar_registro(r, posicion="?") -> None:
    """Comprueba que un registro tenga todos los campos y valores permitidos."""
    if not isinstance(r, dict):
        raise ErrorAlmacenamiento(f"El registro #{posicion} no es un objeto.")
    faltan = [c for c in CAMPOS_REGISTRO if c not in r]
    if faltan:
        raise ErrorAlmacenamiento(f"El registro #{posicion} no tiene los campos: {faltan}.")
    for campo in CAMPOS_REGISTRO:
        if not isinstance(r[campo], str) or not r[campo].strip():
            raise ErrorAlmacenamiento(f"El registro #{posicion} tiene «{campo}» vacío o no es texto.")
    if r["sentimiento"] not in SENTIMIENTOS:
        raise ErrorAlmacenamiento(
            f"El registro #{posicion} tiene un sentimiento no permitido: {r['sentimiento']!r}."
        )


def _validar_estructura(datos) -> dict:
    """Valida el diccionario completo de opiniones.json (esquema inesperado = error)."""
    if not isinstance(datos, dict) or not isinstance(datos.get("opiniones"), list):
        raise ErrorAlmacenamiento(
            "opiniones.json tiene un esquema inesperado: se esperaba un objeto "
            "con la clave «opiniones» (lista). Se conservó sin cambios."
        )
    ids = set()
    for i, r in enumerate(datos["opiniones"], start=1):
        _validar_registro(r, i)
        if r["id"] in ids:
            raise ErrorAlmacenamiento(f"opiniones.json tiene el id repetido {r['id']!r}.")
        ids.add(r["id"])
    return datos


def cargar_opiniones(ruta: Path = None) -> dict:
    """Lee el diccionario persistente de opiniones.

    * Si el archivo no existe, se inicializa con la estructura vacía.
    * Si existe pero está dañado o tiene otro esquema -> ErrorAlmacenamiento y el
      archivo NO se toca (nunca se sustituye por una lista vacía).
    """
    ruta = Path(ruta or RUTA_OPINIONES)
    if not ruta.exists():
        datos = estructura_vacia()
        _escribir_atomico(ruta, datos)
        return datos
    return _validar_estructura(_leer_json(ruta))


def crear_registro(
    jugador: dict,
    texto: str,
    analisis: AnalisisOpinion,
    modelo: str,
    registro_id: str | None = None,
) -> dict:
    """Arma el registro final: el programa pone UUID, fecha y metadatos.

    `registro_id` permite reutilizar el id de un envío (para que un reintento
    no genere un registro distinto).
    """
    if not analisis.es_pertinente or analisis.sentimiento is None:
        raise ErrorClasificacion("Una opinión no pertinente no genera registro.")
    registro = {
        "id": registro_id or str(uuid.uuid4()),
        "fecha_utc": datetime.now(timezone.utc).isoformat(),
        "jugador_id": jugador["id"],
        "jugador_nombre": jugador["nombre"],
        "opinion_original": texto.strip(),
        "sentimiento": analisis.sentimiento,
        "razon": analisis.razon.strip(),
        "modelo": modelo,
        "version_prompt": VERSION_PROMPT,
    }
    _validar_registro(registro)
    return registro


def guardar_opinion(ruta: Path, registro: dict) -> bool:
    """Añade `registro` sin perder los anteriores.

    Lee el estado actual, añade y escribe el diccionario completo de forma
    atómica. Devuelve True si se guardó y False si ese id YA existía (así un
    reintento o una reejecución no duplica el registro).
    """
    ruta = Path(ruta or RUTA_OPINIONES)
    _validar_registro(registro)
    with _CANDADO:
        datos = cargar_opiniones(ruta)
        if any(r["id"] == registro["id"] for r in datos["opiniones"]):
            return False
        datos["opiniones"].append(registro)
        _escribir_atomico(ruta, datos)
    return True


# ------------------------------------------------------ consulta (Actividad 6)
def _clave_fecha(registro: dict):
    try:
        return datetime.fromisoformat(registro["fecha_utc"])
    except (KeyError, ValueError):
        return datetime.min.replace(tzinfo=timezone.utc)


def consultar_opiniones(
    registros: list[dict],
    jugador_id: str | None = None,
    sentimiento: str | None = None,
) -> list[dict]:
    """Filtra por jugador y/o sentimiento (None = todos). Más recientes primero.

    Es una función pura: NO consulta al modelo.
    """
    resultado = [
        r
        for r in registros
        if (jugador_id is None or r["jugador_id"] == jugador_id)
        and (sentimiento is None or r["sentimiento"] == sentimiento)
    ]
    return sorted(resultado, key=_clave_fecha, reverse=True)


def contar_por_sentimiento(registros: list[dict]) -> dict:
    """Cantidad por categoría, siempre con las cuatro claves (aunque valgan 0)."""
    conteo = {s: 0 for s in SENTIMIENTOS}
    for r in registros:
        conteo[r["sentimiento"]] += 1
    return conteo
