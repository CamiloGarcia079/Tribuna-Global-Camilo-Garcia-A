# Cómo funciona Tribuna Global (explicación paso a paso)

Este documento sirve para **explicar el código en clase** y para la rúbrica («explicación del código», 15 pts).

## 1. Idea general en una frase

El usuario elige un jugador y escribe una opinión → el programa la valida → un modelo (Gemini u OpenAI) la clasifica y devuelve un **objeto Pydantic** → el programa lo vuelve a validar, le pone UUID, fecha y metadatos → lo guarda en un JSON de forma atómica → la sección de consulta lee ese JSON y filtra **sin llamar al modelo**.

```text
 Streamlit (app.py)                analisis.py                         almacenamiento.py
 ┌───────────────────┐   texto    ┌──────────────────────────┐        ┌──────────────────────────┐
 │ chat_input        │ ─────────► │ validar_texto (5–1000)   │        │ cargar_jugadores         │
 │ selectbox jugador │            │ prompt (system + human)  │        │ cargar_opiniones         │
 │ (snapshot al      │            │ modelo.with_structured_  │        │ crear_registro (uuid,    │
 │  enviar)          │            │   output(AnalisisOpinion)│        │   fecha, metadatos)      │
 │                   │ ◄───────── │ validar_analisis         │ ─────► │ guardar_opinion (atómico,│
 │ mensajes en       │  resultado └──────────────────────────┘ regis- │   sin duplicar ids)      │
 │ session_state     │                                          tro   │ consultar_opiniones      │
 └───────────────────┘                                                └──────────────────────────┘
        ▲  modelos.py: AnalisisOpinion (contrato), SENTIMIENTOS, errores (Entrada / Clasificación / Almacenamiento)
```

## 2. Qué hace cada archivo

| Archivo | Responsabilidad | Actividad del taller |
| --- | --- | --- |
| `modelos.py` | Contrato `AnalisisOpinion` (exactamente el del taller), constantes (5–1000 caracteres, las 4 categorías, `VERSION_PROMPT`) y las tres excepciones propias. | 4 y 7 |
| `almacenamiento.py` | Leer/validar el catálogo (ids únicos), leer/crear/validar `opiniones.json`, `crear_registro`, `guardar_opinion` (atómico e idempotente), `consultar_opiniones`, `contar_por_sentimiento`. | 1, 5 y 6 |
| `analisis.py` | `ChatPromptTemplate` con rol `system` y `human`, creación del modelo (OpenAI/Gemini), `analizar_opinion`, validación de coherencia. | 3 y 4 |
| `app.py` | Interfaz: dos secciones, selector, historial en `st.session_state`, botón de nueva conversación, errores, tabla y descarga. | 2, 6 y 7 |

## 3. El flujo de un envío, con detalle

1. **Captura.** Al pulsar enviar, `app.py` crea un *envío* con su propio `id` (uuid), una **copia** del jugador seleccionado y el texto. Por eso cambiar el selector después **no modifica** registros anteriores.
2. **Validación de entrada** (`validar_texto`): sin espacios exteriores, entre 5 y 1000 caracteres. Si falla, **no se llama al modelo** ni se guarda.
3. **Prompt.** `ChatPromptTemplate.from_messages([("system", …), ("human", …)])`. El `system` define criterios para las 4 categorías, ironía y pertinencia, y dice que el contenido de la opinión son **datos** (defensa contra «ignora las reglas…»). El `human` lleva `{jugador}` y la `{opinion}` entre etiquetas `<opinion>`.
4. **Modelo con salida estructurada.** `prompt | modelo.with_structured_output(AnalisisOpinion)` y `.invoke({...})`. El resultado es un **objeto Pydantic**: se usa `analisis.sentimiento`, **no** `response.content` como en el chatbot original.
5. **Validación de coherencia** (`validar_analisis`). El esquema no comprueba por sí solo que *pertinente ⇒ tiene categoría* y *no pertinente ⇒ sentimiento `None`*. Lo hace esta función.
6. **No pertinente** → se avisa («No se guardó…») y termina: no se guarda como neutro.
7. **Registro.** `crear_registro` añade UUID (el del envío), fecha UTC y metadatos (`modelo`, `version_prompt`). El modelo **solo** genera `es_pertinente`, `sentimiento` y `razon`.
8. **Guardado atómico** (`guardar_opinion`): lee el estado, añade el registro, escribe UTF-8 con `ensure_ascii=False` e indentación en un **archivo temporal en la misma carpeta**, hace `fsync` y lo reemplaza con `os.replace`. Si algo falla, el archivo anterior queda intacto.
9. **Confirmación** solo después de que el guardado terminó bien («Opinión guardada. Sentimiento estimado: …»).

## 4. Por qué cada decisión (ligadas a las reglas del taller)

| Regla / criterio | Cómo se cumple |
| --- | --- |
| Jugador desde un catálogo, no identificado por el modelo | El jugador sale del `selectbox`; el modelo solo recibe su nombre como dato. |
| Historial visual ≠ clasificador | `analizar_opinion` recibe **solo** la opinión actual; hay una prueba (`test_el_analisis_solo_ve_la_opinion_actual`). |
| Un fallo no es «neutro» | Cualquier excepción del modelo se convierte en `ErrorClasificacion` y se muestra en rojo; nunca se crea un registro. |
| Confirmar solo tras escribir | El mensaje de éxito está en el bloque `else` del `try` que contiene el guardado. |
| Archivo dañado se conserva | `cargar_opiniones` lanza `ErrorAlmacenamiento`; no hay ningún `except` que lo reemplace por `[]`. Prueba parametrizada con 4 tipos de daño. |
| No duplicar por reejecución | Streamlit reejecuta el script con cada interacción, pero `chat_input` solo devuelve texto en el envío; además el registro conserva el `id` del envío y `guardar_opinion` devuelve `False` si ese id ya existe. El **reintento** reutiliza el análisis ya hecho (no vuelve a gastar una llamada). |
| Dos opiniones con el mismo texto no son duplicados | Cada envío tiene su id: se guardan dos registros. |
| Nueva conversación | Vacía `st.session_state` (chat y pendientes); no toca `opiniones.json`. |
| Consultar no llama al modelo | `consultar_opiniones` es una función pura sobre la lista; hay una prueba que cuenta las llamadas al modelo (0). |
| Rutas independientes del directorio | `BASE_DIR = Path(__file__).resolve().parent`. |

### Historial de sesión vs. persistencia en disco
- `st.session_state["mensajes"]` es el **chat que se ve**: vive mientras dure la sesión del navegador.
- `datos/opiniones.json` es la **persistencia**: sobrevive a cerrar el programa. Por eso, al pulsar «Nueva conversación» el chat desaparece pero la consulta sigue mostrando todo.

## 5. Gemini y OpenAI (lo que cambia)

- El proveedor se decide por el nombre del modelo (`gemini*` → Google; si no, OpenAI). Las claves vienen de `.env`.
- Gemini 3.x ignora la temperatura (la app no la envía); en 2.5 y en `gpt-4o-mini` se usa `temperature=0`.
- Con salida estructurada **no** se usa `extraer_texto` (aquel arreglo era para `response.content` en formato de lista de bloques); el objeto Pydantic ya viene parseado. Solo la **alternativa JSON** (ver abajo) lo necesita y lo incluye.
- **Método de salida `auto`:** primero `with_structured_output`; si falla por un problema del esquema o del formato, intenta la **alternativa de profundización** (pedir JSON en el prompt, `json.loads` y validar con Pydantic). Si el error es de clave, cuota o modelo inexistente **no reintenta** (no serviría) y lo muestra. Se puede forzar con `METODO_SALIDA=estructurada|json`.
- Los mensajes de error ocultan cualquier texto que parezca una clave (`AIza…`, `AQ.…`, `sk-…`).

### Selector de modelos y respaldo automático

En clase nos pasó: `gemini-2.5-flash` ya no estaba disponible para cuentas nuevas (404) y `gemini-3.8-flash` respondía 503 por saturación. Por eso:

- **`listar_modelos`** le pregunta a Google qué modelos de texto tiene la clave y los ordena: estables primero, flash antes que pro, los más nuevos arriba. Si no puede, usa una lista fija.
- **`cadena_de_respaldo`** arma el orden de prueba: el modelo elegido y detrás dos más del mismo proveedor, de preferencia «lite» o alias «latest», que suelen estar menos saturados.
- **`analizar_con_respaldo`** recorre esa lista con un `for`: si un modelo da 503, 429, 404 o se pasa del tiempo, anota el motivo y prueba el siguiente. Si el error es de clave, de entrada o de contrato, se detiene y lo muestra, porque cambiar de modelo no lo arreglaría.
- LangChain trae esto mismo con `modelo.with_fallbacks([otro1, otro2])` (es un Runnable más). Lo hicimos a mano para saber **qué modelo respondió** y guardarlo en el campo `modelo` del registro.
- `crear_modelo` usa `timeout=25` y `max_retries=0`: antes reintentaba dos veces con hasta 60 s cada vez y la pantalla se quedaba en «Analizando…» mucho rato antes de fallar.

## 6. Las pruebas

- `python -m pytest` → 87 pruebas **sin API** (modelo falso): almacenamiento, análisis y la interfaz completa con `streamlit.testing` (`AppTest`).
- `python pruebas_aceptacion.py` → las **16 pruebas del taller** contra el modelo **real**; escribe `REGISTRO_PRUEBAS.md` con lo observado (nada inventado) y deja una sección para que expliques las discrepancias.

| Caso del taller | Cómo se cubre |
| --- | --- |
| Elogio / Crítica / Descripción / Mixta / Ironía / Ajeno / Instrucción | `pruebas_aceptacion.py` con el modelo real (+ pytest con el modelo falso) |
| Entrada vacía | `test_entrada_vacia_no_llama_al_modelo_ni_guarda` |
| Persistencia, Conservación, Cambio de jugador | `pruebas_aceptacion.py` + `test_persistencia_tras_reiniciar_la_aplicacion` |
| Limpieza del chat | `test_nueva_conversacion_limpia_el_chat_y_conserva_el_archivo` + verificación manual |
| Fallo de API | `pruebas_aceptacion.py` (clave inválida) + `test_fallo_de_api_…` |
| Archivo dañado / Fallo de escritura | `test_archivo_danado_…`, `test_fallo_de_escritura_…` (se simula `os.replace` porque *root* ignora `chmod`) |
| Reejecución | `test_reejecucion_al_cambiar_de_seccion_o_filtro_no_duplica` |

## 7. Preguntas que te pueden hacer (y la respuesta corta)

- **¿Por qué `with_structured_output` y no `json.loads` del `content`?** Porque el modelo queda obligado al esquema y LangChain lo parsea a Pydantic; con `json.loads` hay que validar a mano (un JSON válido puede traer datos incorrectos). Aun así dejamos esa vía como alternativa.
- **¿Por qué `os.replace` con un temporal?** Para que un corte a mitad de escritura no deje un `opiniones.json` a medias: el reemplazo es atómico dentro del mismo sistema de archivos.
- **¿Para qué el `id` del envío?** Para la idempotencia: reintentar no crea un segundo registro.
- **¿Qué pasa con dos usuarios a la vez?** Un candado cubre varias sesiones del mismo proceso, pero no varios procesos; para eso, SQLite/PostgreSQL (desafío de ampliación).
- **¿Se puede cambiar la interfaz?** Sí: `analisis.py` y `almacenamiento.py` no importan Streamlit, así que se podrían reutilizar desde una API (FastAPI) con un frontend en React.

## 8. Reflexión sobre errores o ambigüedades de clasificación

> El taller pide **dos** casos. Aquí va uno ya observado en clase y una plantilla para el segundo; **complétalo con lo que obtengas tú** al ejecutar `pruebas_aceptacion.py` (no copies resultados que no viste).

**Caso 1 — Opinión basada en un prejuicio (visto en clase con `gpt-4o-mini`).**
Entrada sobre Vinícius Júnior: «Me parece que no es tan bueno porque es de brasil». El modelo la clasificó **negativa**, con una razón que señalaba que la nacionalidad influye en la valoración.
- *Ambigüedad:* la categoría describe lo que expresa el aficionado (desaprobación) pero la justificación no es deportiva. Un revisor podría discutir si debería marcarse como no pertinente o como negativa con una nota sobre el prejuicio.
- *Decisión de diseño:* el prompt indica clasificar por la valoración expresada y permite que la razón señale el prejuicio. La etiqueta **no** afirma nada sobre la calidad real del jugador.

**Caso 2 — _(completar)_** Elige un caso donde el resultado real te sorprendió: por ejemplo la **ironía** (caso 5), la frontera **mixto vs. neutro** (caso 4/3) o un texto largo con varias ideas.
- Entrada exacta:
- Resultado esperado / observado (copiado de `REGISTRO_PRUEBAS.md`):
- ¿Error del modelo, del prompt o ambigüedad legítima? ¿Qué cambiarías en el prompt (y subirías `VERSION_PROMPT`)?
