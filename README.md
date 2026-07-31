# Token Analyzer

Herramienta de análisis, traducción y optimización de prompts y archivos Excel para reducir el consumo de tokens antes de enviarlos a un LLM.

## Qué hace

El proyecto tiene 3 funcionalidades principales:

| Caso | Descripción |
|---|---|
| **Caso 1 · Prompt Engineering** | Analiza un prompt individual: detecta idioma, cuenta tokens en español e inglés, evalúa su calidad con IA local (Qwen 2.5), genera una versión mejorada y recomienda el modelo de IA más adecuado. |
| **Caso 2 · Reseñas Excel** | Procesa archivos Excel/CSV/PDF/TXT con reseñas de productos: extrae el texto, cuenta tokens, traduce, clasifica por tipo de error y severidad, y simula costos de procesamiento a escala (10.000 reseñas/día). |
| **Caso 3 · Optimización de tokens** | Lee archivos Excel con mensajes (ej: citas médicas), los traduce al inglés, aplica una heurística de simplificación para reducir tokens, y exporta un nuevo archivo con el texto optimizado, métricas de ahorro y costos estimados. |

## Arquitectura

```
prompt_analizer/
├── backend/                     # API REST en FastAPI
│   ├── main.py                  # Endpoints y orquestación
│   ├── token_counter.py         # Toda la lógica de negocio
│   ├── criterios_evaluacion.json # Rúbrica de evaluación de prompts
│   └── requirements.txt         # Dependencias Python
├── frontend/                    # SPA en React + Vite
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js           # Proxy /api → localhost:8000
│   └── src/
│       ├── main.jsx             # Punto de entrada React
│       ├── App.jsx              # Todos los componentes
│       └── index.css            # Estilos (tema oscuro)
├── scripts/                     # Utilidades auxiliares
│   ├── cli.py                   # Contador de tokens por terminal
│   ├── generador_scripts.py     # Genera PDFs de contratos sintéticos
│   └── generar_contratos.py     # Script standalone para generar PDFs
├── generador_excel.py           # Genera Excel con 10K reseñas sintéticas
└── .gitignore
```

## Requerimientos

### Backend
- Python 3.12
- [Ollama](https://ollama.com) con los modelos `qwen2.5:0.5b` y `llama3:8b`
- Dependencias en `backend/requirements.txt`

### Frontend
- Node.js 18+
- Dependencias en `frontend/package.json`

## Dependencias

### Python (`backend/requirements.txt`)
| Paquete | Uso |
|---|---|
| `fastapi` | Framework REST |
| `uvicorn[standard]` | Servidor ASGI |
| `python-multipart` | Soporte para upload de archivos |
| `tiktoken` | Tokenización (encoding `gpt-4o` / `o200k_base`) |
| `deep-translator` | Traducción ES↔EN vía Google Translate |
| `ollama` | Cliente para modelos locales (Qwen 2.5, Llama 3) |
| `openpyxl` | Lectura/escritura de archivos Excel |
| `PyMuPDF` | Extracción de texto de PDFs |

### Node.js (`frontend/package.json`)
| Paquete | Uso |
|---|---|
| `react` / `react-dom` | UI |
| `vite` / `@vitejs/plugin-react` | Bundler y dev server |

## Modelos de IA utilizados

El proyecto usa modelos locales vía Ollama:

| Modelo | Tamaño | Uso |
|---|---|---|
| `qwen2.5:0.5b` | 442 MB | Evaluar calidad de prompts, clasificar reseñas, generar mejoras |
| `llama3:8b` | ~4.7 GB | Auditoría de prompts por rúbrica detallada |

Para tokenización usa `tiktoken` con encoding `gpt-4o`. La traducción se hace con Google Translate (sin IA local). El Caso 3 no usa modelos de IA — la clasificación y optimización son por reglas locales.

## Cómo correr el proyecto

### 1. Instalar dependencias

```bash
cd prompt_analizer

# Backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# Frontend
cd frontend
npm install
```

### 2. Iniciar Ollama y descargar modelos

```bash
ollama serve                    # En una terminal aparte
ollama pull qwen2.5:0.5b
ollama pull llama3:8b           # Solo para el endpoint /api/analyze/rubric
```

### 3. Ejecutar

**Terminal 1 — Backend (puerto 8000):**
```bash
cd prompt_analizer
source .venv/bin/activate
python -m backend.main
```

**Terminal 2 — Frontend (puerto 5173):**
```bash
cd prompt_analizer/frontend
npm run dev
```

Abrir `http://localhost:5173` en el navegador.

### 4. Solo backend (sin frontend)

```bash
cd prompt_analizer
source .venv/bin/activate
python -m backend.main
```

La API estará disponible en `http://localhost:8000`. La documentación interactiva (Swagger) en `http://localhost:8000/docs`.

## Endpoints de la API

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/analyze` | Analiza un prompt: idioma, tokens, calidad, mejora, modelo recomendado |
| `POST` | `/api/analyze/rubric` | Auditoría de prompt contra rúbrica con `llama3:8b` |
| `POST` | `/api/reviews` | Procesa archivos con reseñas: tokens, traducción, clasificación, costos |
| `POST` | `/api/reviews/folder` | Igual que `/api/reviews` pero desde carpeta local |
| `POST` | `/api/reviews/export/{formato}` | Exporta reseñas en JSON, CSV o XLSX |
| `POST` | `/api/citas/analyze` | Procesa Excel con mensajes: traducción, optimización, ahorro de tokens |
| `POST` | `/api/citas/analyze/folder` | Igual que `/api/citas/analyze` desde carpeta local |
| `POST` | `/api/citas/export/{formato}` | Exporta resultados de optimización en JSON, CSV o XLSX |
| `GET`  | `/api/health` | Health check |

## Parámetros de costos

| Parámetro | Valor |
|---|---|
| Precio por 1M tokens | $2.50 USD |
| Volumen reseñas/día | 10.000 |
| Volumen citas/día | 15.000 |
| Días por mes | 30 |

## Puntos importantes

- **Tiempos de espera**: el socket HTTP tiene un timeout global de 15 segundos para evitar que el servidor se cuelgue si Google Translate no responde.
- **Procesamiento batch**: el Caso 3 agrupa mensajes por `acción|especialidad|idioma` y procesa los grupos en paralelo (5 workers) para reducir el número de llamadas a Google Translate.
- **Clasificación híbrida**: el Caso 2 clasifica reseñas primero con reglas locales (keywords). Solo consulta a Ollama cuando la clasificación local tiene baja confianza.
- **Sin IA en Caso 3**: la extracción de esquemas médicos (acción, especialidad, horario) y la optimización de texto se hacen con reglas heurísticas locales, sin llamar a ningún modelo.
- **Optimización de tokens**: el Caso 3 elimina frases redundantes y muletillas del texto traducido para reducir el consumo de tokens sin alterar el significado.
- **Formatos de exportación**: todos los casos permiten exportar resultados en JSON, CSV y XLSX.
- **Auto-detección de columnas**: al subir un Excel, el sistema detecta automáticamente la columna que contiene el texto (reseña, mensaje, comentario, etc.).
- **Perfilado**: cada endpoint imprime en consola un desglose del tiempo invertido en cada etapa (lectura, procesamiento, clasificación, total).
