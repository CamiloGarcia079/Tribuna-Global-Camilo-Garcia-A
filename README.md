# LangChain + Streamlit — Tribuna Global

Proyecto de la clase de Inteligencia Artificial 2 (CampusLands, bases de datos vectoriales y LangChain). Parte del entorno Docker que armó el profe Johlver Pardo y lo adapta para trabajar con Gemini u OpenAI. Encima de eso está el taller **Tribuna Global**, un chatbot que guarda opiniones de aficionados sobre futbolistas y las clasifica con un modelo de lenguaje.

Autor: Camilo Andrés García Almeida.

## Qué hay aquí

- **Entorno de desarrollo.** Un Dev Container de VS Code con tres servicios: la app de Python, PostgreSQL y pgAdmin (`docker-compose.yml`, `Dockerfile`, `.devcontainer/`).
- **Ejemplos de clase** en `app/`: el hola mundo con OpenAI y con Gemini, y los chatbots de Streamlit (`streamlit_chatbot.py` con `PromptTemplate`, `streamlit_chatbot2.py` con `ChatPromptTemplate` y selector de personalidad, y `full_chatbot.py`). `utils_chat.py` tiene una función que arregla un problema con Gemini 3.x, que devuelve la respuesta como lista de bloques en vez de texto.
- **Ejercicios de LangChain** en `app/intermedio/`, en el orden de la clase (ver la tabla de abajo).
- **Taller Tribuna Global** en `app/tribuna_global/`. Tiene su propio README.

## Ejercicios de `app/intermedio/`

Cada archivo se corre solo con `python nombre.py` desde esa carpeta. Los que no usan modelo no necesitan clave.

| Archivo | Tema | ¿Usa modelo? |
| --- | --- | --- |
| `ejemplo_runnables.py` | `RunnableLambda`, `invoke`/`batch`, el operador `\|`, `RunnableParallel`, `RunnablePassthrough` | No |
| `prompt_templates.py` | `PromptTemplate` (plantilla de texto) | No |
| `chat_prompt_template.py` | `ChatPromptTemplate` con roles `system` y `human` | No |
| `rol_prompt_templates.py` | `SystemMessagePromptTemplate` y `HumanMessagePromptTemplate` | No |
| `message_placeholders.py` | `MessagesPlaceholder` para el historial (`--modelo` consulta al modelo real) | Opcional |
| `analisis_sentimientos_parte1.py` | Mini-proyecto: `RunnableLambda` y cadena `preprocesador \| process` | Sí |
| `analisis_sentimientos_parte2.py` | Mini-proyecto: `RunnableParallel` y `batch()` | Sí |
| `output_parsers_parte1.py` | `StrOutputParser` y `JsonOutputParser` | Sí |
| `output_parsers_parte2.py` | `PydanticOutputParser` y `with_structured_output` | Sí |
| `streamlit_chatbot2.py` | Chatbot con historial como mensajes (`streamlit run streamlit_chatbot2.py`) | Sí |

`modelo_llm.py` solo crea el modelo: usa OpenAI si hay `OPENAI_API_KEY` real y, si no, Gemini con `GOOGLE_API_KEY`.

## Tribuna Global en pocas palabras

Eliges un jugador de un catálogo de 20, escribes una opinión y el modelo la clasifica como positiva, negativa, neutra o mixta, con una razón corta. El resultado se guarda en un JSON y después se puede consultar con filtros, ver los recuentos y descargar. La clasificación describe lo que dice el aficionado, no la calidad del jugador.

Algunas decisiones que vale la pena conocer:

- El modelo solo devuelve el análisis; el id, la fecha y el resto del registro los pone el programa.
- Si algo falla (la API, la validación o la escritura) se muestra el error y no se guarda nada. Nunca se guarda un «neutro» inventado.
- El archivo se escribe de forma atómica y un reintento no duplica el registro.
- Cada opinión se analiza sola: el historial del chat nunca llega al clasificador.

## Cómo correrlo

La forma recomendada es **sin Docker**: un script crea el entorno, instala lo necesario, pide la clave de Gemini si falta y abre la app. Funciona igual en el PC del campus (Linux, sin permisos de administrador) y en Windows.

**Linux**, desde la carpeta del proyecto:

```bash
bash iniciar.sh
```

**Windows**, desde la carpeta del proyecto en PowerShell (o doble clic en `iniciar.bat`):

```powershell
.\iniciar.bat
```

La primera vez tarda unos minutos instalando librerías. Si no hay `.env`, el script lo crea y te pide la `GOOGLE_API_KEY`: la pegas y queda guardada solo en tu PC. Después se abre http://localhost:8501 (si ese puerto está ocupado, Streamlit usa el 8502). Para detenerla, `Ctrl + C`.

En la barra lateral eliges el proveedor y el modelo de una lista con los modelos que tu clave puede usar. Si el modelo elegido está saturado (error 503) o sin cuota (429), la app prueba sola el siguiente de la lista y te dice cuál respondió.

### Con el Dev Container (opcional)

Si Docker funciona en tu equipo: crea el `.env` en la raíz, abre la carpeta en VS Code y elige **Dev Containers: Reopen in Container**. En la terminal del contenedor:

```bash
cd /app/app/tribuna_global
streamlit run app.py --server.address=0.0.0.0 --server.port=8501
```

Para los ejemplos sueltos: `python app/hello_world_gemini.py` o `streamlit run app/full_chatbot.py`.

## Pruebas

Dentro de `app/tribuna_global/`:

```bash
python -m pytest                # 87 pruebas, sin gastar API
python pruebas_aceptacion.py    # las 16 pruebas del taller con el modelo real
```

## Cosas a tener en cuenta

- Solo puede haber un entorno levantado a la vez: los nombres de los contenedores y los puertos se repiten.
- Si Docker da problemas (`docker.sock ... no such file`, `permission denied`), no hace falta: usa `bash iniciar.sh`.
- Los scripts de Linux van con `bash iniciar.sh`, no con `./iniciar.sh`: al pasar por Windows o GitHub el archivo puede perder el permiso de ejecución.
- `app/tribuna_global/datos/opiniones.json` viene con 16 opiniones de ejemplo, marcadas como ficticias. Para empezar de cero: `python cargar_demo.py --vaciar`.
- Nunca subas claves. Si alguna se expone, bórrala y crea otra.
