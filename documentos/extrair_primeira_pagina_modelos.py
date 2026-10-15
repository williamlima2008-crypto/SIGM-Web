from pathlib import Path

from pypdf import PdfReader, PdfWriter


BASE_DIR = Path(__file__).resolve().parent.parent
PASTA_MODELOS = BASE_DIR / "documentos" / "modelos"
PASTA_MODELOS_CORRIGIDOS = BASE_DIR / "documentos" / "modelos_corrigidos"

MODELOS = (
    "pedido_membramento.pdf",
    "pedido_reconciliacao.pdf",
)


def extrair_primeira_pagina(nome_arquivo):
    caminho_entrada = PASTA_MODELOS / nome_arquivo
    caminho_saida = PASTA_MODELOS_CORRIGIDOS / nome_arquivo

    if not caminho_entrada.exists():
        raise FileNotFoundError(f"Modelo original nao encontrado: {caminho_entrada}")

    leitor = PdfReader(str(caminho_entrada))
    total_paginas = len(leitor.pages)

    print(f"{nome_arquivo}: original tinha {total_paginas} pagina(s).")

    if total_paginas == 0:
        raise ValueError(f"PDF sem paginas: {caminho_entrada}")

    escritor = PdfWriter()
    escritor.add_page(leitor.pages[0])

    with caminho_saida.open("wb") as arquivo_saida:
        escritor.write(arquivo_saida)

    print(f"{nome_arquivo}: primeira pagina salva em {caminho_saida}")


def corrigir_modelos():
    PASTA_MODELOS_CORRIGIDOS.mkdir(parents=True, exist_ok=True)

    for nome_arquivo in MODELOS:
        extrair_primeira_pagina(nome_arquivo)


if __name__ == "__main__":
    corrigir_modelos()
