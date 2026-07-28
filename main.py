from token_counter import contar_tokens


def main():
    texto = input("Ingrese un texto:\n")

    cantidad = contar_tokens(texto)

    print(f"\nCantidad de tokens: {cantidad}")


if __name__ == "__main__":
    main()