from flask import Flask, request, render_template, jsonify, send_file
from token_counter import (contar_tokens, traducir, detectar_idioma,
                           analizar_prompt, generar_ejemplo_mejora,
                           recomendar_modelo,
                           leer_excel_resenas, leer_csv_resenas,
                           extraer_texto_archivo,
                           clasificar_resenas_qwen,
                           calcular_costo, contar_tokens_texto,
                           _RESENAS_POR_DIA, _DIAS_POR_MES)
import io, json as _json

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB max


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        texto = request.form.get("texto", "").strip()

        if not texto:
            return render_template("index.html", error="Por favor, escribe un texto.")

        idioma = detectar_idioma(texto)

        if idioma == "es":
            tokens_orig = contar_tokens(texto)
            traduccion = traducir(texto, "es", "en")
            tokens_trad = contar_tokens(traduccion)
        else:
            traduccion = traducir(texto, "en", "es")
            tokens_orig = contar_tokens(texto)
            tokens_trad = contar_tokens(traduccion)

        prompt = analizar_prompt(texto)
        optimo = prompt["puntaje"] >= 80
        mejora = None if optimo else generar_ejemplo_mejora(texto)
        modelo = recomendar_modelo(texto, prompt)

        return render_template(
            "index.html",
            texto_original=texto,
            idioma_original=idioma,
            tokens_orig=tokens_orig,
            tokens_trad=tokens_trad,
            traduccion=traduccion,
            prompt=prompt,
            optimo=optimo,
            mejora=mejora,
            modelo=modelo,
        )

    return render_template("index.html")


@app.route("/excel-reviews", methods=["GET", "POST"])
def excel_reviews():
    if request.method == "POST":
        archivos = request.files.getlist("archivos")
        columna = request.form.get("columna", "").strip()
        optimizar = request.form.get("optimizar", "off") == "on"

        if not archivos or not any(a.filename for a in archivos):
            return render_template("excel_reviews.html",
                                   error="Selecciona al menos un archivo Excel.")

        import os as _os, tempfile

        todas_resenas = []
        columnas_globales = set()

        for archivo in archivos:
            if not archivo.filename:
                continue
            ext = archivo.filename.rsplit(".", 1)[-1].lower() if "." in archivo.filename else ""
            if ext not in ("xlsx", "csv", "pdf", "txt"):
                continue
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix="." + ext)
            archivo.save(tmp.name)
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
                        # Split long text into individual reviews by newlines
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
            return render_template("excel_reviews.html",
                                   error="No se encontraron reseñas en los archivos.",
                                   columnas_disponibles=sorted(columnas_globales),
                                   columna_seleccionada=columna)

        # Procesar cada reseña
        resultados = []
        total_es = total_en = 0

        for texto in todas_resenas:
            texto_utilizado = texto
            tokens_es = contar_tokens_texto(texto)
            tokens_en = tokens_es
            traduccion = ""

            if optimizar:
                try:
                    traduccion = traducir(texto, "es", "en")
                    texto_utilizado = traduccion
                    tokens_en = contar_tokens_texto(traduccion)
                except Exception:
                    tokens_en = tokens_es

            total_es += tokens_es
            total_en += tokens_en

            resultados.append({
                "original": texto,
                "traduccion": traduccion,
                "texto_utilizado": texto_utilizado,
                "tokens_es": tokens_es,
                "tokens_en": tokens_en,
            })

        # Clasificación con Qwen (batch)
        clasificaciones = clasificar_resenas_qwen(todas_resenas)
        for i, r in enumerate(resultados):
            if i < len(clasificaciones):
                r["clasificacion"] = clasificaciones[i]
            r["costo"] = calcular_costo(r["tokens_en"] if optimizar else r["tokens_es"])

        n = len(resultados)

        # Proyección económica
        costo_mensual_es = calcular_costo(total_es * _RESENAS_POR_DIA * _DIAS_POR_MES / n) if n else 0
        costo_mensual_en = calcular_costo(total_en * _RESENAS_POR_DIA * _DIAS_POR_MES / n) if n else 0
        ahorro = round(costo_mensual_es - costo_mensual_en, 2)
        pct_ahorro = round(ahorro / costo_mensual_es * 100, 1) if costo_mensual_es > 0 else 0

        return render_template(
            "excel_reviews.html",
            resultados=resultados,
            optimizar=optimizar,
            total_resenas=n,
            total_tokens_es=total_es,
            total_tokens_en=total_en,
            promedio_es=round(total_es / n) if n else 0,
            promedio_en=round(total_en / n) if n else 0,
            costo_mensual_es=costo_mensual_es,
            costo_mensual_en=costo_mensual_en,
            ahorro=ahorro,
            pct_ahorro=pct_ahorro,
            columnas_disponibles=sorted(columnas_globales),
            columna_seleccionada=columna,
        )

    return render_template("excel_reviews.html")


@app.route("/excel-reviews/exportar/<formato>", methods=["POST"])
def exportar_excel_reviews(formato):
    data = request.get_json(force=True) if request.is_json else {}
    resultados = data.get("resultados", [])
    if not resultados:
        return jsonify({"error": "Sin datos"}), 400

    if formato == "json":
        output = io.BytesIO()
        output.write(_json.dumps(resultados, indent=2, ensure_ascii=False).encode("utf-8"))
        output.seek(0)
        return send_file(output, mimetype="application/json",
                         as_attachment=True, download_name="reseñas_analizadas.json")

    elif formato == "csv":
        import csv as _csv
        out = io.StringIO()
        w = _csv.writer(out)
        w.writerow(["Original", "Traducción", "Tokens ES", "Tokens EN",
                     "Costo", "Error Type", "Component", "Severity", "Category"])
        for r in resultados:
            c = r.get("clasificacion", {})
            w.writerow([r.get("original", ""), r.get("traduccion", ""),
                         r.get("tokens_es", 0), r.get("tokens_en", 0),
                         r.get("costo", 0),
                         c.get("error_type", ""), c.get("component", ""),
                         c.get("severity", ""), c.get("category", "")])
        out.seek(0)
        bio = io.BytesIO(out.getvalue().encode("utf-8-sig"))
        return send_file(bio, mimetype="text/csv",
                         as_attachment=True, download_name="reseñas_analizadas.csv")

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
                        r.get("costo", 0),
                        c.get("error_type", ""), c.get("component", ""),
                        c.get("severity", ""), c.get("category", "")])
        out = io.BytesIO()
        wb.save(out)
        out.seek(0)
        return send_file(out,
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                         as_attachment=True, download_name="reseñas_analizadas.xlsx")

    return jsonify({"error": "Formato no soportado"}), 400


if __name__ == "__main__":
    app.run(debug=True)
