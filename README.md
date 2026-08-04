# Token Analyzer

Herramienta de analisis, traduccion, optimizacion y clasificacion de prompts y archivos Excel para reducir el consumo de tokens antes de enviarlos a un LLM. Simula costos de procesamiento a escala para ayudar a tomar decisiones informadas sobre idiomas y modelos.

---

## Descripcion

**Problema**: cada token enviado a una API de LLM tiene un costo. Los prompts en espanol consumen ~30% mas tokens que su equivalente en ingles para el mismo contenido, y los prompts mal formulados generan mas iteraciones y respuestas de baja calidad.

**Solucion**: Token Analyzer analiza tus prompts y archivos de texto, los traduce, evalua su calidad, los optimiza y proyecta el ahorro economico que obtendrias al usar ingles o prompts mejor estructurados.

**Publico objetivo**: desarrolladores que integran LLMs, equipos de producto que gestionan grandes volumenes de texto, y cualquier persona que quiera reducir costos de API sin sacrificar calidad.

**Beneficios**:

- Reduccion cuantificable del gasto en tokens (proyeccion diaria, mensual y anual)
- Evaluacion automatica de calidad de prompts con IA local
- Clasificacion inteligente de grandes volumenes de resenas
- Optimizacion de mensajes con ahorro medible de tokens
- **100% offline**: traduccion local con MarianMT, sin APIs externas ni llamadas HTTP
- **Cache persistente SQLite**: las traducciones sobreviven reinicios y se comparten entre ejecuciones

---

## Caracteristicas principales

| Caso | Capacidad |
|---|---|
| **Caso 1 . Prompt Engineering** | Analiza un prompt individual: detecta idioma, cuenta tokens en espanol e ingles, evalua su calidad con IA local (Qwen 2.5), genera una version mejorada y recomienda el modelo de IA mas adecuado para la tarea. |
| **Caso 2 . Resenas Masivas** | Procesa archivos Excel, CSV, PDF o TXT con resenas de productos: extrae el texto, cuenta tokens, traduce, clasifica por tipo de error, componente, severidad y sentimiento, y simula costos de procesamiento a escala (10.000 resenas/dia). |
| **Caso 3 . Citas Medicas** | Procesa archivos Excel con mensajes de pacientes: extrae esquemas medicos (accion, especialidad, horario), traduce al ingles, optimiza el texto para reducir tokens, y exporta resultados con metricas de ahorro y costos proyectados (15.000 citas/dia). |

**Capacidades transversales**:

- Auto-deteccion de columnas de texto al subir archivos Excel o CSV
- Exportacion de resultados en JSON, CSV y XLSX
- Procesamiento desde archivos individuales o carpetas completas
- Perfilado de tiempos por etapa (visible en consola del backend)
- Interfaz web con tema oscuro y tres pestanas independientes
- Traduccion 100% offline con modelo MarianMT (sin dependencia de internet)
- Cache SQLite persistente que elimina la retraduccion en ejecuciones sucesivas

---

## Arquitectura

```
┌──────────────┐       HTTP/REST       ┌───────────────┐
│   Frontend   │ ◄──────────────────► │    Backend    │
│  React+Vite  │   /api/* endpoints    │   FastAPI     │
│  :5173       │                       │   :8000       │
└──────────────┘                       └───────┬───────┘
                                               │
                                    ┌──────────┴──────────┐
                                    │                     │
                              ┌─────┴─────┐         ┌─────┴─────┐
                              │  Ollama   │         │ MarianMT  │
                              │  (local)  │         │  (local)  │
                              │ Qwen 2.5  │         │ opus-mt   │
                              │  Llama 3  │         │ es<->en   │
                              └───────────┘         └─────┬─────┘
                                                         │
                                                   ┌─────┴─────┐
                                                   │  SQLite   │
                                                   │  Cache    │
                                                   └───────────┘
```

**Frontend**: SPA en React 18 + Vite que consume la API REST del backend. Sin estado persistente: toda la logica reside en el servidor. Proxy de desarrollo configurado para enrutar `/api` al backend.

**Backend**: API REST en FastAPI con nueve endpoints. Toda la logica de negocio esta en `token_counter.py`. El backend coordina la tokenizacion (tiktoken con encoding cacheado), traduccion (MarianMT local con cache SQLite), evaluacion con IA local, clasificacion hibrida (reglas + LLM) y optimizacion de texto.

**IA**: Modelos locales servidos por Ollama. Qwen 2.5 (0.5B) para evaluacion de prompts y clasificacion de resenas. Llama 3 (8B) para auditoria por rubrica.

**Traduccion**: MarianMT de HuggingFace (`Helsinki-NLP/opus-mt-es-en` y `opus-mt-en-es`) ejecutandose 100% local. Sin peticiones HTTP. Cache SQLite con WAL mode que persiste entre reinicios del servidor y elimina la retraduccion de textos ya procesados.

**Rendimiento**: primera ejecucion ~2-3 min en CPU (carga del modelo + traduccion de ~9K textos). Ejecuciones sucesivas **<5s** gracias al cache SQLite. Con GPU (CUDA) la primera ejecucion baja a **~12-20s**.

---

## Tecnologias utilizadas

### Frontend

| Tecnologia | Proposito |
|---|---|
| React 18 | Biblioteca de componentes UI |
| Vite 5 | Bundler y servidor de desarrollo |
| CSS3 (variables + flexbox + grid) | Estilos con tema oscuro personalizado |
| Google Fonts (Inter + JetBrains Mono) | Tipografia |

### Backend

| Tecnologia | Proposito |
|---|---|
| Python 3.12 | Lenguaje de backend |
| FastAPI | Framework REST con documentacion Swagger automatica |
| Uvicorn | Servidor ASGI |
| tiktoken | Tokenizacion con encoding de OpenAI (gpt-4o), cacheado a nivel modulo |
| MarianMT (Helsinki-NLP/opus-mt) | Traduccion ES<->EN 100% local con HuggingFace Transformers |
| PyTorch | Motor de inferencia para MarianMT (CPU/GPU automatico) |
| SQLite | Cache persistente de traducciones (WAL mode, thread-safe) |
| Ollama (cliente Python) | Inferencia con modelos locales (Qwen 2.5, Llama 3) |
| openpyxl | Lectura y escritura de archivos Excel (.xlsx), directo desde BytesIO |
| PyMuPDF (fitz) | Extraccion de texto de archivos PDF |
| ThreadPoolExecutor | Procesamiento paralelo de traduccion, tokenizacion y clasificacion |

### IA

| Tecnologia | Proposito |
|---|---|
| Qwen 2.5 (0.5B) | Evaluacion de calidad de prompts, clasificacion de resenas, generacion de mejoras |
| Llama 3 (8B) | Auditoria de prompts por rubrica detallada |
| MarianMT opus-mt-es-en (~74M) | Traduccion espanol -> ingles |
| MarianMT opus-mt-en-es (~74M) | Traduccion ingles -> espanol |
| tiktoken (encoding gpt-4o) | Conteo preciso de tokens |

### Dependencias opcionales (scripts)

| Tecnologia | Proposito |
|---|---|
| pandas | Lectura alternativa de Excel en procesamiento por carpeta |
| faker | Generacion de datos sinteticos (resenas, contratos, citas) |
| weasyprint | Generacion de PDFs a partir de HTML (contratos) |

---

## Instalacion

### Requisitos previos

- Python 3.12+
- Node.js 18+
- [Ollama](https://ollama.com) instalado y ejecutandose (opcional para clasificacion con LLM y rubrica)

### 1. Clonar el repositorio

```bash
git clone <repo-url>
cd prompt_analizer
```

### 2. Instalar dependencias del backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

### 3. Instalar dependencias del frontend

```bash
cd frontend
npm install
cd ..
```

### 4. Descargar modelos de IA (opcional)

```bash
# Asegurate de que Ollama este corriendo (en otra terminal)
ollama serve

# Descargar modelos
ollama pull qwen2.5:0.5b
ollama pull llama3:8b    # Solo necesario para /api/analyze/rubric
```

> **Nota**: los modelos MarianMT se descargan automaticamente en la primera ejecucion desde HuggingFace Hub (~300 MB cada uno). Si Ollama no esta disponible, la evaluacion de prompts y clasificacion usan heuristica de respaldo.

---

## Configuracion

Toda la configuracion esta embebida como constantes en el codigo:

| Constante | Archivo | Valor | Descripcion |
|---|---|---|---|
| `_PRECIO_POR_MILLON` | `token_counter.py` | $2.50 | Precio USD por millon de tokens |
| `_RESENAS_POR_DIA` | `token_counter.py` | 10.000 | Volumen diario de resenas para proyeccion |
| `_CITAS_POR_DIA` | `token_counter.py` | 15.000 | Volumen diario de citas para proyeccion |
| `_DIAS_POR_MES` | `token_counter.py` | 30 | Dias por mes para proyeccion |
| `MAX_TRANSLATION_WORKERS` | `main.py` | 10 | Workers concurrentes para traduccion/optimizacion |
| `MAX_LLM_WORKERS` | `main.py` | 6 | Workers concurrentes para clasificacion con LLM |
| `_MARIAN_BATCH_SIZE` | `token_counter.py` | 128 | Tamano de batch para inferencia MarianMT |
| `_MAX_NEW_TOKENS` | `token_counter.py` | 128 | Tokens maximos generados por traduccion |

---

## Ejecucion

### Backend (API)

```bash
cd prompt_analizer
source .venv/bin/activate
python -m backend.main
```

La API estara disponible en `http://localhost:8000`. Documentacion Swagger en `http://localhost:8000/docs`.

### Frontend (UI)

```bash
cd prompt_analizer/frontend
npm run dev
```

Abrir `http://localhost:5173` en el navegador. El proxy de Vite redirige automaticamente las peticiones `/api` al backend en `localhost:8000`.

### Solo backend (sin frontend)

El backend es completamente funcional sin el frontend. Puedes consumir la API directamente desde cualquier cliente HTTP, `curl` o la interfaz Swagger.

---

## Uso

### Caso 1 - Analizar un prompt

1. Abre la pestana **Caso 1 - Prompt Engineering**
2. Escribe o pega tu prompt en el area de texto
3. Haz clic en **ANALIZAR PROMPT**

El sistema te mostrara:
- Idioma detectado y comparacion de tokens (original vs traducido)
- Puntuacion de calidad (0-100) evaluada por Qwen 2.5 con rubrica de 7 dimensiones
- Fortalezas, debilidades y recomendaciones
- Version mejorada del prompt (si la puntuacion es < 80)
- Modelo de IA recomendado segun el tipo de tarea

### Caso 2 - Procesar resenas masivas

1. Abre la pestana **Caso 2 - Resenas Excel**
2. Sube uno o varios archivos (`.xlsx`, `.csv`, `.pdf`, `.txt`)
3. Opcionalmente activa **Optimizar Tokens** para traducir al ingles
4. Activa/desactiva **Modo Rapido** (solo heuristica vs clasificacion hibrida con IA)
5. Haz clic en **PROCESAR RESENAS**

Obtendras:
- Tabla paginada con cada resena, tokens, costo individual, tipo de error, severidad y categoria
- Estadisticas globales (totales, promedios)
- Simulacion economica mensual comparando espanol vs ingles
- Exportacion a CSV, Excel o JSON

### Caso 3 - Optimizar mensajes de citas medicas

1. Abre la pestana **Caso 3 - Citas Medicas**
2. Selecciona modo **Archivo** (subir Excel) o **Carpeta** (ruta del servidor)
3. Activa **Optimizar Tokens** para traducir y comparar
4. Haz clic en **PROCESAR CITAS**

Obtendras:
- Tabla con cada mensaje: original, traduccion, texto optimizado, tokens y porcentaje de ahorro
- Resumen de optimizacion global (tokens ahorrados, porcentaje de reduccion)
- Simulacion economica mensual (15.000 citas/dia)
- Exportacion a CSV, Excel o JSON

---

## Inteligencia Artificial

### Modelos utilizados

| Modelo | Tamano | Rol |
|---|---|---|
| `qwen2.5:0.5b` | ~442 MB | Evaluador principal: calidad de prompts (rubrica 7D), clasificacion de resenas (error, componente, severidad), generacion de prompts mejorados |
| `llama3:8b` | ~4.7 GB | Auditoria especializada de prompts contra rubrica externa (`criterios_evaluacion.json`). Solo se invoca en el endpoint `/api/analyze/rubric` |
| `opus-mt-es-en` | ~300 MB | Traduccion espanol a ingles con MarianMT (Helsinki-NLP) |
| `opus-mt-en-es` | ~300 MB | Traduccion ingles a espanol con MarianMT (Helsinki-NLP) |

### Tareas de IA

- **Evaluacion de calidad**: Qwen 2.5 evalua cada prompt con una rubrica estricta de 7 dimensiones (claridad, contexto, objetivo, restricciones, formato, especificidad, coherencia), calibrada con reglas anti-inflacion para evitar puntuaciones artificialmente altas
- **Clasificacion hibrida de resenas**: primero se clasifica localmente con heuristica de keywords precompiladas (frozensets O(1)). Solo los grupos con baja confianza (< 0.6) se envian al LLM, reduciendo drasticamente el numero de llamadas
- **Auditoria por rubrica**: Llama 3 evalua el prompt contra una rubrica JSON configurable con criterios de claridad, concision, contexto, estructura e idioma
- **Mejora de prompts**: Qwen 2.5 genera una version mejorada del prompt cuando la puntuacion es inferior a 80/100

### Beneficios

- Evaluacion 100% local, sin costo de API externa
- Procesamiento por lotes con agrupacion inteligente para minimizar llamadas al LLM
- Fallback automatico a heuristica cuando Ollama no esta disponible
- Puntuacion matematicamente consistente (recalculada desde las metricas, no desde el texto generado)

---

## Optimizaciones de rendimiento

### Traduccion local con MarianMT

Reemplazo completo de Google Translate por modelos MarianMT de HuggingFace ejecutandose 100% offline. Cero llamadas HTTP. Carga lazy con `threading.Lock` para thread-safety. Inferencia con `torch.inference_mode()`, batches de 128 textos, deteccion automatica de GPU/CPU, `max_new_tokens=128`.

### Traduccion unificada

Todos los textos unicos de todos los grupos se traducen en un solo batch de MarianMT antes de distribuir los resultados a los workers. Elimina la division recursiva por limite de caracteres y reduce ~885 peticiones HTTP a una sola pasada de inferencia local.

### Cache SQLite persistente

Base de datos SQLite con WAL mode y synchronous=NORMAL. Conexion abierta/cerrada por operacion para thread-safety. Las traducciones persisten entre reinicios del servidor y entre procesos. Un texto traducido una vez nunca se retraduce. La cache crece ilimitadamente con cada ejecucion.

### Tokenizacion cacheada

El encoding `tiktoken.encoding_for_model("gpt-4o")` se crea una sola vez (lazy init) y se reusa en todas las llamadas (~30K invocaciones eliminadas).

### Clasificacion optimizada

La clasificacion local de resenas en `_procesar_resenas` se reusa en `clasificar_resenas_qwen` sin recalcular. Keywords como `frozenset` (lookup O(1)). Patrones regex precompilados a nivel modulo (12 patrones).

### Concurrencia

- Tokenizacion paralela con `ThreadPoolExecutor(8)` en pipeline de citas
- Workers de traduccion/optimizacion: 10 concurrentes
- Workers de clasificacion LLM: 6 concurrentes
- Lectura de Excel desde `BytesIO` sin archivos temporales

### Optimizacion de texto

Eliminacion de frases redundantes, muletillas y construcciones verbosas mediante patrones regex compilados, preservando datos medicos, fechas, nombres propios e informacion critica.

---

## Estructura del proyecto

```
prompt_analizer/
├── backend/                        # API REST y logica de negocio
│   ├── main.py                     # Endpoints FastAPI y orquestacion
│   ├── token_counter.py            # Logica: tokens, traduccion (MarianMT), IA, clasificacion, cache SQLite, optimizacion
│   ├── criterios_evaluacion.json   # Rubrica de evaluacion para /api/analyze/rubric
│   ├── requirements.txt            # Dependencias Python
│   └── _cache_traducciones.db      # Cache SQLite persistente de traducciones
├── frontend/                       # SPA en React + Vite
│   ├── index.html                  # Entry point HTML
│   ├── package.json                # Dependencias Node.js
│   ├── vite.config.js              # Configuracion de Vite + proxy /api
│   └── src/
│       ├── main.jsx                # Punto de entrada React
│       ├── App.jsx                 # Componentes: 3 pestanas, formularios, tablas, exportacion
│       └── index.css               # Estilos (tema oscuro, responsive)
└── scripts/                        # Utilidades de generacion de datos
    ├── cli.py                      # Contador de tokens por terminal
    ├── generador_excel.py          # Genera Excel con resenas sinteticas (10K+)
    ├── generate_citas.py           # Genera Excel con citas medicas sinteticas
    ├── generador_scripts.py        # Master script: genera PDFs de contratos + script standalone
    └── generar_contratos.py        # Script standalone generado para crear PDFs de contratos
```

> **Nota**: el archivo `_cache_traducciones.json` ha sido reemplazado por `_cache_traducciones.db` (SQLite).

---

## Scripts disponibles

| Script | Comando | Descripcion |
|---|---|---|
| `cli.py` | `python scripts/cli.py` | Cuenta tokens de un texto ingresado por terminal |
| `generador_excel.py` | `python scripts/generador_excel.py` | Genera un archivo Excel con 10.000 resenas sinteticas en espanol con datos de cliente, producto y ciudad |
| `generate_citas.py` | `python scripts/generate_citas.py` | Genera un archivo Excel con 10.000 solicitudes de citas medicas sinteticas (paciente, especialidad, fecha, mensaje) |
| `generador_scripts.py` | `python scripts/generador_scripts.py` | Genera 3 PDFs de ejemplo de contratos de arrendamiento en espanol y escribe el script standalone `generar_contratos.py` |
| `generar_contratos.py` | `python scripts/generar_contratos.py [N]` | Genera N contratos PDF sinteticos (por defecto 5). Requiere `faker` y `weasyprint` |

---

## Endpoints de la API

| Metodo | Ruta | Descripcion |
|---|---|---|
| `POST` | `/api/analyze` | Analiza un prompt: idioma, tokens, calidad (Qwen), mejora, modelo recomendado |
| `POST` | `/api/analyze/rubric` | Auditoria de prompt contra rubrica externa con Llama 3 (8B). Devuelve score 1-10, desglose, sugerencias y version optimizada |
| `POST` | `/api/reviews` | Procesa archivos con resenas (xlsx, csv, pdf, txt): tokens, traduccion, clasificacion, costos |
| `POST` | `/api/reviews/folder` | Igual que `/api/reviews` pero desde una carpeta del servidor |
| `POST` | `/api/reviews/export/{formato}` | Exporta resultados de resenas en `json`, `csv` o `xlsx` |
| `POST` | `/api/citas/analyze` | Procesa Excel con citas medicas: traduccion, optimizacion, ahorro de tokens, costos proyectados |
| `POST` | `/api/citas/analyze/folder` | Igual que `/api/citas/analyze` desde carpeta del servidor |
| `POST` | `/api/citas/export/{formato}` | Exporta resultados de optimizacion en `json`, `csv` o `xlsx` |
| `GET` | `/api/health` | Health check |

---

## Licencia

Este proyecto no incluye archivo de licencia explicito.
