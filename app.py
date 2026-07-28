from flask import Flask, request, render_template
from token_counter import (contar_tokens, traducir, detectar_idioma,
                           analizar_prompt, generar_ejemplo_mejora,
                           recomendar_modelo)

app = Flask(__name__)


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


if __name__ == "__main__":
    app.run(debug=True)
