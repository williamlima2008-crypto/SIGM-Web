from io import BytesIO
from pathlib import Path

import fitz
try:
    from PIL import Image, ImageOps
except ImportError:
    Image = None
    ImageOps = None
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from documentos.datas import separar_data_documento
from utils.caminhos import base_dados, caminho_recurso


FONTE_PADRAO = "Helvetica"
TAMANHO_FONTE_PADRAO = 10


AJUSTES_POSICIONAMENTO = {
    "pedido_membramento": {
        "congregacao": {"dy": 5},
        "numero": {"dy": 5},
        "dirigente": {"dy": 5},
        "nome_membro": {"dy": 1},
        "igreja_origem": {"dx": 14, "dy": 5},
        "cidade_origem": {"dx": 14, "dy": 5},
        "estado_origem": {"dx": 14, "dy": 5},
        "dirigente_local": {
            "x": 20,
            "largura": 186,
            "alinhamento": "centro",
            "tamanho": 8,
        },
        "pastor_setorial": {
            "x": 218,
            "largura": 173,
            "alinhamento": "centro",
            "tamanho": 8,
        },
        "carimbo_assinatura_dirigente": {
            "x": 20,
            "largura": 186,
            "alinhamento": "centro",
        },
        "visto_pastor_setorial": {
            "x": 218,
            "largura": 173,
            "alinhamento": "centro",
        },
        "local_cidade": {"alinhamento": "centro"},
        "local_dia": {"alinhamento": "centro"},
        "local_mes": {"alinhamento": "centro"},
        "local_ano": {"alinhamento": "centro"},
    },
    "pedido_reconciliacao": {
        "congregacao": {"dy": 5},
        "numero": {"dy": 5},
        "dirigente": {"dy": 5},
        "nome_membro": {"dy": 1},
        "dirigente_local": {
            "x": 17,
            "largura": 190,
            "alinhamento": "centro",
            "tamanho": 8,
        },
        "pastor_setorial": {
            "x": 218,
            "largura": 170,
            "alinhamento": "centro",
            "tamanho": 8,
        },
        "carimbo_assinatura_dirigente": {
            "x": 17,
            "largura": 190,
            "alinhamento": "centro",
        },
        "visto_pastor_setorial": {
            "x": 218,
            "largura": 170,
            "alinhamento": "centro",
        },
        "local_cidade": {"alinhamento": "centro"},
        "local_dia": {"alinhamento": "centro"},
        "local_mes": {"alinhamento": "centro"},
        "local_ano": {"alinhamento": "centro"},
    },
}


LAYOUTS_DATA = {
    "pedido_membramento": {
        "cidade": {"x": 78, "y": 212, "limpar": (78, 207, 62, 15)},
        "dia": {"x": 164, "y": 212, "largura": 34},
        "mes": {"x": 215, "y": 212, "largura": 132},
        "ano": {"x": 379, "y": 212},
        "ano_limpar": (377, 207, 35, 15),
    },
    "pedido_reconciliacao": {
        "cidade": {"x": 72, "y": 289, "limpar": (72, 284, 62, 15)},
        "dia": {"x": 152, "y": 289, "largura": 42},
        "mes": {"x": 206, "y": 289, "largura": 136},
        "ano": {"x": 372.5, "y": 289},
        "ano_limpar": (372, 284, 34, 15),
    },
}


CAMPOS_ASSINATURA_MANUAL = {
    "pedido_membramento": {
        "dirigente_local",
        "pastor_setorial",
        "carimbo_assinatura_dirigente",
        "visto_pastor_setorial",
    },
    "pedido_reconciliacao": {
        "dirigente_local",
        "pastor_setorial",
        "carimbo_assinatura_dirigente",
        "visto_pastor_setorial",
    },
}

SUFIXOS_DATA = {
    "dia": 0,
    "mes": 1,
    "ano": 2,
}
CAMPOS_DATA_BASE_DERIVADA = {
    "batismo_aguas",
    "batismo_espirito_santo",
    "data_nascimento",
    "data_nascimento_conjuge",
}


def valor_texto(dados, nome_campo):
    valor = dados.get(nome_campo, "")
    if valor is None:
        return ""

    return str(valor).strip()


def campo_assinatura_manual(campo, codigo):
    return campo.get("nome") in CAMPOS_ASSINATURA_MANUAL.get(codigo, set())


def base_e_sufixo_data(nome_campo):
    for sufixo in SUFIXOS_DATA:
        final = f"_{sufixo}"
        if nome_campo.endswith(final):
            return nome_campo[: -len(final)], sufixo

    return "", ""


def valor_campo_data(dados, nome_campo):
    valor = valor_texto(dados, nome_campo)
    if valor:
        return valor

    nome_base, sufixo = base_e_sufixo_data(nome_campo)
    if not nome_base:
        return ""
    if nome_base not in CAMPOS_DATA_BASE_DERIVADA:
        return ""

    partes = separar_data_documento(valor_texto(dados, nome_base))
    return partes[SUFIXOS_DATA[sufixo]]


def codigo_documento(mapeamento):
    return (mapeamento or {}).get("codigo", "")


def campo_com_ajustes(campo, codigo):
    campo_ajustado = campo.copy()
    ajustes = AJUSTES_POSICIONAMENTO.get(codigo, {}).get(campo["nome"], {})

    if not ajustes:
        return campo_ajustado

    campo_ajustado.update(
        {
            chave: valor
            for chave, valor in ajustes.items()
            if chave not in {"dx", "dy"}
        }
    )
    campo_ajustado["x"] = campo_ajustado.get("x", 0) + ajustes.get("dx", 0)
    campo_ajustado["y"] = campo_ajustado.get("y", 0) + ajustes.get("dy", 0)
    return campo_ajustado


def valor_marcado(dados, nome_campo):
    valor = dados.get(nome_campo, "")

    if isinstance(valor, bool):
        return valor

    texto = str(valor or "").strip().lower()
    return texto in {"1", "s", "sim", "true", "x", "marcado", "checked"}


def quebrar_linhas(texto, max_caracteres):
    linhas = []

    for linha in str(texto or "").splitlines():
        linha_atual = linha
        while len(linha_atual) > max_caracteres:
            linhas.append(linha_atual[:max_caracteres])
            linha_atual = linha_atual[max_caracteres:]
        linhas.append(linha_atual)

    return linhas


def partes_data_extenso(texto):
    partes = str(texto or "").split(", ", 1)
    cidade = partes[0].strip() if partes else ""
    restante = partes[1] if len(partes) > 1 else ""
    itens = restante.split(" de ")

    if len(itens) >= 3:
        return cidade, itens[0].strip(), itens[1].strip(), itens[2].strip()

    return cidade, "", "", ""


def limpar_retangulo(pdf, retangulo):
    x, y, largura, altura = retangulo

    pdf.saveState()
    pdf.setFillColorRGB(1, 1, 1)
    pdf.setStrokeColorRGB(1, 1, 1)
    pdf.rect(x, y, largura, altura, stroke=0, fill=1)
    pdf.restoreState()


def obter_partes_data(campo, dados):
    texto = valor_texto(dados, campo["nome"])
    cidade, dia, mes, ano = partes_data_extenso(texto)

    if not cidade:
        cidade = valor_texto(dados, "local_cidade") or "Guarulhos"
    if not dia:
        dia = valor_texto(dados, "local_dia")
    if not mes:
        mes = valor_texto(dados, "local_mes")
    if not ano:
        ano = valor_texto(dados, "local_ano")

    return cidade, dia, mes, ano


def escrever_texto_centralizado(pdf, texto, x, y, largura):
    pdf.drawCentredString(x + (largura / 2), y, texto)


def escrever_cidade_data(pdf, cidade, item):
    if not cidade:
        return

    if cidade.strip().lower() != "guarulhos":
        limpar_retangulo(pdf, item["limpar"])
        pdf.drawString(item["x"], item["y"], f"{cidade},")


def escrever_data_linhada(pdf, campo, dados, codigo):
    layout = LAYOUTS_DATA.get(codigo)
    if not layout:
        return

    cidade, dia, mes, ano = obter_partes_data(campo, dados)
    fonte = campo.get("fonte", FONTE_PADRAO)
    tamanho = campo.get("tamanho", TAMANHO_FONTE_PADRAO)

    pdf.setFont(fonte, tamanho)

    escrever_cidade_data(pdf, cidade, layout["cidade"])

    if dia:
        escrever_texto_centralizado(
            pdf,
            dia,
            layout["dia"]["x"],
            layout["dia"]["y"],
            layout["dia"]["largura"],
        )

    if mes:
        escrever_texto_centralizado(
            pdf,
            mes,
            layout["mes"]["x"],
            layout["mes"]["y"],
            layout["mes"]["largura"],
        )

    if "de_ano" in layout:
        pdf.drawString(layout["de_ano"]["x"], layout["de_ano"]["y"], "de")

    if ano:
        limpar_retangulo(pdf, layout["ano_limpar"])
        if "largura" in layout["ano"]:
            escrever_texto_centralizado(
                pdf,
                ano,
                layout["ano"]["x"],
                layout["ano"]["y"],
                layout["ano"]["largura"],
            )
            return

        pdf.drawString(layout["ano"]["x"], layout["ano"]["y"], ano)


def limpar_area(pdf, campo):
    largura = campo.get("limpar_largura") or campo.get("largura")
    altura = campo.get("limpar_altura") or campo.get("altura")

    if not largura or not altura:
        return

    x = campo.get("limpar_x", campo["x"])
    y = campo.get("limpar_y", campo["y"] - 3)

    pdf.saveState()
    pdf.setFillColorRGB(1, 1, 1)
    pdf.setStrokeColorRGB(1, 1, 1)
    pdf.rect(x, y, largura, altura, stroke=0, fill=1)
    pdf.restoreState()


def caminhos_possiveis_imagem(caminho):
    texto_caminho = str(caminho or "").strip().strip('"')
    if not texto_caminho:
        return []

    caminho = Path(texto_caminho)
    if caminho.is_absolute():
        return [caminho]

    candidatos = [
        caminho,
        Path.cwd() / caminho,
        base_dados() / caminho,
        caminho_recurso(caminho),
    ]

    caminhos = []
    for candidato in candidatos:
        if candidato not in caminhos:
            caminhos.append(candidato)

    return caminhos


def resolver_caminho_imagem(caminho):
    for candidato in caminhos_possiveis_imagem(caminho):
        if candidato.exists() and candidato.is_file():
            return candidato

    return None


def carregar_imagem(caminho):
    if Image is not None:
        with Image.open(caminho) as imagem:
            imagem = ImageOps.exif_transpose(imagem)
            if imagem.mode not in {"RGB", "RGBA", "L"}:
                imagem = imagem.convert("RGB")
            else:
                imagem = imagem.copy()

        return ImageReader(imagem), imagem.width, imagem.height

    leitor = ImageReader(str(caminho))
    largura, altura = leitor.getSize()
    return leitor, largura, altura


def valor_caminho_imagem(campo, dados):
    for chave in campo.get("chaves_dados", (campo.get("nome"),)):
        valor = dados.get(chave)
        if valor:
            return valor

    return ""


def escrever_imagem(pdf, campo, dados):
    caminho = resolver_caminho_imagem(valor_caminho_imagem(campo, dados))
    if caminho is None:
        return

    x = campo["x"]
    y = campo["y"]
    largura_quadro = campo["largura"]
    altura_quadro = campo["altura"]

    try:
        imagem, largura_imagem, altura_imagem = carregar_imagem(caminho)
        if largura_imagem <= 0 or altura_imagem <= 0:
            return

        if campo.get("limpar", True):
            limpar_retangulo(pdf, (x, y, largura_quadro, altura_quadro))

        escala = min(
            largura_quadro / largura_imagem,
            altura_quadro / altura_imagem,
        )
        largura_final = largura_imagem * escala
        altura_final = altura_imagem * escala
        x_final = x + ((largura_quadro - largura_final) / 2)
        y_final = y + ((altura_quadro - altura_final) / 2)

        pdf.drawImage(
            imagem,
            x_final,
            y_final,
            width=largura_final,
            height=altura_final,
            mask="auto",
        )
    except Exception:
        return


def escrever_checkbox(pdf, campo, dados):
    if not valor_marcado(dados, campo["nome"]):
        return

    if campo.get("limpar"):
        limpar_area(pdf, campo)

    x = campo["x"]
    y = campo["y"]
    largura = campo.get("largura", 10)
    altura = campo.get("altura", 10)

    pdf.saveState()
    pdf.setStrokeColorRGB(0, 0, 0)
    pdf.setLineWidth(1.2)
    pdf.line(x + 2, y + altura * 0.52, x + largura * 0.42, y + 2)
    pdf.line(x + largura * 0.42, y + 2, x + largura - 2, y + altura - 2)
    pdf.restoreState()


def escrever_campo_texto(pdf, campo, dados):
    texto = valor_campo_data(dados, campo["nome"])
    if not texto:
        return

    if campo.get("limpar"):
        limpar_area(pdf, campo)

    fonte = campo.get("fonte", FONTE_PADRAO)
    tamanho = campo.get("tamanho", TAMANHO_FONTE_PADRAO)
    largura = campo.get("largura")
    if largura and not campo.get("multilinha"):
        while tamanho > 7 and pdf.stringWidth(texto, fonte, tamanho) > largura:
            tamanho -= 0.5

    pdf.setFont(fonte, tamanho)

    if campo.get("multilinha"):
        linhas = quebrar_linhas(texto, campo.get("max_caracteres", 90))
        altura_linha = campo.get("altura_linha", tamanho + 3)
        max_linhas = campo.get("max_linhas", len(linhas))

        for indice, linha in enumerate(linhas[:max_linhas]):
            pdf.drawString(campo["x"], campo["y"] - (indice * altura_linha), linha)
        return

    if campo.get("alinhamento") == "centro" and campo.get("largura"):
        pdf.drawCentredString(campo["x"] + (campo["largura"] / 2), campo["y"], texto)
        return

    pdf.drawString(campo["x"], campo["y"], texto)


def escrever_campo(pdf, campo, dados, codigo):
    if campo_assinatura_manual(campo, codigo):
        return

    if campo.get("nome") == "data_documento_extenso":
        escrever_data_linhada(pdf, campo, dados, codigo)
        return

    if campo.get("tipo") == "imagem":
        escrever_imagem(pdf, campo, dados)
        return

    if campo.get("tipo") == "checkbox":
        escrever_checkbox(pdf, campo, dados)
        return

    escrever_campo_texto(pdf, campo, dados)


def criar_overlay_pdf(documento_modelo, dados, mapeamento):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    campos = mapeamento.get("campos", [])
    codigo = codigo_documento(mapeamento)

    for indice_pagina, pagina_modelo in enumerate(documento_modelo):
        largura = float(pagina_modelo.rect.width)
        altura = float(pagina_modelo.rect.height)
        pdf.setPageSize((largura, altura))

        for campo in campos:
            if campo.get("pagina", 0) == indice_pagina:
                escrever_campo(
                    pdf,
                    campo_com_ajustes(campo, codigo),
                    dados,
                    codigo,
                )

        pdf.showPage()

    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()


def gerar_pdf_final(modelo_pdf, caminho_saida, dados, mapeamento):
    modelo_pdf = Path(modelo_pdf)
    caminho_saida = Path(caminho_saida)

    if not modelo_pdf.exists():
        raise FileNotFoundError(f"Modelo PDF nao encontrado: {modelo_pdf}")

    caminho_saida.parent.mkdir(parents=True, exist_ok=True)

    documento_modelo = fitz.open(str(modelo_pdf))
    try:
        overlay_bytes = criar_overlay_pdf(documento_modelo, dados, mapeamento)
        documento_overlay = fitz.open("pdf", overlay_bytes)

        try:
            for indice, pagina_modelo in enumerate(documento_modelo):
                if indice < len(documento_overlay):
                    pagina_modelo.show_pdf_page(
                        pagina_modelo.rect,
                        documento_overlay,
                        indice,
                    )

            documento_modelo.save(str(caminho_saida), deflate=True, garbage=4)
        finally:
            documento_overlay.close()
    finally:
        documento_modelo.close()

    return str(caminho_saida)
