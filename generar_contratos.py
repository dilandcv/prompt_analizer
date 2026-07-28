import os
import random
from datetime import datetime, timedelta
from faker import Faker
from weasyprint import HTML

# Inicializar Faker con localización en español
fake = Faker('es_ES')

# Templates de cláusulas legales extensas
RESONS_LEGALES = [
    "Que ambas partes se reconocen mutuamente con capacidad legal suficiente para otorgar el presente contrato de arrendamiento urbano, formalizando las siguientes cláusulas.",
    "Que reuniéndose los comparecientes en la representación con la que actúan, y reconociéndose capacidad legal bastante para contratar y obligarse, libre y espontáneamente manifiestan.",
    "Que por medio del presente documento de carácter legal, privado y vinculante, acuerdan celebrar el contrato de arrendamiento sujeto a las siguientes estipulaciones legales."
]

PENALIZACIONES = [
    "En caso de mora o demora injustificada en el pago de la renta dentro de los primeros cinco (5) días hábiles del mes, el ARRENDATARIO incurrirá en un recargo de demora del 5% acumulativo por cada semana de retraso sobre la mensualidad pactada.",
    "Si el ARRENDATARIO decide resolver unilateralmente el contrato antes del plazo estipulado, deberá indemnizar al ARRENDADOR con una cantidad equivalente a una mensualidad de la renta en vigor por cada año del contrato que reste por cumplir.",
    "El incumplimiento de la prohibición de subarriendo o cesión de la vivienda dará derecho al ARRENDADOR a rescindir de inmediato el contrato e incautar la totalidad de la fianza depositada.",
    "En el caso de no restituir el inmueble en el estado original salvo el desgaste natural, el ARRENDATARIO asumirá las reparaciones descontando el costo total de la fianza e imputando saldos pendientes si correspondiese."
]

CLAUSULAS_ADICIONALES = [
    "El inmueble se destinará exclusivamente a vivienda habitual del ARRENDATARIO y su familia, quedando expresamente prohibido el ejercicio de actividades comerciales o profesionales en el mismo.",
    "Los gastos por servicios de suministro de agua, electricidad, gas y telecomunicaciones serán de cuenta exclusiva y cargo del ARRENDATARIO desde la fecha de firma del presente instrumento.",
    "El ARRENDATARIO no podrá realizar obras ni modificaciones en la estructura o acabados del inmueble sin la autorización previa y por escrito del ARRENDADOR.",
    "Queda expresamente prohibida la tenencia de animales domésticos o mascotas de cualquier especie en el inmueble objeto de este contrato sin autorización previa."
]

CSS_STYLE = """
@page { size: A4; margin: 20mm 15mm; background-color: #fcfcfd; }
body { font-family: 'Times New Roman', Times, serif; font-size: 11pt; line-height: 1.6; color: #1a1a1a; margin: 0; padding: 0; }
.header { text-align: center; border-bottom: 2px solid #2c3e50; padding-bottom: 12px; margin-bottom: 20px; }
.title { font-size: 16pt; font-weight: bold; text-transform: uppercase; color: #1a252f; margin: 0; }
.subtitle { font-size: 10pt; color: #555555; margin-top: 5px; font-style: italic; }
.section-heading { font-size: 12pt; font-weight: bold; color: #2c3e50; margin-top: 18px; margin-bottom: 8px; border-bottom: 1px solid #dcdcdc; padding-bottom: 3px; }
p { text-align: justify; margin-bottom: 10px; text-indent: 15px; }
p.no-indent { text-indent: 0; }
.highlight-box { background-color: #f4f6f7; border-left: 4px solid #2c3e50; padding: 10px 12px; margin: 15px 0; font-size: 10.5pt; }
.signatures { margin-top: 40px; width: 100%; page-break-inside: avoid; }
.signature-table { width: 100%; border-collapse: collapse; }
.signature-cell { width: 50%; text-align: center; vertical-align: top; padding: 20px; }
.signature-line { border-top: 1px solid #000; margin-top: 50px; padding-top: 5px; font-weight: bold; }
"""

def generar_contrato_pdf(num_contratos=5, carpeta_salida="contratos_pdf"):
    os.makedirs(carpeta_salida, exist_ok=True)
    print(f"Generando {num_contratos} contratos en PDF...")

    for i in range(1, num_contratos + 1):
        contract_id = f"CTR-{random.randint(1000, 9999)}-{i:03d}"
        arrendador = fake.name()
        dni_arrendador = fake.dni()
        arrendatario = fake.name()
        dni_arrendatario = fake.dni()
        direccion = fake.address().replace("\n", ", ")
        
        monto_alquiler = random.choice([450, 600, 750, 850, 1000, 1200, 1500, 1800, 2200])
        fianza = monto_alquiler * random.choice([1, 2])
        
        fecha_inicio = fake.date_between(start_date='-1y', end_date='today')
        duracion_meses = random.choice([12, 24, 36, 60])
        fecha_fin = fecha_inicio + timedelta(days=duracion_meses * 30)

        intro_legal = random.choice(RESONS_LEGALES)
        penalizacion_1 = random.choice(PENALIZACIONES)
        penalizacion_2 = random.choice([p for p in PENALIZACIONES if p != penalizacion_1])
        clausulas_extra = random.sample(CLAUSULAS_ADICIONALES, k=random.randint(2, 4))
        clausulas_extra_html = "".join([f"<p><strong>CLÁUSULA ADICIONAL:</strong> {c}</p>" for c in clausulas_extra])

        html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Contrato - {contract_id}</title>
    <style>{CSS_STYLE}</style>
</head>
<body>
    <div class="header">
        <h1 class="title">CONTRATO DE ARRENDAMIENTO URBANO</h1>
        <div class="subtitle">Documento de Vinculación Jurídica Privada - ref: {contract_id}</div>
    </div>
    <p class="no-indent">En la ciudad de Madrid, a {fecha_inicio.strftime('%d de %B de %Y')}.</p>
    <div class="section-heading">REUNIDOS DE UNA PARTE</div>
    <p>De una parte, como <strong>ARRENDADOR</strong>, D./Dña. <strong>{arrendador}</strong>, con DNI <strong>{dni_arrendador}</strong>.</p>
    <p>Y de otra parte, como <strong>ARRENDATARIO</strong>, D./Dña. <strong>{arrendatario}</strong>, con DNI <strong>{dni_arrendatario}</strong>.</p>
    <div class="section-heading">MANIFESTACIONES PREVIAS</div>
    <p>{intro_legal}</p>
    <p>Que el ARRENDADOR es propietario del inmueble situado en: <strong>{direccion}</strong>.</p>
    <div class="section-heading">ESTIPULACIONES Y CLÁUSULAS REGULADORAS</div>
    <p><strong>PRIMERA. Objeto y Duración:</strong> Duración de <strong>{duracion_meses} meses</strong>, desde el <strong>{fecha_inicio.strftime('%d/%m/%Y')}</strong> al <strong>{fecha_fin.strftime('%d/%m/%Y')}</strong>.</p>
    <p><strong>SEGUNDA. Renta y Pago:</strong> Renta mensual de <strong>{monto_alquiler} EUR (€)</strong>.</p>
    <p><strong>TERCERA. Fianza Constitutiva:</strong> Fianza legal de <strong>{fianza} EUR (€)</strong>.</p>
    <div class="highlight-box">
        <strong>CUARTA. Cláusulas de Penalización por Incumplimiento:</strong><br>
        1. {penalizacion_1}<br><br>
        2. {penalizacion_2}
    </div>
    {clausulas_extra_html}
    <div class="signatures">
        <table class="signature-table">
            <tr>
                <td class="signature-cell">
                    <div class="signature-line">EL ARRENDADOR</div>
                    <div>{arrendador}</div>
                    <div>DNI: {dni_arrendador}</div>
                </td>
                <td class="signature-cell">
                    <div class="signature-line">EL ARRENDATARIO</div>
                    <div>{arrendatario}</div>
                    <div>DNI: {dni_arrendatario}</div>
                </td>
            </tr>
        </table>
    </div>
</body>
</html>
"""
        filename = f"{carpeta_salida}/contrato_{i:03d}_{contract_id}.pdf"
        HTML(string=html_content).write_pdf(filename)
        print(f" Generado: {filename}")

if __name__ == "__main__":
    import sys
    num = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    generar_contrato_pdf(num)
