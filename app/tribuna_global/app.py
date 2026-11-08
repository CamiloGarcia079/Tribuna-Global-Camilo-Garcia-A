"""Tribuna Global: interfaz Streamlit (Actividades 2, 6 y 7).

Ejecutar desde la carpeta tribuna_global:
    streamlit run app.py

Reparto de responsabilidades:
    app.py            -> interfaz (este archivo)
    analisis.py       -> prompt, modelo y clasificación
    almacenamiento.py -> archivos JSON y consultas
    modelos.py        -> contrato Pydantic, constantes y errores

Dos memorias distintas (Resultado de aprendizaje: «historial de sesión vs. disco»):
    st.session_state  -> el chat que se ve; se pierde al recargar o con «Nueva conversación».
    datos/opiniones.json -> las opiniones guardadas; sobreviven al reinicio.
"""
import json
import re
import uuid

import pandas as pd
import streamlit as st

import almacenamiento as alm
import analisis
from modelos import (
    MAX_CARACTERES,
    MIN_CARACTERES,
    SENTIMIENTOS,
    ErrorAlmacenamiento,
    ErrorCatalogo,
    ErrorClasificacion,
    ErrorEntrada,
)

SECCIONES = ("Emitir opinión", "Consultar opiniones")
TODOS = "Todos"

st.set_page_config(page_title="Tribuna Global", page_icon="⚽", layout="wide")


# ------------------------------------------------------------------ utilidades
def _plano(texto: str) -> str:
    """Escapa el Markdown para que el texto del usuario se vea tal cual lo escribió."""
    texto = re.sub(r"([\\`*_{}\[\]()#+\-.!$<>|~])", r"\\\1", texto)
    return texto.replace("\n", "  \n")


def iniciar_estado() -> None:
    st.session_state.setdefault("mensajes", [])  # historial visual del chat
    st.session_state.setdefault("envio_pendiente", None)  # envío que falló y se puede reintentar


def nueva_conversacion() -> None:
    """Limpia el chat y los envíos pendientes. NO toca opiniones.json."""
    st.session_state.mensajes = []
    st.session_state.envio_pendiente = None


def agregar_mensaje(rol: str, jugador: str, texto: str) -> dict:
    mensaje = {"rol": rol, "jugador": jugador, "texto": texto}
    st.session_state.mensajes.append(mensaje)
    return mensaje


def mostrar_mensaje(m: dict) -> None:
    """Dibuja un mensaje; el nombre del jugador queda asociado a cada uno."""
    if m["rol"] == "usuario":
        with st.chat_message("user"):
            st.caption(m["jugador"])
            st.markdown(m["texto"])
        return
    with st.chat_message("assistant"):
        st.caption(m["jugador"])
        if m["rol"] == "error":
            st.error(m["texto"])
        elif m["rol"] == "aviso":
            st.warning(m["texto"])
        else:
            st.markdown(m["texto"])


# --------------------------------------------------------------------- envío
def procesar_envio(envio: dict, modelos: list[str], clave: str | None) -> None:
    """Clasifica (si hace falta) y guarda un envío. Distingue los tres tipos de fallo.

    El envío ya trae capturado el jugador y su propio id, así que:
      * cambiar el selector después no altera registros anteriores;
      * un reintento reutiliza el id y el análisis ya obtenido -> no se duplica
        el registro ni se vuelve a gastar una llamada al modelo.
    `modelos` es la cadena de respaldo: si el primero está saturado se prueba el siguiente.
    """
    jugador = envio["jugador"]
    nombre = jugador["nombre"]

    def decir(rol: str, texto: str) -> None:
        mostrar_mensaje(agregar_mensaje(rol, nombre, texto))

    try:
        if envio["registro"] is None:
            with st.spinner(f"Analizando la opinión con {modelos[0]}…"):
                resultado, usado, fallos = analisis.analizar_con_respaldo(
                    jugador, envio["texto"], modelos, clave
                )
            if fallos:
                saltados = ", ".join(f"{m} ({motivo})" for m, motivo in fallos)
                decir("aviso", f"Respondió {usado} porque antes falló: {saltados}.")
            if not resultado.es_pertinente:
                decir(
                    "aviso",
                    f"No se guardó: el mensaje no parece una opinión sobre {nombre}. "
                    f"{_plano(resultado.razon)}",
                )
                st.session_state.envio_pendiente = None
                return
            envio["registro"] = alm.crear_registro(
                jugador, envio["texto"], resultado, usado, registro_id=envio["id"]
            )
        with st.spinner("Guardando…"):
            guardado = alm.guardar_opinion(alm.RUTA_OPINIONES, envio["registro"])
    except ErrorEntrada as exc:  # 1) fallo de ENTRADA (no se reintenta: se corrige el texto)
        decir("error", f"Entrada no válida. {exc}")
        st.session_state.envio_pendiente = None
    except ErrorClasificacion as exc:  # 2) fallo de CLASIFICACIÓN
        decir("error", f"No se pudo clasificar la opinión; no se guardó nada. {exc}")
    except ErrorAlmacenamiento as exc:  # 3) fallo de ALMACENAMIENTO
        decir("error", f"La opinión se clasificó pero NO se pudo guardar. {exc}")
    except Exception as exc:  # cualquier otra cosa: se muestra, jamás se disfraza de «neutro»
        decir("error", f"Error inesperado ({type(exc).__name__}); no se guardó nada. {analisis._sanear(exc)}")
    else:
        # La confirmación aparece SOLO después de una escritura exitosa.
        registro = envio["registro"]
        if guardado:
            decir(
                "asistente",
                f"Opinión guardada. Sentimiento estimado: {registro['sentimiento']}.\n\n"
                f"{_plano(registro['razon'])}\n\nRegistro: `{registro['id']}`",
            )
        else:
            decir("asistente", f"Este envío ya estaba guardado; no se duplicó. Registro: `{registro['id']}`")
        st.session_state.envio_pendiente = None


def vista_emitir(jugador: dict, modelos: list[str], clave: str | None) -> None:
    st.subheader(f"Opiniones sobre {jugador['nombre']}")
    st.caption("Cada envío se analiza de forma independiente y se asocia al jugador seleccionado.")

    # chat_input siempre queda fijo abajo, sin importar dónde se llame.
    texto = st.chat_input(f"Opinión sobre el jugador seleccionado ({MIN_CARACTERES} a {MAX_CARACTERES} caracteres)")

    for m in st.session_state.mensajes:
        mostrar_mensaje(m)

    if texto is not None:
        limpio = texto.strip()
        if not limpio:
            st.warning("Escribe una opinión antes de enviar. No se llamó al modelo ni se guardó nada.")
        else:
            # La selección queda CAPTURADA aquí: cambiarla después no afecta este envío.
            envio = {"id": str(uuid.uuid4()), "jugador": dict(jugador), "texto": limpio, "registro": None}
            mostrar_mensaje(agregar_mensaje("usuario", jugador["nombre"], _plano(limpio)))
            try:
                analisis.validar_texto(limpio)  # largo 5–1000: si falla, NO se llama al modelo
            except ErrorEntrada as exc:
                mostrar_mensaje(agregar_mensaje("error", jugador["nombre"], f"Entrada no válida. {exc}"))
            else:
                st.session_state.envio_pendiente = envio
                procesar_envio(envio, modelos, clave)

    pendiente = st.session_state.envio_pendiente
    if pendiente is not None:
        st.info(
            f"Hay un envío sin guardar sobre {pendiente['jugador']['nombre']}: "
            f"«{pendiente['texto'][:80]}{'…' if len(pendiente['texto']) > 80 else ''}»"
        )
        if st.button("Reintentar envío", key="reintentar"):
            procesar_envio(pendiente, modelos, clave)
            st.rerun()


# ------------------------------------------------------------------- consulta
def _mostrar_tabla(df: pd.DataFrame) -> None:
    try:  # Streamlit reciente
        st.dataframe(df, width="stretch", hide_index=True)
    except Exception:  # Streamlit anterior
        st.dataframe(df, use_container_width=True, hide_index=True)


def vista_consultar(jugadores: list[dict]) -> None:
    st.subheader("Consulta de opiniones")
    st.caption("Los recuentos representan únicamente los registros de esta aplicación.")

    try:
        registros = alm.cargar_opiniones(alm.RUTA_OPINIONES)["opiniones"]
    except ErrorAlmacenamiento as exc:
        st.error(f"No se pueden consultar las opiniones. {exc}")
        return

    nombres = {j["id"]: j["nombre"] for j in jugadores}
    filtro_j = st.selectbox(
        "Filtro por jugador", [TODOS, *nombres], format_func=lambda i: TODOS if i == TODOS else nombres[i]
    )
    filtro_s = st.selectbox("Filtro por sentimiento", [TODOS, *SENTIMIENTOS])

    # La tabla, los recuentos y la descarga usan EXACTAMENTE los mismos filtros.
    filtrados = alm.consultar_opiniones(
        registros,
        None if filtro_j == TODOS else filtro_j,
        None if filtro_s == TODOS else filtro_s,
    )
    conteo = alm.contar_por_sentimiento(filtrados)

    columnas = st.columns(1 + len(SENTIMIENTOS))
    columnas[0].metric("Total", len(filtrados))
    for col, s in zip(columnas[1:], SENTIMIENTOS):
        col.metric(s.capitalize(), conteo[s])

    if not filtrados:
        st.info("No hay opiniones que coincidan con los filtros seleccionados.")
        return

    _mostrar_tabla(
        pd.DataFrame(
            {
                "Fecha UTC": [r["fecha_utc"] for r in filtrados],
                "Jugador": [r["jugador_nombre"] for r in filtrados],
                "Opinión": [r["opinion_original"] for r in filtrados],
                "Sentimiento": [r["sentimiento"] for r in filtrados],
                "Razón": [r["razon"] for r in filtrados],
            }
        )
    )
    st.download_button(
        "Descargar resultados JSON",
        data=json.dumps({"version": alm.VERSION_ESQUEMA, "opiniones": filtrados}, ensure_ascii=False, indent=2),
        file_name="opiniones_filtradas.json",
        mime="application/json",
    )


# --------------------------------------------------------------------- modelo
OTRO = "Otro (escribir el nombre)…"


@st.cache_data(ttl=3600, show_spinner="Consultando los modelos disponibles…")
def modelos_disponibles(proveedor: str, clave: str | None) -> list[str]:
    """Se pregunta una vez por hora; así cambiar de jugador o sección no vuelve a consultar."""
    return analisis.listar_modelos(proveedor, clave)


def configurar_modelo() -> tuple[list[str], str | None]:
    """Barra lateral: proveedor, clave, modelo y respaldo. Devuelve (modelos a probar, clave)."""
    solo_openai = analisis.obtener_clave("openai") and not analisis.obtener_clave("google")
    proveedor = st.radio(
        "Proveedor", ["google", "openai"], index=1 if solo_openai else 0, horizontal=True,
        format_func=lambda p: "Google (Gemini)" if p == "google" else "OpenAI",
    )
    clave = analisis.obtener_clave(proveedor)
    if clave is None:
        clave = st.text_input(
            f"{analisis.VARIABLE_CLAVE[proveedor]} (solo esta sesión)", type="password"
        ).strip() or None

    disponibles = modelos_disponibles(proveedor, clave)
    preferido = analisis._valor_real("GEMINI_MODEL" if proveedor == "google" else "OPENAI_MODEL")
    opciones = list(dict.fromkeys([*([preferido] if preferido else []), *disponibles])) + [OTRO]
    elegido = st.selectbox("Modelo", opciones, index=0)
    if elegido == OTRO:
        elegido = st.text_input("Nombre del modelo", placeholder="ej.: gemini-3.5-flash-lite").strip()
        if not elegido:
            st.caption("Escribe el nombre del modelo para poder enviar.")
            elegido = opciones[0]

    respaldo = st.checkbox("Si el modelo está saturado, probar otro", value=True)
    modelos = analisis.cadena_de_respaldo(elegido, disponibles) if respaldo else [elegido]
    st.caption("Orden de prueba: " + " → ".join(modelos))
    st.caption("Temperatura 0 cuando el modelo la admite y salida estructurada (JSON Schema).")
    return modelos, clave


# ------------------------------------------------------------------ principal
def main() -> None:
    iniciar_estado()
    st.title("⚽ Tribuna Global")
    st.caption("Opiniones de aficionados sobre futbolistas. Las categorías son estimaciones de IA.")

    try:
        jugadores = alm.cargar_jugadores(alm.RUTA_JUGADORES)
    except ErrorCatalogo as exc:
        st.error(f"No se pudo cargar el catálogo de jugadores. {exc}")
        st.stop()
    por_id = {j["id"]: j for j in jugadores}

    with st.sidebar:
        st.header("Configuración")
        seccion = st.radio("Sección", SECCIONES)
        jugador_id = st.selectbox(
            "Jugador",
            list(por_id),
            format_func=lambda i: f"{por_id[i]['nombre']} · {por_id[i]['pais']}",
        )
        modelos, clave = configurar_modelo()
        st.button("Nueva conversación", on_click=nueva_conversacion)
        st.caption(
            "La nueva conversación limpia el chat y los envíos pendientes; conserva los registros guardados."
        )

    if seccion == SECCIONES[0]:
        vista_emitir(por_id[jugador_id], modelos, clave)
    else:
        vista_consultar(jugadores)


main()
