import random
import pandas as pd
from faker import Faker


def generar_resenas_excel(
    nombre_archivo="resenas_productos_50k.xlsx", num_filas=10000
):
    print(f"Generando {num_filas} registros fake en español...")

    # Inicializar Faker en español
    fake = Faker("es_ES")

    # Lista de productos de ejemplo para hacer los datos más consistentes
    productos_cat = [
        "Audífonos Bluetooth Wireless",
        "Smartphone Pro Max 256GB",
        "Laptop Gamer 15.6''",
        "Reloj Inteligente Sport",
        "Cámara Digital 4K",
        "Teclado Mecánico RGB",
        "Monitor LED 27'' Curved",
        "Silla Ergonómica Oficina",
        "Cafetera Automática Express",
        "Aspiradora Robot Robotik",
        "Mochila Antirrobo Impermeable",
        "Parlante Portátil Waterproof",
    ]

    # Lista de plantillas de reseñas
    plantillas_resenas = [
    # Positivas / Excelentes
        "Excelente producto. Tenía mis dudas al principio, pero superó completamente mis expectativas en cuanto a rendimiento y acabados. Definitivamente vale cada centavo y lo volvería a comprar.",
        
        "El envío fue impecable: llegó exactamente el día acordado y la caja venía perfectamente protegida. Tras probarlo durante un par de días, puedo decir que funciona al 100%. Muy recomendado.",
        
        "Llevo usándolo todos los días desde que llegó y la experiencia ha sido genial. Es práctico, fácil de usar y cumple de sobra con lo que promete la descripción.",

        # Neutras / Calidad-Precio
        "La relación calidad-precio es bastante justa. Los materiales se sienten aceptables para el costo del producto, aunque no esperes acabados de gama alta. Cumple su función básica.",
        
        "En general es un buen producto: tiene un gran diseño y se nota de buen material. Mi única pega es que el precio está un poco elevado para lo que ofrece, pero no deja de ser una compra razonable.",
        
        "El producto cumple exactamente con lo prometido en la publicación, sin sorpresas. No destaca demasiado en nada en particular, pero resuelve la necesidad adecuadamente.",

        # Negativas / Problemas
        "Lamentablemente la calidad deja mucho que desear. Por el precio esperaba un producto mejor construido, pero los materiales se sienten frágiles y no creo que dure mucho tiempo.",
        
        "Pésima experiencia con la entrega. El paquete llegó tarde y la caja venía aplastada, lo que provocó que el producto sufriera daños. Ya me puse en contacto para gestionar la devolución."
    ]

    data = []

    # Generación eficiente de datos
    for _ in range(num_filas):
        id_cliente = fake.uuid4()[:8].upper()
        cliente = fake.name()
        ciudad = fake.city()
        producto = random.choice(productos_cat)

        # Probabilidad del 25% de que la reseña esté vacía ( None / np.nan )
        # y 75% de que contenga un texto generado o predefinido
        if random.random() < 0.25:
            resena = ""
        else:
            # Combina una plantilla aleatoria con texto simulado de Faker
            resena = (
                f"{random.choice(plantillas_resenas)} {fake.sentence(nb_words=6)}"
            )

        data.append(
            {
                "id_cliente": id_cliente,
                "cliente": cliente,
                "ciudad": ciudad,
                "producto": producto,
                "reseña": resena,
            }
        )

    print("Creando DataFrame de Pandas...")
    df = pd.DataFrame(data)

    print(f"Guardando archivo Excel: {nombre_archivo}...")
    # Exportar a Excel (requiere openpyxl)
    df.to_excel(nombre_archivo, index=False, engine="openpyxl")

    print(f"¡Proceso completado con éxito! Archivo creado: {nombre_archivo}")


if __name__ == "__main__":
    generar_resenas_excel()
