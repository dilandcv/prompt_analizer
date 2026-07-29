import re
import tiktoken
from deep_translator import GoogleTranslator

import json

try:
    import ollama
    OLLAMA_EVAL_MODEL = "qwen2.5:0.5b"
    OLLAMA_MEJORA_MODEL = "qwen2.5:0.5b"
    _ollama_client = ollama.Client(timeout=15)
    _ollama_disponible = True
except ImportError:
    ollama = None
    OLLAMA_EVAL_MODEL = "qwen2.5:0.5b"
    OLLAMA_MEJORA_MODEL = "qwen2.5:0.5b"
    _ollama_client = None
    _ollama_disponible = False



def _ollama_generate(prompt: str, model: str = None, max_tokens: int = 500,
                     temperature: float = 0.1) -> str:
    response = _ollama_client.generate(
        model=model or OLLAMA_MEJORA_MODEL,
        prompt=prompt,
        options={"temperature": temperature, "num_predict": max_tokens},
    )
    return response["response"].strip()


def _evaluar_con_qwen(texto: str) -> dict:
    """Evalua la calidad del prompt usando Qwen 2.5 con rubrica estricta.

    Usa una rubrica anclada de 7 dimensiones (0-20 puntos cada una) con
    descripciones explicitas de cada nivel para evitar inflacion de puntuaciones.
    La complejidad de la tarea se considera para ajustar expectativas.
    """
    prompt_ia = (
        "Eres un evaluador automatico de prompts. Aplica una rubrica ESTRICTA "
        "de 7 dimensiones. Se OBJETIVO y CONSISTENTE.\n\n"

        "=== ESCALA POR DIMENSION (0-20) ===\n"
        "0-4  AUSENTE: la dimension no aparece en el prompt.\n"
        "5-8  DEFICIENTE: solo una mencion vaga o implicita, sin sustancia.\n"
        "9-12 BASICO: cubierto minimamente, pero sin detalles especificos.\n"
        "13-16 BUENO: cubierto con detalles relevantes y concretos.\n"
        "17-20 EXCELENTE: cubierto excepcionalmente, con precision notable.\n\n"

        "=== REGLAS ANTI-INFLACION ===\n"
        "R1. La puntuacion POR DEFECTO de cualquier dimension es 5, nunca 10.\n"
        "R2. Solo se asigna >=13 si el prompt tiene detalles ESPECIFICOS.\n"
        "R3. Solo se asigna >=17 si es EXCEPCIONALMENTE detallado y concreto.\n"
        "R4. Sin contexto definido => maximo 4 puntos en contexto.\n"
        "R5. Sin restricciones explicitas => maximo 4 puntos en restricciones.\n"
        "R6. Sin formato de salida solicitado => maximo 4 puntos en formato.\n"
        "R7. Prompt vago o generico => maximo 8 puntos en especificidad.\n"
        "R8. Para tareas complejas (medicas, tecnicas, analiticas) se EXIGE "
        "mayor detalle para puntuar alto.\n\n"

        "=== DIMENSIONES ===\n"
        "1. claridad (0-20): ¿instruccion directa, sin ambiguedades, facil de "
        "entender a la primera lectura?\n"
        "2. contexto (0-20): ¿define rol, audiencia, nivel, situacion o proposito "
        "del prompt?\n"
        "3. objetivo (0-20): ¿especifica EXPLICITAMENTE que resultado concreto "
        "se espera?\n"
        "4. restricciones (0-20): ¿menciona limites de longitud, tono, exclusiones, "
        "restricciones de contenido?\n"
        "5. formato (0-20): ¿indica estructura deseada (secciones, listas, tablas, "
        "pasos numerados)?\n"
        "6. especificidad (0-20): ¿contiene detalles concretos, ejemplos, cifras, "
        "nombres propios? ¿evita ser vago?\n"
        "7. coherencia (0-20): ¿las ideas estan organizadas logicamente? ¿el prompt "
        "fluye bien?\n\n"

        "=== EJEMPLO DE CALIBRACION ===\n"
        'Prompt: "Explica que es Python"\n'
        "Evaluacion: claridad=9, contexto=3, objetivo=5, restricciones=2, "
        "formato=2, especificidad=3, coherencia=6\n"
        "Score=(9+3+5+2+2+3+6)/140*100=21 => nivel: Muy pobre\n\n"
        'Prompt: "Eres un profesor de programacion. Explica Python a estudiantes '
        'de primer ano de ingenieria: historia del lenguaje, tipos de datos con '
        'ejemplos de codigo, y estructuras de control. Respuesta de 500-800 palabras, '
        'organizada en secciones con subtitulos, tono formal."\n'
        "Evaluacion: claridad=16, contexto=17, objetivo=15, restricciones=17, "
        "formato=16, especificidad=17, coherencia=16\n"
        "Score=(16+17+15+17+16+17+16)/140*100=81 => nivel: Bueno\n\n"

        "=== FORMATO DE RESPUESTA ===\n"
        "Responde UNICAMENTE un JSON valido. Sin Markdown. Sin texto extra.\n"
        '{"score": <0-100>, "nivel": "<Excelente|Bueno|Aceptable|Deficiente|Muy pobre>", '
        '"metricas": {"claridad": <0-20>, "contexto": <0-20>, '
        '"objetivo": <0-20>, "restricciones": <0-20>, '
        '"formato": <0-20>, "especificidad": <0-20>, '
        '"coherencia": <0-20>}, '
        '"fortalezas": ["..."], "debilidades": ["..."], '
        '"recomendaciones": ["..."]}\n\n'
        "El score DEBE ser: suma de las 7 metricas / 140 * 100, redondeado.\n"
        "El nivel DEBE seguir la escala: 0-39=Muy pobre, 40-59=Deficiente, "
        "60-79=Aceptable, 80-89=Bueno, 90-100=Excelente.\n\n"
        f'Prompt a evaluar:\n"""{texto}"""'
    )
    respuesta = _ollama_generate(
        prompt_ia,
        model=OLLAMA_EVAL_MODEL,
        max_tokens=200,
        temperature=0.1,
    )
    return _parsear_json_qwen(respuesta)


def _parsear_json_qwen(texto: str) -> dict:
    """Intenta parsear el JSON devuelto por Qwen con multiples estrategias.

    Lanza ValueError si ninguna estrategia de parseo funciona.
    """
    texto = texto.strip()

    estrategias = [
        lambda t: json.loads(t),
        lambda t: json.loads(re.search(r"```(?:json)?\s*([\s\S]*?)```", t).group(1)),
        lambda t: json.loads(re.search(r"\{[\s\S]*\}", t).group(0)),
    ]

    for i, estrategia in enumerate(estrategias):
        try:
            return estrategia(texto)
        except (json.JSONDecodeError, AttributeError, TypeError):
            continue

    raise ValueError(f"No se pudo parsear el JSON de Qwen: {texto[:200]}")


def _normalizar_metricas(metricas: dict) -> dict:
    """Normaliza las metricas de Qwen al rango 0-20 si vienen en 0-100."""
    normalizadas = {}
    for clave, valor in metricas.items():
        if isinstance(valor, (int, float)):
            normalizadas[clave] = int(valor / 5) if valor > 20 else int(valor)
        else:
            normalizadas[clave] = 0
    return normalizadas


def _formatear_evaluacion_qwen(eval_qwen: dict) -> dict:
    """Convierte la evaluacion de Qwen al formato del template.

    El score se calcula SIEMPRE desde la suma de las 7 metricas para garantizar
    consistencia matematica y evitar puntuaciones infladas por Qwen.
    """
    metricas = _normalizar_metricas(eval_qwen.get("metricas", {}))
    suma_metricas = sum(metricas.values())
    score_final = min(100, round(suma_metricas / 140 * 100))

    if score_final >= 90:
        nivel = "excelente"
    elif score_final >= 80:
        nivel = "bueno"
    elif score_final >= 60:
        nivel = "aceptable"
    elif score_final >= 40:
        nivel = "deficiente"
    else:
        nivel = "muy-pobre"

    detalles = [
        ("Claridad", metricas.get("claridad", 0) * 5, "Claridad de la instruccion"),
        ("Contexto", metricas.get("contexto", 0) * 5, "Informacion de fondo proporcionada"),
        ("Objetivo", metricas.get("objetivo", 0) * 5, "Objetivo claramente definido"),
        ("Restricciones", metricas.get("restricciones", 0) * 5, "Limitaciones y condiciones"),
        ("Formato", metricas.get("formato", 0) * 5, "Estructura de salida solicitada"),
        ("Especificidad", metricas.get("especificidad", 0) * 5, "Nivel de detalle y concrecion"),
        ("Coherencia", metricas.get("coherencia", 0) * 5, "Organizacion interna del prompt"),
    ]

    return {
        "puntaje": score_final,
        "nivel": nivel,
        "detalles": detalles,
        "fortalezas": eval_qwen.get("fortalezas", []),
        "debilidades": eval_qwen.get("debilidades", []),
        "recomendaciones": eval_qwen.get("recomendaciones", []),
        "puntaje_ia": score_final,
        "puntaje_heuristico": score_final,
        "evaluacion_ia": True,
    }


def _evaluacion_heuristica_completa(texto: str) -> dict:
    """Evaluacion heuristica de respaldo cuando Ollama no esta disponible."""
    pt = _calcular_puntaje(texto)
    if pt >= 90:
        nivel = "excelente"
    elif pt >= 80:
        nivel = "bueno"
    elif pt >= 60:
        nivel = "aceptable"
    elif pt >= 40:
        nivel = "deficiente"
    else:
        nivel = "muy-pobre"
    detalle = _analizar_detalles(texto)
    return {
        "puntaje": pt, "nivel": nivel, "detalles": detalle,
        "fortalezas": [], "debilidades": [], "recomendaciones": [],
        "puntaje_ia": pt, "puntaje_heuristico": pt, "evaluacion_ia": False,
    }


PAL_ES = {"que", "de", "el", "la", "los", "las", "del", "con", "por", "para",
          "una", "como", "más", "pero", "sus", "son", "era", "han", "está",
          "muy", "sin", "entre", "todo", "eso", "esa", "este", "tiene", "hace",
          "dar", "ver", "saber", "poder", "otro", "cada", "nada", "algo",
          "siempre", "nunca", "después", "antes", "bueno", "malo", "mejor"}

PAL_EN = {"the", "and", "of", "to", "in", "is", "it", "you", "that", "was",
          "for", "are", "with", "they", "this", "have", "from", "not", "but",
          "what", "all", "were", "when", "can", "there", "which", "their",
          "will", "each", "about", "how", "out", "them", "then", "she", "many",
          "some", "these", "would", "other", "into", "more", "also", "its"}


def detectar_idioma(texto: str) -> str:
    texto_lower = texto.lower()
    palabras = re.findall(r"[a-záéíóúüñ]+", texto_lower)
    if not palabras:
        return "es"
    if re.search(r"[ñáéíóúü¿¡]", texto_lower):
        return "es"
    cnt_es = sum(1 for p in palabras if p in PAL_ES)
    cnt_en = sum(1 for p in palabras if p in PAL_EN)
    return "es" if cnt_es > cnt_en else "en"


def contar_tokens(texto: str) -> int:
    encoding = tiktoken.encoding_for_model("gpt-4o")
    tokens = encoding.encode(texto)
    return len(tokens)


def traducir(texto: str, origen: str, destino: str) -> str:
    try:
        traductor = GoogleTranslator(source=origen, target=destino)
        return traductor.translate(texto)
    except Exception:
        if _ollama_client is None:
            raise
        prompt = (
            f"Translate the following text from {origen.upper()} to {destino.upper()}. "
            f"Respond ONLY with the translation, no explanations:\n\n{texto}"
        )
        return _ollama_generate(prompt, max_tokens=200, temperature=0.1)


def traducir_a_ingles(texto: str) -> str:
    return traducir(texto, "es", "en")


def analizar_prompt(texto: str) -> dict:
    """Evalua la calidad del prompt usando Qwen 2.5 como evaluador principal.

    La heuristica solo se usa como respaldo cuando Ollama no responde o como
    validacion basica para prompts vacios o extremadamente cortos.
    """
    palabras = texto.split()
    texto_limpio = texto.strip()

    if len(palabras) == 0:
        return {
            "puntaje": 0, "nivel": "vacio", "detalles": [],
            "fortalezas": [], "debilidades": [], "recomendaciones": [],
            "puntaje_ia": 0, "puntaje_heuristico": 0, "evaluacion_ia": False,
        }

    if len(texto_limpio) < 10:
        return _evaluacion_heuristica_completa(texto)

    if _ollama_client is not None:
        try:
            eval_qwen = _evaluar_con_qwen(texto)
            if eval_qwen and isinstance(eval_qwen.get("score"), (int, float)):
                return _formatear_evaluacion_qwen(eval_qwen)
        except Exception:
            pass

    return _evaluacion_heuristica_completa(texto)


def _calcular_puntaje(texto: str) -> int:
    palabras = texto.split()
    oraciones = [o.strip() for o in re.split(r"[.!?]+", texto) if o.strip()]
    letras = len(texto)
    s = 0
    if letras >= 80:
        s += 30
    elif letras >= 30:
        s += 15
    else:
        s += 5
    if re.search(r"\d+", texto):
        s += 15
    if re.search(r"[A-ZÁÉÍÓÚÜÑ]", texto):
        s += 10
    if re.search(r"¿?\?$", texto.strip()) or re.search(
        r"\b(explica|describe|genera|crea|haz|escribe|traduce|analiza|compara|resume|lista|muestra|dame|quiero|necesito)\b",
        texto.lower(),
    ):
        s += 25
    if len(oraciones) >= 2:
        s += 10
    if len(palabras) > 0 and texto[0].isupper() and texto.strip()[-1] in ".!?":
        s += 10
    return min(100, s)


def _analizar_detalles(texto: str) -> list:
    palabras = texto.split()
    oraciones = [o.strip() for o in re.split(r"[.!?]+", texto) if o.strip()]
    letras = len(texto)
    d = []

    if letras >= 200:
        d.append(("Longitud", 20, "Buena extensión. Tienes contexto suficiente."))
    elif letras >= 80:
        d.append(("Longitud", 15, "Extensión adecuada. Puedes agregar más detalles."))
    elif letras >= 30:
        d.append(("Longitud", 10, "Corta. Describe mejor lo que necesitas."))
    else:
        d.append(("Longitud", 5, "Muy corto. Agrega más contexto."))

    esp = sum([
        bool(re.search(r"\d+", texto)),
        bool(re.search(r"[A-ZÁÉÍÓÚÜÑ]", texto)),
        bool(re.search(r"\b(como|ejemplo|específicamente|concreto|detalle|versión|tipo|clase|marca|modelo|año|día|mes)\b", texto.lower())),
    ])
    if esp >= 2:
        d.append(("Especificidad", 25, "Incluyes datos concretos y específicos."))
    elif esp == 1:
        d.append(("Especificidad", 15, "Agrega números, nombres o ejemplos concretos."))
    else:
        d.append(("Especificidad", 5, "Muy genérico. Sé más concreto."))

    if re.search(r"¿?\?$", texto.strip()) or re.search(
        r"\b(explica|describe|genera|crea|haz|escribe|traduce|analiza|compara|resume|lista|muestra|dame|quiero|necesito)\b",
        texto.lower(),
    ):
        d.append(("Claridad", 25, "Claro. Se entiende lo que pides."))
    else:
        d.append(("Claridad", 10, "Poco claro. Usa una pregunta o instrucción directa."))

    if len(oraciones) >= 3:
        d.append(("Estructura", 15, "Bien organizado en varias ideas."))
    elif len(oraciones) == 2:
        d.append(("Estructura", 10, "Separa mejor tus ideas."))
    else:
        d.append(("Estructura", 5, "Una sola idea. Divide el prompt."))

    mayus = texto[0].isupper() if texto else False
    punct = texto.strip()[-1] in ".!?" if texto.strip() else False
    if mayus and punct:
        d.append(("Gramática", 15, "Ortografía y puntuación correctas."))
    elif mayus or punct:
        d.append(("Gramática", 8, "Revisa mayúsculas o puntuación."))
    else:
        d.append(("Gramática", 3, "Corrige ortografía básica."))

    return d


def recomendar_modelo(texto: str, prompt_info: dict) -> dict:
    baja = texto.lower()
    largo = len(texto)
    num_palabras = len(texto.split())

    es_codigo = bool(re.search(
        r"\b(python|javascript|java|código|codigo|code|función|function|clase|class|def|"
        r"import|print|var|const|let|html|css|sql|bash|script|api|backend|frontend|"
        r"algoritmo|algorithm|debug|error|bug|compilar|compile|server|database|bd|"
        r"datos|archivo|file|csv|json|xml|endpoint|ruta|route)\b", baja))
    es_creativo = bool(re.search(
        r"\b(escribe|cuento|poema|historia|story|poem|creative|creativo|escribir|write|"
        r"novela|guion|artículo|article|blog|ensayo|essay|narrativa|narrative|imagina|"
        r"imagine|inventa|invent|crea|create|diseña|design)\b", baja))
    es_analitico = bool(re.search(
        r"\b(analiza|analyz|compara|compare|explain|explica|qué es|what is|how|"
        r"por qué|why|razón|reason|diferencia|difference|significa|meaning|"
        r"definición|definition|resume|summar|conclusión|conclusion|interpreta|interpret)\b",
        baja))
    es_largo = largo > 500 or num_palabras > 80
    es_simple = largo < 100 and num_palabras < 20

    if es_codigo:
        return {
            "modelo": "Claude 3.5 Sonnet",
            "alternativo": "GPT-4o",
            "razon": "Ideal para tareas de programación. Su amplio contexto y precisión en código lo hacen la mejor opción.",
            "icono": "💻",
            "ventaja": "Excelente en depuración, generación y refactorización de código.",
        }
    if es_creativo:
        return {
            "modelo": "GPT-4o",
            "alternativo": "Claude 3.5 Sonnet",
            "razon": "Destaca en tareas creativas con respuestas rápidas y coherentes.",
            "icono": "🎨",
            "ventaja": "Mejor equilibrio entre velocidad, creatividad y precio.",
        }
    if es_analitico:
        return {
            "modelo": "GPT-4o",
            "alternativo": "Gemini 1.5 Pro",
            "razon": "Excelente para análisis profundo y razonamiento estructurado.",
            "icono": "🔍",
            "ventaja": "Alta precisión en tareas de análisis y comparación.",
        }
    if es_largo:
        return {
            "modelo": "Claude 3.5 Sonnet",
            "alternativo": "Gemini 1.5 Pro",
            "razon": "Ventana de contexto de 200K tokens, ideal para textos extensos.",
            "icono": "📄",
            "ventaja": "Maneja documentos largos sin perder coherencia.",
        }
    if es_simple:
        return {
            "modelo": "GPT-4o-mini",
            "alternativo": "Claude 3 Haiku",
            "razon": "Para tareas simples y rápidas. Mucho más económico y igual de eficaz.",
            "icono": "⚡",
            "ventaja": "Hasta 30x más barato que GPT-4o para tareas sencillas.",
        }

    return {
        "modelo": "GPT-4o",
        "alternativo": "Claude 3.5 Sonnet",
        "razon": "El modelo más equilibrado para tareas generales.",
        "icono": "🤖",
        "ventaja": "Versátil, rápido y con excelente calidad en cualquier idioma.",
    }


def generar_ejemplo_mejora(texto: str) -> dict:
    """Genera un prompt mejorado con Qwen y lo traduce a ingles."""

    mejora_es = _construir_mejora(texto)

    mejora_en = traducir_a_ingles(mejora_es)

    tokens_es = contar_tokens(mejora_es)
    tokens_en = contar_tokens(mejora_en)

    if tokens_es <= tokens_en:
        recomendacion = "es"
        ahorro = tokens_en - tokens_es
    else:
        recomendacion = "en"
        ahorro = tokens_es - tokens_en

    return {
        "mejora_es": mejora_es,
        "mejora_en": mejora_en,
        "tokens_es": tokens_es,
        "tokens_en": tokens_en,
        "recomendacion": recomendacion,
        "ahorro": ahorro,
    }


def _construir_mejora(texto: str) -> str:
    """Construye una version mejorada del prompt usando una plantilla heuristica.

    Anade contexto, requisitos y formato de salida al prompt original para
    hacerlo mas efectivo. No depende de Ollama para ser instantaneo.
    """

    tiene_pregunta = bool(re.search(r"\?$", texto.strip()))
    tiene_verbo = bool(re.search(
        r"\b(explica|describe|genera|crea|haz|escribe|traduce|analiza|compara|resume|lista)\b",
        texto.lower(),
    ))
    ya_tiene_contexto = bool(re.search(
        r"\b(eres|act[uú]a|imagina|supon|como si|rol|eres un|actua como)\b", texto.lower()
    ))
    ya_tiene_formato = bool(re.search(
        r"\b(secciones|pasos|lista|tabla|json|markdown|esquema|estructura)\b", texto.lower()
    ))

    partes = []

    if not ya_tiene_contexto:
        partes.append(
            "Eres un asistente experto. Proporciona respuestas precisas, "
            "bien fundamentadas y utiles para el usuario."
        )

    if tiene_pregunta:
        partes.append(f"Pregunta:\n{texto}")
    elif tiene_verbo:
        partes.append(f"Tarea:\n{texto}")
    else:
        partes.append(f"Tarea:\n{texto}")

    requisitos = []
    if not ya_tiene_formato:
        requisitos.append("Responde de forma estructurada, con secciones claras y bien organizadas.")
    requisitos.append("Incluye ejemplos concretos que ilustren cada punto.")
    requisitos.append("Explica el razonamiento paso a paso cuando sea relevante.")
    requisitos.append("Se especifico: menciona detalles, nombres, cifras o casos de uso reales.")

    partes.append("Requisitos:\n- " + "\n- ".join(requisitos))

    return "\n\n".join(partes)


def _construir_mejora_con_feedback(texto_actual: str, evaluacion: dict) -> str:
    """Reintento de mejora usando las debilidades detectadas en la evaluacion."""
    if _ollama_client is None:
        return ""

    try:
        debilidades = "; ".join(evaluacion.get("debilidades", []))
        recomendaciones = "; ".join(evaluacion.get("recomendaciones", []))
        prompt_ia = (
            "Eres un experto en Prompt Engineering. El siguiente prompt "
            "mejorado aun tiene deficiencias detectadas por la evaluacion.\n\n"
            f"Debilidades detectadas: {debilidades}\n"
            f"Recomendaciones: {recomendaciones}\n\n"
            "Corrige esas debilidades y genera una nueva version optimizada. "
            "Responde SOLO con el prompt mejorado en espanol, sin explicaciones:\n\n"
            f"\"{texto_actual}\"\n\n"
            "Nueva version mejorada:"
        )
        mejora = _ollama_generate(
            prompt_ia,
            model=OLLAMA_MEJORA_MODEL,
            max_tokens=500,
            temperature=0.2,
        )
        if mejora and len(mejora) > 20:
            return mejora
    except Exception:
        pass
    return ""


# ═══════════════════════════════════════════
#  Módulo: Procesamiento de Reseñas Excel
# ═══════════════════════════════════════════

import io
import json as _json
from pathlib import Path

_PRECIO_POR_MILLON = 2.50
_RESENAS_POR_DIA = 10000
_DIAS_POR_MES = 30


def leer_excel_resenas(filepath: str, columna: str = None) -> tuple:
    """Lee un archivo Excel y extrae reseñas de una columna.

    Args:
        filepath: ruta al archivo .xlsx
        columna: nombre de columna a usar. Si es None, se auto-detecta.

    Returns:
        (resenas, columnas_disponibles) donde resenas es list[str] y
        columnas_disponibles es list[str] con los encabezados.
    """
    import openpyxl
    wb = openpyxl.load_workbook(filepath, read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    if not rows:
        return [], []

    headers = [str(h).strip() if h else "" for h in rows[0]]
    if not columna:
        columna = _detectar_columna_review(headers)
    if columna not in headers:
        raise ValueError(f"Columna '{columna}' no encontrada. Columnas disponibles: {headers}")
    col_idx = headers.index(columna)

    resenas = []
    for row in rows[1:]:
        if col_idx < len(row) and row[col_idx]:
            val = str(row[col_idx]).strip()
            if val and len(val) > 3:
                resenas.append(val)
    return resenas, headers


def leer_pdf_texto(filepath: str) -> str:
    """Extrae todo el texto de un archivo PDF usando PyMuPDF."""
    import fitz
    doc = fitz.open(filepath)
    texto = " ".join(page.get_text() for page in doc)
    doc.close()
    return texto.strip()


def leer_txt_texto(filepath: str) -> str:
    """Lee el contenido completo de un archivo TXT."""
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        return f.read().strip()


def leer_csv_resenas(filepath: str, columna: str = None) -> tuple:
    """Lee un CSV y extrae reseñas. Retorna (resenas, columnas_disponibles)."""
    import csv as _csv
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        reader = _csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        if not columna:
            columna = _detectar_columna_review(fieldnames)
        if columna not in fieldnames:
            raise ValueError(f"Columna '{columna}' no encontrada. Columnas disponibles: {fieldnames}")
        resenas = []
        for row in reader:
            val = row.get(columna, "").strip()
            if val and len(val) > 3:
                resenas.append(val)
    return resenas, fieldnames


def extraer_texto_archivo(filepath: str, filename: str) -> str:
    """Extrae texto de un archivo según su extensión. Soporta PDF, TXT."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == "pdf":
        return leer_pdf_texto(filepath)
    elif ext == "txt":
        return leer_txt_texto(filepath)
    raise ValueError(f"Formato no soportado: .{ext}")


def _detectar_columna_review(headers: list) -> str:
    """Auto-detecta la columna de reseñas entre los encabezados."""
    candidates = ["review", "comment", "feedback", "message",
                  "comentario", "reseña", "resena", "texto", "text",
                  "contenido", "descripcion", "descripción", "opinion",
                  "opinión", "valoracion", "valoración"]
    headers_lower = [h.lower() for h in headers]
    for c in candidates:
        if c in headers_lower:
            return headers[headers_lower.index(c)]
    # Si no encuentra ninguna, devuelve la primera columna de texto larga
    return headers[0] if headers else ""


def contar_tokens_texto(texto: str) -> int:
    """Cuenta tokens de un texto (wrapper de contar_tokens para claridad)."""
    return contar_tokens(texto)


def calcular_costo(tokens: int, precio_por_millon: float = None) -> float:
    """Calcula costo en USD dado un número de tokens."""
    precio = precio_por_millon if precio_por_millon is not None else _PRECIO_POR_MILLON
    return round(tokens / 1_000_000 * precio, 4)


def clasificar_resenas_qwen(resenas: list, chunk_size: int = 30, rapido: bool = False) -> list:
    """Clasifica reseñas usando Qwen 2.5 en lotes.

    Envía las reseñas en chunks para no exceder la ventana de contexto.
    Retorna una lista de dicts con error_type, component, severity,
    summary y category para cada reseña.
    """
    if rapido or _ollama_client is None:
        return [_clasificacion_fallback(r) for r in resenas]

    resultados = []
    for i in range(0, len(resenas), chunk_size):
        chunk = resenas[i : i + chunk_size]
        try:
            res = _clasificar_chunk_qwen(chunk)
            resultados.extend(res if isinstance(res, list) else
                              [_clasificacion_fallback(r) for r in chunk])
        except Exception:
            resultados.extend([_clasificacion_fallback(r) for r in chunk])
    return resultados


def _clasificar_chunk_qwen(chunk: list) -> list:
    """Clasifica un chunk de reseñas con una sola llamada a Qwen."""
    items = "\n".join(f'{i+1}. "{r}"' for i, r in enumerate(chunk))
    prompt = (
        "Eres un clasificador de reseñas de aplicaciones. Analiza cada reseña "
        "y genera un JSON con estos campos:\n"
        "- error_type: crash, performance, loading_failure, bug, ui_issue, "
        "feature_request, other\n"
        "- component: nombre del componente afectado\n"
        "- severity: high, medium, low\n"
        "- summary: resumen en inglés en una frase\n"
        "- category: bug, performance, feature, other\n\n"
        "Reseñas:\n" + items + "\n\n"
        "Responde SOLO con un array JSON con un objeto por reseña, en el "
        "mismo orden. Sin markdown ni texto adicional:\n"
        '[{"error_type":"...","component":"...","severity":"...",'
        '"summary":"...","category":"..."}, ...]'
    )
    respuesta = _ollama_generate(
        prompt, model=OLLAMA_EVAL_MODEL,
        max_tokens=3000, temperature=0.1,
    )
    parsed = _parsear_json_qwen(respuesta)
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict) and len(chunk) == 1:
        return [parsed]
    return [_clasificacion_fallback(r) for r in chunk]


def _clasificacion_fallback(texto: str) -> dict:
    """Clasificación por keywords cuando Qwen no está disponible."""
    t = texto.lower()
    if any(p in t for p in ["cierra", "crash", "crashea", "congela", "reinicia"]):
        err = "crash"
    elif any(p in t for p in ["lento", "lenta", "tarda", "demora"]):
        err = "performance"
    elif any(p in t for p in ["no carga", "no abre", "pantalla blanca", "blanco"]):
        err = "loading_failure"
    elif any(p in t for p in ["error", "falla", "roto", "bug"]):
        err = "bug"
    elif any(p in t for p in ["quisiera", "sería bueno", "me gustaría", "sugiero"]):
        err = "feature_request"
    else:
        err = "other"

    if any(p in t for p in ["foto", "imagen", "perfil", "galeria", "cámara", "camara"]):
        comp = "profile_picture_upload"
    elif any(p in t for p in ["pago", "compra", "tarjeta", "precio", "checkout"]):
        comp = "payment_flow"
    elif any(p in t for p in ["login", "sesión", "sesion", "contraseña", "registro"]):
        comp = "authentication"
    elif any(p in t for p in ["notificación", "notificacion", "aviso"]):
        comp = "notifications"
    else:
        comp = "general_ui"

    if any(p in t for p in ["siempre", "cada vez", "constante", "todo el tiempo"]):
        sev = "high"
    elif any(p in t for p in ["a veces", "ocasional", "raro"]):
        sev = "low"
    else:
        sev = "medium"

    return {
        "error_type": err, "component": comp, "severity": sev,
        "summary": texto[:120], "category": "bug" if err != "performance" else "performance",
    }


def leer_carpeta_excel(ruta_carpeta: str, columna: str = None) -> tuple:
    """Lee una carpeta con archivos .xlsx y consolida todas las reseñas.

    Args:
        ruta_carpeta: ruta al directorio que contiene los .xlsx.
        columna: nombre de columna a usar. Si es None, se auto-detecta.

    Returns:
        (resenas, columnas_disponibles) donde resenas es list[str] y
        columnas_disponibles es list[str] con headers de todos los archivos.
    """
    carpeta = Path(ruta_carpeta)
    if not carpeta.is_dir():
        raise FileNotFoundError(f"La carpeta no existe: {ruta_carpeta}")

    archivos_xlsx = sorted(carpeta.glob("*.xlsx"))
    if not archivos_xlsx:
        raise ValueError(f"No se encontraron archivos .xlsx en: {ruta_carpeta}")

    try:
        import pandas as pd
    except ImportError:
        pandas = None

    todas_resenas = []
    columnas_globales = set()

    for archivo in archivos_xlsx:
        try:
            if pandas is not None:
                df = pd.read_excel(archivo, dtype=str)
                headers = list(df.columns)
                columnas_globales.update(headers)

                col = columna if columna else _detectar_columna_review(headers)
                if col not in headers:
                    col = headers[0] if headers else ""

                if col in df.columns:
                    valores = df[col].dropna().astype(str).str.strip()
                    resenas_archivo = [v for v in valores if len(v) > 3]
                else:
                    resenas_archivo = []
            else:
                resenas_archivo, headers = leer_excel_resenas(str(archivo), columna)
                columnas_globales.update(headers)

            todas_resenas.extend(resenas_archivo)
        except Exception as e:
            raise ValueError(f"Error al leer {archivo.name}: {e}")

    if not todas_resenas:
        raise ValueError("No se encontraron reseñas en los archivos.")

    return todas_resenas, sorted(columnas_globales)


# ═══════════════════════════════════════════
#  Módulo: Análisis de Prompt por Rúbrica
# ═══════════════════════════════════════════

_RUBRICA_PATH = Path(__file__).parent / "criterios_evaluacion.json"
try:
    with open(_RUBRICA_PATH, "r", encoding="utf-8") as _f:
        RUBRICA = json.load(_f)
except (FileNotFoundError, json.JSONDecodeError):
    RUBRICA = {}

OLLAMA_RUBRIC_MODEL = "llama3:8b"


def _analizar_prompt_por_rubrica(texto: str) -> dict:
    """Evalua un prompt contra la rubrica usando llama3:8b con formato JSON."""
    system_instruction = (
        "Eres un Ingeniero de Prompts Senior y Auditor de LLMs.\n"
        "Audita el prompt del usuario aplicando RIGIDAMENTE estos criterios:\n\n"
        f"{json.dumps(RUBRICA, ensure_ascii=False, indent=2)}\n\n"
        "Instrucciones:\n"
        "1. Evalua cada criterio y calcula la puntuacion total de 1 a 100.\n"
        "2. Divide el puntaje final entre 10 para dar una nota de 1.0 a 10.0.\n"
        "3. Genera una version optimizada en espanol y otra en ingles.\n\n"
        "Responde UNICAMENTE en JSON estricto, sin markdown ni texto extra:\n"
        "{\n"
        '  "calidad_score": <1.0 a 10.0>,\n'
        '  "desglose_puntaje": {\n'
        '    "claridad_y_objetivo": <0-25>,\n'
        '    "concision_y_eficiencia_tokens": <0-25>,\n'
        '    "contexto_y_restricciones": <0-20>,\n'
        '    "estructura_y_formato": <0-15>,\n'
        '    "idioma_y_tokenizacion": <0-15>\n'
        "  },\n"
        '  "analisis_critico": "justificacion de puntos restados segun la rubrica",\n'
        '  "sugerencias": ["sugerencia 1", "sugerencia 2"],\n'
        '  "prompt_optimizado_es": "version mejorada en espanol",\n'
        '  "prompt_optimizado_en": "version mejorada en ingles"\n'
        "}"
    )
    try:
        response = _ollama_client.chat(
            model=OLLAMA_RUBRIC_MODEL,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": f"Prompt a auditar: {texto}"},
            ],
            options={"temperature": 0.1, "num_predict": 800},
            format={"type": "json_object"},
        )
        return json.loads(response["message"]["content"])
    except Exception as e:
        raise RuntimeError(f"Error en la evaluacion por rubrica: {e}")


def _analizar_por_rubrica_fallback(texto: str) -> dict:
    """Evaluacion basica cuando la rubrica con Ollama no esta disponible."""
    palabras = len(texto.split())
    if palabras < 5:
        score = 2.0
        analisis = "Prompt extremadamente corto. Necesita mas contexto y especificidad."
    elif palabras < 15:
        score = 4.0
        analisis = "Prompt basico. Agregar contexto, restricciones y formato de salida."
    elif palabras < 40:
        score = 6.0
        analisis = "Prompt aceptable. Podria beneficiarse de ejemplos y restricciones explicitas."
    else:
        score = 7.5
        analisis = "Prompt con buena cantidad de contexto. Refinar formato y concision."

    return {
        "calidad_score": score,
        "desglose_puntaje": {
            "claridad_y_objetivo": int(score * 2.5),
            "concision_y_eficiencia_tokens": int(score * 2.5),
            "contexto_y_restricciones": int(score * 2),
            "estructura_y_formato": int(score * 1.5),
            "idioma_y_tokenizacion": int(score * 1.5),
        },
        "analisis_critico": analisis,
        "sugerencias": [
            "Define un rol y audiencia para el modelo.",
            "Especifica el formato de salida deseado (JSON, lista, secciones).",
            "Agrega restricciones de tono, longitud o exclusiones.",
        ],
        "prompt_optimizado_es": texto,
        "prompt_optimizado_en": texto,
    }


def analizar_prompt_rubrica(texto: str) -> dict:
    """Pipeline completo de analisis por rubrica.

    Evalua el prompt, genera versiones optimizadas en ES/EN, y
    calcula el ahorro de tokens al usar la version en ingles.
    """
    texto = texto.strip()
    if not texto:
        return {"error": "El prompt no puede estar vacio."}

    enc = tiktoken.get_encoding("cl100k_base")

    try:
        english_prompt = traducir(texto, "es", "en")
    except Exception:
        english_prompt = texto

    tokens_es_orig = len(enc.encode(texto))
    tokens_en_orig = len(enc.encode(english_prompt))

    if _ollama_client is not None:
        try:
            ia_data = _analizar_prompt_por_rubrica(texto)
        except Exception:
            ia_data = _analizar_por_rubrica_fallback(texto)
    else:
        ia_data = _analizar_por_rubrica_fallback(texto)

    opt_es = ia_data.get("prompt_optimizado_es", texto)
    opt_en = ia_data.get("prompt_optimizado_en", english_prompt)

    tokens_opt_es = len(enc.encode(opt_es)) if opt_es else 0
    tokens_opt_en = len(enc.encode(opt_en)) if opt_en else 0

    ahorro = max(0, tokens_es_orig - tokens_opt_en)
    pct_ahorro = round(ahorro / tokens_es_orig * 100, 1) if tokens_es_orig > 0 else 0

    return {
        "original": {
            "es_text": texto,
            "es_tokens": tokens_es_orig,
            "en_text": english_prompt,
            "en_tokens": tokens_en_orig,
        },
        "evaluacion": {
            "score": ia_data.get("calidad_score", 5.0),
            "desglose": ia_data.get("desglose_puntaje", {}),
            "analisis": ia_data.get("analisis_critico", ""),
            "sugerencias": ia_data.get("sugerencias", []),
        },
        "optimizado": {
            "es_text": opt_es,
            "es_tokens": tokens_opt_es,
            "en_text": opt_en,
            "en_tokens": tokens_opt_en,
        },
        "ahorro": {
            "tokens_ahorrados": ahorro,
            "porcentaje_ahorro": pct_ahorro,
        },
    }
