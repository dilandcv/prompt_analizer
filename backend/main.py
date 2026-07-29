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
    _RESENAS_POR_DIA, _DIAS_POR_MES,
)

app = FastAPI(title="Token Analyzer API", version="2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── Prompt Analysis ──

@app.post("/api/analyze")
async def analyze_prompt(texto: str = Form("")):
    texto = texto.strip()
    if not texto:
        raise HTTPException(400, "Texto vacío")

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

    try:
        prompt = analizar_prompt(texto)
    except Exception:
        prompt = {"puntaje": 0, "nivel": "error", "detalles": [],
                  "fortalezas": [], "debilidades": [], "recomendaciones": [],
                  "puntaje_ia": 0, "puntaje_heuristico": 0, "evaluacion_ia": False}
    optimo = prompt["puntaje"] >= 80
    try:
        mejora = None if optimo else generar_ejemplo_mejora(texto)
    except Exception:
        mejora = None
    modelo = recomendar_modelo(texto, prompt)

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


# ── Excel / File Reviews ──

def _procesar_resenas(todas_resenas: list, optimizar: bool) -> list:
    resultados = []
    for texto in todas_resenas:
        tokens_es = contar_tokens_texto(texto)
        tokens_en = tokens_es
        traduccion = ""
        if optimizar:
            try:
                traduccion = traducir(texto, "es", "en")
                tokens_en = contar_tokens_texto(traduccion)
            except Exception:
                tokens_en = tokens_es
        resultados.append({
            "original": texto, "traduccion": traduccion,
            "tokens_es": tokens_es, "tokens_en": tokens_en,
        })
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
):
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

    resultados = _procesar_resenas(todas_resenas, optimizar)
    total_es = sum(r["tokens_es"] for r in resultados)
    total_en = sum(r["tokens_en"] for r in resultados)

    textos_para_clasificar = [r["traduccion"] if (optimizar and r["traduccion"]) else r["original"] for r in resultados]
    clasificaciones = clasificar_resenas_qwen(textos_para_clasificar)
    for i, r in enumerate(resultados):
        if i < len(clasificaciones):
            r["clasificacion"] = clasificaciones[i]
        r["costo"] = calcular_costo(r["tokens_en"] if optimizar else r["tokens_es"])

    stats = _calcular_stats(resultados, total_es, total_en)

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
):
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

    resultados = _procesar_resenas(todas_resenas, optimizar)
    total_es = sum(r["tokens_es"] for r in resultados)
    total_en = sum(r["tokens_en"] for r in resultados)

    textos_para_clasificar = [r["traduccion"] if (optimizar and r["traduccion"]) else r["original"] for r in resultados]
    clasificaciones = clasificar_resenas_qwen(textos_para_clasificar)
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


@app.get("/api/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
