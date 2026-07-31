"""Token Analyzer — FastAPI Backend."""
import sys, time as _time

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import io, json as _json, tempfile, os as _os, csv as _csv

from backend.token_counter import (
    contar_tokens, traducir, detectar_idioma,
    analizar_prompt, generar_ejemplo_mejora, recomendar_modelo,
    leer_excel_resenas, leer_csv_resenas, extraer_texto_archivo,
    leer_carpeta_excel,
    clasificar_resenas_qwen, calcular_costo, contar_tokens_texto,
    _clasificacion_fallback,
    analizar_prompt_rubrica,
    leer_excel_citas_medicas, leer_carpeta_excel_citas,
    extraer_esquema_medico, _traducir_lote, _limpiar_cache_traducciones,
    _obtener_metricas_cache,
    optimizar_texto, _calcular_ahorro,
    _RESENAS_POR_DIA, _DIAS_POR_MES,
)

app = FastAPI(title="Token Analyzer API", version="2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── Configuración de rendimiento ──

CHUNK_SIZE = 3000
MAX_TRANSLATION_WORKERS = 5
MAX_LLM_WORKERS = 4

# ── Prompt Analysis ──

@app.post("/api/analyze")
async def analyze_prompt(texto: str = Form("")):
    import time
    t_total = time.perf_counter()

    texto = texto.strip()
    if not texto:
        raise HTTPException(400, "Texto vacío")

    # ── Detección + traducción ──
    t0 = time.perf_counter()
    idioma = detectar_idioma(texto)
    try:
        if idioma == "es":
            tokens_orig = contar_tokens(texto)
            traduccion = traducir(texto, "es", "en")
            tokens_trad = contar_tokens(traduccion)
        else:
            traduccion = traducir(texto, "en", "es")
            tokens_orig = contar_tokens(texto)
            tokens_trad = contar_tokens(traduccion)
    except Exception:
        traduccion = ""
        tokens_orig = contar_tokens(texto)
        tokens_trad = 0
    t1 = time.perf_counter()

    # ── Evaluación de calidad ──
    try:
        prompt = analizar_prompt(texto)
    except Exception:
        prompt = {"puntaje": 0, "nivel": "error", "detalles": [],
                  "fortalezas": [], "debilidades": [], "recomendaciones": [],
                  "puntaje_ia": 0, "puntaje_heuristico": 0, "evaluacion_ia": False}
    t2 = time.perf_counter()

    # ── Mejora + recomendación ──
    optimo = prompt["puntaje"] >= 80
    try:
        mejora = None if optimo else generar_ejemplo_mejora(texto)
    except Exception:
        mejora = None
    modelo = recomendar_modelo(texto, prompt)
    t3 = time.perf_counter()

    print(f"""
[Prompt] idioma={idioma} tokens={tokens_orig}/{tokens_trad} puntaje={prompt['puntaje']} nivel={prompt['nivel']}
  Traduccion....{t1 - t0:.2f}s
  Evaluacion....{t2 - t1:.2f}s  (IA={prompt.get('evaluacion_ia', False)})
  Mejora........{t3 - t2:.2f}s
  TOTAL.........{t3 - t_total:.2f}s""")

    return {
        "original": texto,
        "idioma": idioma,
        "tokens_orig": tokens_orig,
        "tokens_trad": tokens_trad,
        "traduccion": traduccion,
        "prompt": prompt,
        "optimo": optimo,
        "mejora": mejora,
        "modelo": modelo,
    }


# ── Rubric Analysis ──

@app.post("/api/analyze/rubric")
async def analyze_rubric(texto: str = Form("")):
    texto = texto.strip()
    if not texto:
        raise HTTPException(400, "El prompt no puede estar vacio.")
    try:
        result = analizar_prompt_rubrica(texto)
    except Exception as e:
        raise HTTPException(500, f"Error auditando el prompt: {str(e)}")
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


# ── Excel / File Reviews ──

def _procesar_resenas(todas_resenas: list, optimizar: bool, rapido: bool = False) -> list:
    """Procesa reseñas con agrupacion por sentimiento|categoria.

    1. Clasifica localmente cada reseña (sentimiento, categoria).
    2. Agrupa por clave compuesta (sentimiento|categoria).
    3. Traduce cada grupo en lote (una llamada Google Translate por grupo).
    4. Cuenta tokens de las traducciones.
    """
    import itertools, concurrent.futures

    # ── Fase 1: Conteo de tokens + clasificacion local ──
    resultados = []
    for texto in todas_resenas:
        tokens_es = contar_tokens_texto(texto)
        clasif = _clasificacion_fallback(texto)
        clave = f"{clasif['sentimiento']}|{clasif['category']}"
        resultados.append({
            "original": texto,
            "traduccion": "",
            "tokens_es": tokens_es,
            "tokens_en": tokens_es,
            "_clave": clave,
        })

    if not optimizar:
        for r in resultados:
            r.pop("_clave", None)
        return resultados

    # ── Fase 2: Agrupamiento ──
    resultados.sort(key=lambda r: r["_clave"])
    grupos = {k: list(g) for k, g in itertools.groupby(resultados, key=lambda r: r["_clave"])}

    # ── Fase 3: Traduccion por grupo (concurrente) ──
    grupos_lista = list(grupos.items())
    max_workers = min(len(grupos_lista), MAX_TRANSLATION_WORKERS)

    def _traducir_grupo(item):
        clave, grupo = item
        textos = [r["original"] for r in grupo]
        traducciones = _traducir_lote(textos, "es")
        for j, r in enumerate(grupo):
            if j < len(traducciones) and traducciones[j]:
                r["traduccion"] = traducciones[j]
                r["tokens_en"] = contar_tokens_texto(traducciones[j])
        return clave, len(grupo)

    completados = 0
    total_grupos = len(grupos_lista)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futuros = {ex.submit(_traducir_grupo, g): g for g in grupos_lista}
        for futuro in concurrent.futures.as_completed(futuros):
            clave, tam = futuro.result()
            completados += 1
            print(f"  [Reviews] Traducido {completados}/{total_grupos} "
                  f"'{clave}': {tam} reseñas")

    print(f"  [Reviews] Agrupacion: {total_grupos} grupos desde "
          f"{len(todas_resenas)} reseñas")

    for r in resultados:
        r.pop("_clave", None)

    return resultados


def _calcular_stats(resultados: list, total_es: int, total_en: int) -> dict:
    n = len(resultados)
    costo_diario_es = calcular_costo(total_es * _RESENAS_POR_DIA / n) if n else 0
    costo_diario_en = calcular_costo(total_en * _RESENAS_POR_DIA / n) if n else 0
    costo_mensual_es = round(costo_diario_es * _DIAS_POR_MES, 2)
    costo_mensual_en = round(costo_diario_en * _DIAS_POR_MES, 2)
    costo_anual_es = round(costo_mensual_es * 12, 2)
    costo_anual_en = round(costo_mensual_en * 12, 2)
    ahorro_diario = round(costo_diario_es - costo_diario_en, 2)
    ahorro_mensual = round(costo_mensual_es - costo_mensual_en, 2)
    ahorro_anual = round(costo_anual_es - costo_anual_en, 2)
    pct_ahorro = round(ahorro_mensual / costo_mensual_es * 100, 1) if costo_mensual_es > 0 else 0
    return {
        "total_resenas": n,
        "total_tokens_es": total_es,
        "total_tokens_en": total_en,
        "promedio_es": round(total_es / n) if n else 0,
        "promedio_en": round(total_en / n) if n else 0,
        "ahorro_diario": ahorro_diario,
        "ahorro_mensual": ahorro_mensual,
        "ahorro_anual": ahorro_anual,
        "costo_diario_es": costo_diario_es,
        "costo_diario_en": costo_diario_en,
        "costo_mensual_es": costo_mensual_es,
        "costo_mensual_en": costo_mensual_en,
        "costo_anual_es": costo_anual_es,
        "costo_anual_en": costo_anual_en,
        "ahorro": ahorro_mensual,
        "pct_ahorro": pct_ahorro,
    }


@app.post("/api/reviews")
async def process_reviews(
    archivos: list[UploadFile] = File(...),
    columna: str = Form(""),
    optimizar: bool = Form(False),
    rapido: bool = Form(False),
):
    import time
    t_total = time.perf_counter()
    _limpiar_cache_traducciones()

    # ── Lectura de archivos ──
    t0 = time.perf_counter()
    todas_resenas = []
    columnas_globales = set()

    for archivo in archivos:
        if not archivo.filename:
            continue
        ext = archivo.filename.rsplit(".", 1)[-1].lower() if "." in archivo.filename else ""
        if ext not in ("xlsx", "csv", "pdf", "txt"):
            continue
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix="." + ext)
        tmp.write(await archivo.read())
        tmp.close()
        try:
            if ext == "xlsx":
                resenas, headers = leer_excel_resenas(tmp.name, columna or None)
                todas_resenas.extend(resenas)
                columnas_globales.update(headers)
            elif ext == "csv":
                resenas, headers = leer_csv_resenas(tmp.name, columna or None)
                todas_resenas.extend(resenas)
                columnas_globales.update(headers)
            elif ext in ("pdf", "txt"):
                texto = extraer_texto_archivo(tmp.name, archivo.filename)
                if texto:
                    for linea in texto.split("\n"):
                        linea = linea.strip()
                        if linea and len(linea) > 5:
                            todas_resenas.append(linea)
        finally:
            try:
                _os.unlink(tmp.name)
            except OSError:
                pass

    if not todas_resenas:
        raise HTTPException(400, "No se encontraron reseñas en los archivos.")
    t1 = time.perf_counter()

    # ── Procesamiento por chunks ──
    todos_resultados = []
    total_chunks = (len(todas_resenas) + CHUNK_SIZE - 1) // CHUNK_SIZE
    for ci in range(0, len(todas_resenas), CHUNK_SIZE):
        chunk = todas_resenas[ci:ci + CHUNK_SIZE]
        chunk_resultados = _procesar_resenas(chunk, optimizar, rapido)
        todos_resultados.extend(chunk_resultados)
        if total_chunks > 1:
            print(f"  [Reviews] Chunk {ci // CHUNK_SIZE + 1}/{total_chunks}: "
                  f"{len(chunk)} reseñas")

    resultados = todos_resultados
    total_es = sum(r["tokens_es"] for r in resultados)
    total_en = sum(r["tokens_en"] for r in resultados)
    t2 = time.perf_counter()

    # ── Clasificacion ──
    textos_para_clasificar = [r["traduccion"] if (optimizar and r["traduccion"]) else r["original"] for r in resultados]
    clasificaciones = clasificar_resenas_qwen(textos_para_clasificar, rapido=rapido)
    for i, r in enumerate(resultados):
        if i < len(clasificaciones):
            r["clasificacion"] = clasificaciones[i]
        r["costo"] = calcular_costo(r["tokens_en"] if optimizar else r["tokens_es"])
    t3 = time.perf_counter()

    # ── Stats ──
    stats = _calcular_stats(resultados, total_es, total_en)
    t4 = time.perf_counter()

    # ── Perfilado ──
    n = len(todas_resenas)
    n_grupos = len(set(
        f"{c.get('error_type','')}|{c.get('category','')}|{c.get('sentimiento','')}"
        for c in clasificaciones
    ))
    mt = _obtener_metricas_cache()
    print(f"""
========== PERFIL DE EJECUCION ==========
  Lectura Excel........{t1 - t0:.2f}s  ({n} reseñas)
  Tokens + traduccion..{t2 - t1:.2f}s
  Clasificacion........{t3 - t2:.2f}s  ({n_grupos} grupos detectados)
  Stats................{t4 - t3:.3f}s
  TOTAL................{t4 - t_total:.2f}s
-----------------------------------------
  Textos totales.......{mt.get('textos_originales', 0)}
  Textos unicos........{mt.get('textos_unicos', 0)}
  Peticiones Google....{mt.get('peticiones_google', 0)}
  Reduccion............{n - mt.get('peticiones_google', 0)} llamadas
=========================================""")

    return {
        "resultados": resultados,
        "stats": stats,
        "columnas_disponibles": sorted(columnas_globales),
        "optimizar": optimizar,
    }


# ── Folder Ingest ──

@app.post("/api/reviews/folder")
async def process_reviews_folder(
    carpeta: str = Form(...),
    columna: str = Form(""),
    optimizar: bool = Form(False),
    rapido: bool = Form(False),
):
    _limpiar_cache_traducciones()
    if not carpeta.strip():
        raise HTTPException(400, "Debe especificar una ruta de carpeta.")

    try:
        todas_resenas, columnas_globales = leer_carpeta_excel(carpeta.strip(), columna or None)
    except FileNotFoundError as e:
        raise HTTPException(400, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))

    if not todas_resenas:
        raise HTTPException(400, "No se encontraron reseñas en la carpeta.")

    todos_resultados = []
    for ci in range(0, len(todas_resenas), CHUNK_SIZE):
        chunk = todas_resenas[ci:ci + CHUNK_SIZE]
        todos_resultados.extend(_procesar_resenas(chunk, optimizar, rapido))
    resultados = todos_resultados
    total_es = sum(r["tokens_es"] for r in resultados)
    total_en = sum(r["tokens_en"] for r in resultados)

    textos_para_clasificar = [r["traduccion"] if (optimizar and r["traduccion"]) else r["original"] for r in resultados]
    clasificaciones = clasificar_resenas_qwen(textos_para_clasificar, rapido=rapido)
    for i, r in enumerate(resultados):
        if i < len(clasificaciones):
            r["clasificacion"] = clasificaciones[i]
        r["costo"] = calcular_costo(r["tokens_en"] if optimizar else r["tokens_es"])

    stats = _calcular_stats(resultados, total_es, total_en)

    return {
        "resultados": resultados,
        "stats": stats,
        "columnas_disponibles": columnas_globales,
        "optimizar": optimizar,
    }


# ── Export ──

class ExportRequest(BaseModel):
    resultados: list


@app.post("/api/reviews/export/{formato}")
async def export_reviews(formato: str, body: ExportRequest):
    resultados = body.resultados
    if not resultados:
        raise HTTPException(400, "Sin datos")

    if formato == "json":
        out = io.BytesIO(_json.dumps(resultados, indent=2, ensure_ascii=False).encode("utf-8"))
        return StreamingResponse(out, media_type="application/json",
                                 headers={"Content-Disposition": "attachment; filename=reviews.json"})

    elif formato == "csv":
        out = io.StringIO()
        w = _csv.writer(out)
        w.writerow(["Original", "Traducción", "Tokens ES", "Tokens EN",
                     "Costo", "Error Type", "Component", "Severity", "Category"])
        for r in resultados:
            c = r.get("clasificacion", {})
            w.writerow([r.get("original", ""), r.get("traduccion", ""),
                         r.get("tokens_es", 0), r.get("tokens_en", 0),
                         r.get("costo", 0), c.get("error_type", ""),
                         c.get("component", ""), c.get("severity", ""),
                         c.get("category", "")])
        out.seek(0)
        bio = io.BytesIO(out.getvalue().encode("utf-8-sig"))
        return StreamingResponse(bio, media_type="text/csv",
                                 headers={"Content-Disposition": "attachment; filename=reviews.csv"})

    elif formato == "xlsx":
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Reseñas"
        ws.append(["Original", "Traducción", "Tokens ES", "Tokens EN",
                    "Costo", "Error Type", "Component", "Severity", "Category"])
        for r in resultados:
            c = r.get("clasificacion", {})
            ws.append([r.get("original", ""), r.get("traduccion", ""),
                        r.get("tokens_es", 0), r.get("tokens_en", 0),
                        r.get("costo", 0), c.get("error_type", ""),
                        c.get("component", ""), c.get("severity", ""),
                        c.get("category", "")])
        out = io.BytesIO()
        wb.save(out)
        out.seek(0)
        return StreamingResponse(out,
                                 media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                 headers={"Content-Disposition": "attachment; filename=reviews.xlsx"})

    raise HTTPException(400, "Formato no soportado")


# ═══════════════════════════════════════════
#  Caso 3 — Citas Médicas
# ═══════════════════════════════════════════

_CITAS_POR_DIA = 15000


def _procesar_mensaje_cita(texto: str, optimizar: bool) -> dict:
    """Pipeline completo de optimizacion de un mensaje.

    1. Contar tokens en español
    2. Traducir al ingles
    3. Verificar que la traduccion no este vacia
    4. Optimizar el texto traducido
    5. Contar tokens del texto optimizado
    6. Calcular ahorro y costos
    """
    tokens_es = contar_tokens_texto(texto)
    idioma_detectado = detectar_idioma(texto)

    costo_orig = calcular_costo(tokens_es)

    if not optimizar:
        return {
            "original": texto,
            "traduccion": "",
            "texto_optimizado": texto,
            "idioma": idioma_detectado,
            "tokens_original": tokens_es,
            "tokens_traduccion": tokens_es,
            "tokens_optimizado": tokens_es,
            "tokens_ahorrados": 0,
            "porcentaje_reduccion": 0.0,
            "costo_original": costo_orig,
            "costo_optimizado": costo_orig,
        }

    # ── Traducir ──
    try:
        if idioma_detectado == "es":
            traduccion = traducir(texto, "es", "en")
            idioma_opt = "en"
        else:
            traduccion = traducir(texto, "en", "es")
            idioma_opt = "es"
    except Exception as e:
        print(f"  [DEBUG] Error traduciendo: {e}")
        traduccion = ""

    if not traduccion or not traduccion.strip():
        print(f"  [DEBUG] Traduccion vacia para: {texto[:60]}...")
        return {
            "original": texto,
            "traduccion": "",
            "texto_optimizado": texto,
            "idioma": idioma_detectado,
            "tokens_original": tokens_es,
            "tokens_traduccion": tokens_es,
            "tokens_optimizado": tokens_es,
            "tokens_ahorrados": 0,
            "porcentaje_reduccion": 0.0,
            "costo_original": costo_orig,
            "costo_optimizado": costo_orig,
        }

    tokens_trad = contar_tokens_texto(traduccion)

    # ── Optimizar ──
    texto_opt = _optimizar_con_llm(traduccion, idioma_opt)
    if not texto_opt or not texto_opt.strip():
        print(f"  [DEBUG] Optimizacion vacia, usando traduccion literal")
        texto_opt = traduccion

    tokens_opt = contar_tokens_texto(texto_opt)
    metrica = _calcular_ahorro(tokens_es, tokens_opt)
    costo_opt = calcular_costo(tokens_opt)

    print(f"  [DEBUG] Original ({tokens_es}t): {texto[:50]}...")
    print(f"  [DEBUG] Traduccion ({tokens_trad}t): {traduccion[:50]}...")
    print(f"  [DEBUG] Optimizado ({tokens_opt}t): {texto_opt[:50]}...")
    print(f"  [DEBUG] Ahorro: {metrica['ahorro']}t ({metrica['pct_reduccion']}%)")

    return {
        "original": texto,
        "traduccion": traduccion,
        "texto_optimizado": texto_opt,
        "idioma": idioma_opt,
        "tokens_original": tokens_es,
        "tokens_traduccion": tokens_trad,
        "tokens_optimizado": tokens_opt,
        "tokens_ahorrados": metrica["ahorro"],
        "porcentaje_reduccion": metrica["pct_reduccion"],
        "costo_original": costo_orig,
        "costo_optimizado": costo_opt,
    }


def _procesar_citas_batch(citas: list, optimizar: bool) -> list:
    """Pipeline de optimizacion con agrupacion inteligente.

    Fase 1: extrae esquema medico y cuenta tokens (local).
    Fase 2: agrupa por clave compuesta (accion|especialidad|idioma).
    Fase 3: traduce cada grupo en lote.
    Fase 4: optimiza cada texto y calcula ahorro.
    """
    import time, itertools, concurrent.futures

    t_total = time.time()

    # ── Fase 1: Schemas + conteo ──
    t0 = time.time()
    mensajes = []
    for cita in citas:
        texto = cita["mensaje_texto"]
        tokens_es = contar_tokens_texto(texto)
        idioma = detectar_idioma(texto)
        esquema = extraer_esquema_medico(texto)
        clave = f"{esquema['accion']}|{esquema['especialidad']}|{idioma}"
        costo_orig = calcular_costo(tokens_es)
        mensajes.append({
            "paciente_id": cita.get("paciente_id", ""),
            "original": texto,
            "traduccion": "",
            "texto_optimizado": texto,
            "idioma": idioma,
            "tokens_original": tokens_es,
            "tokens_traduccion": tokens_es,
            "tokens_optimizado": tokens_es,
            "tokens_ahorrados": 0,
            "porcentaje_reduccion": 0.0,
            "costo_original": costo_orig,
            "costo_optimizado": costo_orig,
            "_clave": clave,
            "_idioma_orig": idioma,
        })
    t1 = time.time()
    total = len(mensajes)

    # ── Fase 2: Agrupamiento ──
    mensajes.sort(key=lambda m: m["_clave"])
    grupos = {k: list(g) for k, g in itertools.groupby(mensajes, key=lambda m: m["_clave"])}
    t2 = time.time()

    # ── Fase 3+4: Traduccion + optimizacion por grupo ──
    errores = 0
    if optimizar and grupos:
        grupos_lista = list(grupos.items())
        max_workers = min(len(grupos_lista), MAX_TRANSLATION_WORKERS)
        completados = [0]
        total_grupos = len(grupos_lista)

        def _procesar_grupo(item):
            clave, grupo = item
            textos = [m["original"] for m in grupo]
            idioma_orig = grupo[0]["_idioma_orig"]
            traducciones = _traducir_lote(textos, idioma_orig)

            errs = 0
            for j, m in enumerate(grupo):
                trad = traducciones[j] if j < len(traducciones) and traducciones[j] else ""
                if not trad:
                    errs += 1
                    continue

                idioma_opt = "en" if idioma_orig == "es" else "es"
                tokens_trad = contar_tokens_texto(trad)
                m["traduccion"] = trad
                m["tokens_traduccion"] = tokens_trad

                texto_opt = optimizar_texto(trad, idioma_opt)
                if not texto_opt or not texto_opt.strip():
                    texto_opt = trad

                tokens_opt = contar_tokens_texto(texto_opt)
                metrica = _calcular_ahorro(m["tokens_original"], tokens_opt)

                m["texto_optimizado"] = texto_opt
                m["idioma"] = idioma_opt
                m["tokens_optimizado"] = tokens_opt
                m["tokens_ahorrados"] = metrica["ahorro"]
                m["porcentaje_reduccion"] = metrica["pct_reduccion"]
                m["costo_optimizado"] = calcular_costo(tokens_opt)

            return clave, len(grupo), errs

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
            futuros = {ex.submit(_procesar_grupo, g): g for g in grupos_lista}
            for futuro in concurrent.futures.as_completed(futuros):
                clave, tam, errs = futuro.result()
                completados[0] += 1
                errores += errs
                print(f"  [Citas] Grupo {completados[0]}/{total_grupos} '{clave}': "
                      f"{tam} mensajes" + (f" ({errs} errores)" if errs else ""))

        print(f"  [Citas] Agrupacion: {total_grupos} grupos desde {total} mensajes "
              f"({total} traducciones -> {total_grupos} lotes)")
    else:
        print(f"  [Citas] {total} mensajes procesados (sin optimizar)")

    t3 = time.time()

    # ── Limpiar internos ──
    for m in mensajes:
        m.pop("_clave", None)
        m.pop("_idioma_orig", None)
        m.pop("_trad", None)

    # ── Perfilado ──
    if optimizar:
        ahorro_total = sum(m["tokens_ahorrados"] for m in mensajes)
        total_orig = sum(m["tokens_original"] for m in mensajes)
        pct = round(ahorro_total / total_orig * 100, 1) if total_orig else 0
        print(f"""
===== PERFIL DE OPTIMIZACION =====
  Schemas + conteo......{t1 - t0:.2f}s  ({total} mensajes)
  Agrupamiento..........{t2 - t1:.2f}s  ({len(grupos)} grupos)
  Traduccion + optim....{t3 - t2:.2f}s  ({len(grupos)} lotes, {max_workers if optimizar and grupos else 0} workers, {errores} errores)
  TOTAL.................{t3 - t_total:.2f}s
  Ahorro global.........{ahorro_total} tokens ({pct}%)
====================================""")
    else:
        print(f"  [Citas] {total} mensajes procesados (sin optimizar)")

    return mensajes


def _calcular_stats_citas(resultados: list) -> dict:
    """Resumen global de la optimizacion."""
    n = len(resultados)
    total_orig = sum(r["tokens_original"] for r in resultados) if n else 0
    total_opt = sum(r["tokens_optimizado"] for r in resultados) if n else 0
    total_ahorro = sum(r["tokens_ahorrados"] for r in resultados) if n else 0
    pct_global = round(total_ahorro / total_orig * 100, 1) if total_orig > 0 else 0.0

    costo_diario_orig = calcular_costo(total_orig * _CITAS_POR_DIA / n) if n else 0
    costo_diario_opt = calcular_costo(total_opt * _CITAS_POR_DIA / n) if n else 0
    costo_mensual_orig = round(costo_diario_orig * _DIAS_POR_MES, 2)
    costo_mensual_opt = round(costo_diario_opt * _DIAS_POR_MES, 2)

    return {
        "total_registros": n,
        "tokens_originales": total_orig,
        "tokens_optimizados": total_opt,
        "tokens_ahorrados": total_ahorro,
        "porcentaje_reduccion": pct_global,
        "costo_mensual_original": costo_mensual_orig,
        "costo_mensual_optimizado": costo_mensual_opt,
        "ahorro_mensual": round(costo_mensual_orig - costo_mensual_opt, 2),
    }


@app.post("/api/citas/analyze")
async def analyze_citas(
    archivos: list[UploadFile] = File(...),
    optimizar_tokens: bool = Form(True),
):
    """Procesa archivos Excel con citas médicas.

    Columnas esperadas: paciente_id, mensaje_texto.
    Si optimizar_tokens=True, traduce cada mensaje y compara tokens ES vs EN.
    """
    _limpiar_cache_traducciones()
    t0 = _time.time()
    todas_citas = []
    columnas_globales = set()

    for archivo in archivos:
        if not archivo.filename:
            continue
        ext = archivo.filename.rsplit(".", 1)[-1].lower() if "." in archivo.filename else ""
        if ext not in ("xlsx",):
            continue
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix="." + ext)
        tmp.write(await archivo.read())
        tmp.close()
        try:
            citas, headers = leer_excel_citas_medicas(tmp.name)
            todas_citas.extend(citas)
            columnas_globales.update(headers)
        finally:
            try:
                _os.unlink(tmp.name)
            except OSError:
                pass

    if not todas_citas:
        raise HTTPException(400, "No se encontraron citas médicas en los archivos.")

    t1 = _time.time()
    todos_resultados = []
    total_chunks = (len(todas_citas) + CHUNK_SIZE - 1) // CHUNK_SIZE
    for ci in range(0, len(todas_citas), CHUNK_SIZE):
        chunk = todas_citas[ci:ci + CHUNK_SIZE]
        chunk_resultados = _procesar_citas_batch(chunk, optimizar_tokens)
        todos_resultados.extend(chunk_resultados)
        if total_chunks > 1:
            print(f"  [Citas] Chunk {ci // CHUNK_SIZE + 1}/{total_chunks}: "
                  f"{len(chunk)} mensajes")

    resultados = todos_resultados
    t2 = _time.time()
    stats = _calcular_stats_citas(resultados)
    t3 = _time.time()

    n = len(todas_citas)
    mt = _obtener_metricas_cache()
    print(f"[Citas] {n} mensajes | lectura={t1 - t0:.2f}s | procesamiento={t2 - t1:.2f}s | stats={t3 - t2:.3f}s | total={t3 - t0:.2f}s")
    print(f"  Textos: {mt.get('textos_originales', 0)} total, {mt.get('textos_unicos', 0)} unicos, "
          f"{mt.get('peticiones_google', 0)} peticiones Google")

    return {
        "resultados": resultados,
        "stats": stats,
        "columnas_disponibles": sorted(columnas_globales),
        "optimizar_tokens": optimizar_tokens,
    }


@app.post("/api/citas/analyze/folder")
async def analyze_citas_folder(
    carpeta: str = Form(...),
    optimizar_tokens: bool = Form(True),
):
    """Procesa una carpeta con Excels de citas médicas.

    Recorre automaticamente todos los *.xlsx de la carpeta.
    """
    _limpiar_cache_traducciones()
    if not carpeta.strip():
        raise HTTPException(400, "Debe especificar una ruta de carpeta.")

    t0 = _time.time()
    try:
        todas_citas, columnas_globales = leer_carpeta_excel_citas(carpeta.strip())
    except FileNotFoundError as e:
        raise HTTPException(400, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))

    if not todas_citas:
        raise HTTPException(400, "No se encontraron citas médicas en la carpeta.")

    t1 = _time.time()
    todos_resultados = []
    for ci in range(0, len(todas_citas), CHUNK_SIZE):
        chunk = todas_citas[ci:ci + CHUNK_SIZE]
        todos_resultados.extend(_procesar_citas_batch(chunk, optimizar_tokens))
    resultados = todos_resultados
    t2 = _time.time()
    stats = _calcular_stats_citas(resultados)
    t3 = _time.time()

    n = len(todas_citas)
    print(f"[Citas Folder] {n} mensajes | lectura={t1 - t0:.2f}s | procesamiento={t2 - t1:.2f}s | stats={t3 - t2:.3f}s | total={t3 - t0:.2f}s")

    return {
        "resultados": resultados,
        "stats": stats,
        "columnas_disponibles": columnas_globales,
        "optimizar_tokens": optimizar_tokens,
    }


@app.post("/api/citas/export/{formato}")
async def export_citas(formato: str, body: ExportRequest):
    """Exporta resultados de optimizacion en JSON, CSV o XLSX.

    Incluye: texto original, texto optimizado, idioma, tokens antes/despues,
    ahorro y porcentaje de reduccion.
    """
    resultados = body.resultados
    if not resultados:
        raise HTTPException(400, "Sin datos")

    if formato == "json":
        out = io.BytesIO(_json.dumps(resultados, indent=2, ensure_ascii=False).encode("utf-8"))
        return StreamingResponse(out, media_type="application/json",
                                 headers={"Content-Disposition": "attachment; filename=citas.json"})

    elif formato == "csv":
        out = io.StringIO()
        w = _csv.writer(out)
        w.writerow(["Paciente ID", "Original", "Traduccion", "Optimizado", "Idioma",
                     "Tokens Orig", "Tokens Trad", "Tokens Opt", "Ahorro", "% Reduccion",
                     "Costo Orig", "Costo Opt"])
        for r in resultados:
            w.writerow([r.get("paciente_id", ""), r.get("original", ""),
                         r.get("traduccion", ""), r.get("texto_optimizado", ""),
                         r.get("idioma", ""),
                         r.get("tokens_original", 0), r.get("tokens_traduccion", 0),
                         r.get("tokens_optimizado", 0), r.get("tokens_ahorrados", 0),
                         r.get("porcentaje_reduccion", 0),
                         r.get("costo_original", 0), r.get("costo_optimizado", 0)])
        out.seek(0)
        bio = io.BytesIO(out.getvalue().encode("utf-8-sig"))
        return StreamingResponse(bio, media_type="text/csv",
                                 headers={"Content-Disposition": "attachment; filename=citas.csv"})

    elif formato == "xlsx":
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Optimizacion"
        ws.append(["Paciente ID", "Original", "Traduccion", "Optimizado", "Idioma",
                    "Tokens Orig", "Tokens Trad", "Tokens Opt", "Ahorro", "% Reduccion",
                    "Costo Orig", "Costo Opt"])
        for r in resultados:
            ws.append([r.get("paciente_id", ""), r.get("original", ""),
                        r.get("traduccion", ""), r.get("texto_optimizado", ""),
                        r.get("idioma", ""),
                        r.get("tokens_original", 0), r.get("tokens_traduccion", 0),
                        r.get("tokens_optimizado", 0), r.get("tokens_ahorrados", 0),
                        r.get("porcentaje_reduccion", 0),
                        r.get("costo_original", 0), r.get("costo_optimizado", 0)])
        out = io.BytesIO()
        wb.save(out)
        out.seek(0)
        return StreamingResponse(out,
                                 media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                 headers={"Content-Disposition": "attachment; filename=citas.xlsx"})

    raise HTTPException(400, "Formato no soportado")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
