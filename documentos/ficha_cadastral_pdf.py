from io import BytesIO
from pathlib import Path

from reportlab.pdfgen import canvas

from pypdf import PdfReader, PdfWriter
from utils.caminhos import caminho_recurso


MODELO_FICHA_CADASTRAL = caminho_recurso(
    "documentos",
    "modelos",
    "ficha_cadastral.pdf",
)

FONTE_PADRAO = "Helvetica"
TAMANHO_FONTE_PADRAO = 10
TAMANHO_FONTE_OBSERVACOES = 9


# Coordenadas centralizadas para ajuste fino do overlay da Ficha Cadastral.
# O ponto (0, 0) fica no canto inferior esquerdo da pagina do PDF.
COORDENADAS_FICHA_CADASTRAL = {
    0: {
        "batismo_aguas": (155, 716),
        "congregacao": (385, 716),
        "cargo": (95, 695),
        "ministerio": (290, 695),
        "dirigente": (385, 612),
        "nome_membro": (70, 573),
        "data_nascimento": (95, 530),
        "estado_civil": (310, 530),
        "profissao": (455, 530),
        "rg": (75, 510),
        "cpf": (365, 510),
        "telefone": (80, 406),
        "celular": (220, 406),
        "email": (70, 387),
        "endereco": (60, 346),
        "numero": (370, 346),
        "bairro": (75, 324),
        "cidade": (250, 324),
        "estado": (405, 324),
        "status": (495, 324),
    }
}

COORDENADAS_OBSERVACOES_FICHA_CADASTRAL = {
    0: {
        "x": 35,
        "y": 418,
        "altura_linha": 24,
        "max_linhas": 5,
        "max_caracteres": 85,
    }
}


def valor_campo(dados, campo):
    return str(dados.get(campo) or "").strip()


def escrever_texto(pdf, texto, x, y, tamanho=TAMANHO_FONTE_PADRAO):
    if not texto:
        return

    pdf.setFont(FONTE_PADRAO, tamanho)
    pdf.drawString(x, y, texto)


def escrever_observacoes(pdf, observacoes, configuracao):
    texto = str(observacoes or "").strip()
    if not texto:
        return

    x = configuracao["x"]
    y = configuracao["y"]
    altura_linha = configuracao["altura_linha"]
    max_linhas = configuracao["max_linhas"]
    max_caracteres = configuracao["max_caracteres"]

    pdf.setFont(FONTE_PADRAO, TAMANHO_FONTE_OBSERVACOES)

    linhas = []
    for linha in texto.splitlines():
        while len(linha) > max_caracteres:
            linhas.append(linha[:max_caracteres])
            linha = linha[max_caracteres:]
        linhas.append(linha)

    for indice, linha in enumerate(linhas[:max_linhas]):
        pdf.drawString(x, y - (indice * altura_linha), linha)


def criar_overlay(reader, dados):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)

    for indice_pagina, pagina_modelo in enumerate(reader.pages):
        largura = float(pagina_modelo.mediabox.width)
        altura = float(pagina_modelo.mediabox.height)

        pdf.setPageSize((largura, altura))

        for campo, (x, y) in COORDENADAS_FICHA_CADASTRAL.get(indice_pagina, {}).items():
            escrever_texto(pdf, valor_campo(dados, campo), x, y)

        configuracao_observacoes = COORDENADAS_OBSERVACOES_FICHA_CADASTRAL.get(indice_pagina)
        if configuracao_observacoes:
            escrever_observacoes(pdf, dados.get("observacoes"), configuracao_observacoes)

        pdf.showPage()

    pdf.save()
    buffer.seek(0)
    return PdfReader(buffer)


def gerar_ficha_cadastral_pdf(dados, caminho_saida):
    if not MODELO_FICHA_CADASTRAL.exists():
        raise FileNotFoundError(f"Modelo nao encontrado: {MODELO_FICHA_CADASTRAL}")

    reader_modelo = PdfReader(str(MODELO_FICHA_CADASTRAL))
    reader_overlay = criar_overlay(reader_modelo, dados)
    writer = PdfWriter()

    for indice, pagina_modelo in enumerate(reader_modelo.pages):
        if indice < len(reader_overlay.pages):
            pagina_modelo.merge_page(reader_overlay.pages[indice])

        writer.add_page(pagina_modelo)

    caminho_saida = Path(caminho_saida)
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)

    with caminho_saida.open("wb") as arquivo_saida:
        writer.write(arquivo_saida)

    return str(caminho_saida)
