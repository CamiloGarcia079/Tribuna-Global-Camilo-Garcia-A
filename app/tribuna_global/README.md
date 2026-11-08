# Tribuna Global

Chatbot de Streamlit que registra opiniones de aficionados sobre futbolistas, estima su sentimiento con LangChain (`positivo`, `negativo`, `neutro`, `mixto`) y deja consultarlas aunque se reinicie la aplicación. El catálogo es una selección didáctica, no un ranking de fama o calidad, y las cifras solo reflejan lo registrado en esta app.

## Qué hace cada parte

- **Emitir opinión:** eliges un jugador en la barra lateral, escribes entre 5 y 1000 caracteres y recibes la clasificación con una justificación breve. Se guarda en `datos/opiniones.json`.
- **Consultar opiniones:** filtros por jugador y sentimiento, recuentos, tabla y descarga en JSON. Consultar nunca llama al modelo.
- **Nueva conversación:** limpia el chat; los registros guardados se quedan.

## Archivos

```text
app.py                 interfaz de Streamlit
analisis.py            prompt, modelo y clasificación
almacenamiento.py      lectura y escritura de los JSON, consultas
modelos.py             contrato de Pydantic, constantes y errores
cargar_demo.py         carga o vacía las opiniones de ejemplo
pruebas_aceptacion.py  corre las 16 pruebas del taller y escribe REGISTRO_PRUEBAS.md
versiones.py           escribe requirements-lock.txt con las versiones instaladas
datos/                 jugadores.json (20 jugadores) y opiniones.json
ejemplos/              las 16 opiniones ficticias de ejemplo
tests/                 87 pruebas automáticas
EXPLICACION.md         cómo funciona todo, para explicarlo en clase
```

## Instalación y configuración

Lo más fácil es el script de la raíz del proyecto: `bash iniciar.sh` en Linux o `.\iniciar.bat` en Windows. Crea el entorno, instala, te pide la clave si falta y abre la app.

Las claves van solo en el `.env` de la raíz (la app lo busca sola):

```dotenv
GOOGLE_API_KEY=...        # para Gemini
OPENAI_API_KEY=...        # para OpenAI, opcional
GEMINI_MODEL=...          # opcional: el modelo que aparece primero en el selector
```

En la barra lateral eliges el **proveedor** (Google u OpenAI) y el **modelo** de una lista. Para Gemini la lista se le pide a Google con tu clave, así que solo salen modelos que tu cuenta puede usar; si Google no responde, se usa una lista fija. La opción «Otro» deja escribir cualquier nombre. Si falta la clave, aparece un campo para pegarla durante esa sesión.

**Respaldo automático.** Con la casilla «Si el modelo está saturado, probar otro» marcada, la app prueba el modelo elegido y, si responde 503 (saturado), 429 (sin cuota), 404 (no disponible) o tarda más de 25 segundos, pasa al siguiente. El registro guarda el modelo que de verdad respondió. Un error de clave o de contrato no salta de modelo: se muestra tal cual. Cada llamada espera como máximo 25 segundos y no hace reintentos internos, por eso los errores aparecen rápido.

## Ejecución a mano

Con el entorno activo y desde esta carpeta:

```bash
streamlit run app.py
```

Se abre http://localhost:8501. Dentro del Dev Container hay que añadir `--server.address=0.0.0.0 --server.port=8501`. Otros comandos:

```bash
python cargar_demo.py              # añade los ejemplos que falten
python cargar_demo.py --vaciar     # deja opiniones.json vacío
python -m pytest                   # pruebas automáticas
python pruebas_aceptacion.py       # pruebas del taller con el modelo real
python versiones.py                # guarda tus versiones en requirements-lock.txt
```

## Versiones

Con estas se probó el código. Las de tu propio entorno quedan en `requirements-lock.txt` después de correr `python versiones.py`.

| Paquete | Versión |
| --- | --- |
| Python | 3.13 |
| streamlit | 1.67.0 |
| langchain-core | 1.7.6 |
| langchain-openai | 1.7.4 |
| langchain-google-genai | 4.4.3 |
| pydantic | 2.13.5 |
| pandas | 3.0.5 |

## Entregables del taller

| Entregable | Dónde |
| --- | --- |
| Código ejecutable con `streamlit run app.py` | `app.py`, `analisis.py`, `almacenamiento.py`, `modelos.py` |
| Catálogo de 20 o más futbolistas con id | `datos/jugadores.json` |
| 12 o más registros ficticios, 4 jugadores, 4 categorías | `datos/opiniones.json` (16 registros) |
| Registro de pruebas | `REGISTRO_PRUEBAS.md`, generado por `pruebas_aceptacion.py` |
| Reflexión sobre dos casos ambiguos | `EXPLICACION.md`, sección 8 |
| Evidencias de persistencia y consulta filtrada | capturas de pantalla |

## Límites

Es una práctica local con un solo escritor. Un candado protege varias sesiones del mismo proceso, pero no varios procesos a la vez; para eso habría que pasar a SQLite o PostgreSQL. Y la clasificación es una estimación del modelo: la ironía y los textos con sentimientos mezclados pueden salir ambiguos.
