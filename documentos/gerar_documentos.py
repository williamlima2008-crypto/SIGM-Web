import os
import re
from datetime import date, datetime
from pathlib import Path

import fitz
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from documentos import renderizador_pdf
from documentos.integrador_documentos import (
    buscar_caminho_foto_membro,
    montar_dados_documento,
)
from documentos.mapeamentos.ficha_cadastral import MAPEAMENTO_FICHA_CADASTRAL
from utils.caminhos import caminho_dados, caminho_recurso


PASTA_SAIDA_EDITAVEIS = caminho_dados("documentos_gerados", criar_pai=False)
PASTA_MODELOS_EDITAVEIS = caminho_recurso("documentos", "modelos_editaveis")

TIPO_FICHA_CADASTRAL = "Ficha Cadastral"
TIPO_PEDIDO_MEMBRAMENTO = "Pedido para Apresentação / Membramento"
TIPO_PEDIDO_RECONCILIACAO = "Pedido para Reconciliação"
TIPO_CARTA_RECOMENDACAO = "Carta de Recomendação"

TIPOS_DOCUMENTOS_OFICIAIS_EDITAVEIS = (
    TIPO_FICHA_CADASTRAL,
    TIPO_PEDIDO_MEMBRAMENTO,
    TIPO_PEDIDO_RECONCILIACAO,
)

MODELOS_EDITAVEIS = {
    TIPO_FICHA_CADASTRAL: PASTA_MODELOS_EDITAVEIS / "ficha_cadastral_editavel.pdf",
    TIPO_PEDIDO_MEMBRAMENTO: PASTA_MODELOS_EDITAVEIS / "pedido_membramento_editavel.pdf",
    TIPO_PEDIDO_RECONCILIACAO: PASTA_MODELOS_EDITAVEIS / "pedido_reconciliacao_editavel.pdf",
}

MESES = [
    "janeiro",
    "fevereiro",
    "marco",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
]


def criar_pasta():
    PASTA_SAIDA_EDITAVEIS.mkdir(parents=True, exist_ok=True)


def criar_pasta_editaveis():
    PASTA_SAIDA_EDITAVEIS.mkdir(parents=True, exist_ok=True)


def montar_dados_igreja(igreja):
    try:
        from banco.database import buscar_configuracoes_igreja

        configuracoes = buscar_configuracoes_igreja()
    except Exception:
        configuracoes = {}

    if any(configuracoes.get(campo) for campo in ("nome_igreja", "ministerio", "cidade", "estado")):
        return {
            "nome": configuracoes.get("nome_igreja") or "Igreja",
            "ministerio": configuracoes.get("ministerio") or "",
            "setor": configuracoes.get("setor") or "",
            "cidade": configuracoes.get("cidade") or "",
            "estado": configuracoes.get("estado") or "",
            "endereco": configuracoes.get("rua") or "",
            "telefone": configuracoes.get("telefone") or "",
            "email": configuracoes.get("email") or "",
            "site": configuracoes.get("site") or "",
            "logo": configuracoes.get("logotipo") or "",
            "pastor_presidente": configuracoes.get("pastor_presidente") or "",
            "pastor_setorial": configuracoes.get("pastor_setorial") or "",
            "dirigente": configuracoes.get("congregacao_local_dirigente") or "",
            "convencao": configuracoes.get("convencao") or "",
            "congregacao_local_nome": configuracoes.get("congregacao_local_nome") or "",
        }

    if not igreja:
        return {
            "nome": "Igreja",
            "ministerio": "",
            "setor": "",
            "cidade": "",
            "estado": "",
            "endereco": "",
            "telefone": "",
            "email": "",
            "site": "",
            "logo": "",
            "pastor_presidente": "",
            "pastor_setorial": "",
            "dirigente": "",
            "convencao": "",
            "congregacao_local_nome": "",
        }

    return {
        "nome": igreja[1] or "Igreja",
        "ministerio": igreja[2] or "",
        "setor": "",
        "cidade": igreja[3] or "",
        "estado": igreja[4] or "",
        "endereco": igreja[5] or "",
        "telefone": igreja[6] or "",
        "email": igreja[7] or "",
        "site": "",
        "logo": igreja[8] or "",
        "pastor_presidente": "",
        "pastor_setorial": "",
        "dirigente": "",
        "convencao": "",
        "congregacao_local_nome": "",
    }


def valor_membro(membro, indice):
    if membro is None or len(membro) <= indice:
        return ""

    return membro[indice] or ""


def separar_data(valor):
    if not valor:
        return "", "", ""

    texto = str(valor).strip()

    for formato in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            data = datetime.strptime(texto, formato)
            return data.strftime("%d"), data.strftime("%m"), data.strftime("%Y")
        except ValueError:
            pass

    partes = re.findall(r"\d+", texto)
    if len(partes) >= 3:
        if len(partes[0]) == 4:
            return partes[2].zfill(2), partes[1].zfill(2), partes[0]

        return partes[0].zfill(2), partes[1].zfill(2), partes[2]

    return "", "", ""


def limpar_nome_arquivo(valor):
    texto = str(valor or "").strip()
    texto = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", texto)
    texto = re.sub(r"\s+", "_", texto)
    texto = texto.strip("._")
    return texto or "documento"


def nome_arquivo_unico(tipo, nome_membro, sufixo=""):
    tipo_limpo = limpar_nome_arquivo(tipo)
    membro_limpo = limpar_nome_arquivo(nome_membro)
    data_hora = datetime.now().strftime("%Y%m%d_%H%M%S")
    sufixo_limpo = limpar_nome_arquivo(sufixo) if sufixo else ""
    partes = [tipo_limpo, membro_limpo, data_hora]
    if sufixo_limpo:
        partes.append(sufixo_limpo)
    return "_".join(partes) + ".pdf"


def montar_dados_membro_para_documento(membro, igreja=None):
    dados_igreja = montar_dados_igreja(igreja)
    hoje = date.today()
    nascimento_dia, nascimento_mes, nascimento_ano = separar_data(
        valor_membro(membro, 5)
    )
    batismo_dia, batismo_mes, batismo_ano = separar_data(
        valor_membro(membro, 16)
    )
    batismo_espirito = valor_membro(membro, 29)
    batismo_espirito_dia, batismo_espirito_mes, batismo_espirito_ano = separar_data(
        batismo_espirito
    )
    conjuge_dia, conjuge_mes, conjuge_ano = separar_data(
        valor_membro(membro, 26)
    )

    cidade = valor_membro(membro, 14)
    estado = valor_membro(membro, 15)
    cidade_nascimento = valor_membro(membro, 23)
    estado_nascimento = valor_membro(membro, 24)
    if cidade_nascimento and estado_nascimento:
        cidade_estado_nascimento = f"{cidade_nascimento} - {estado_nascimento}"
    else:
        cidade_estado_nascimento = cidade_nascimento or estado_nascimento
    local_igreja = (
        dados_igreja.get("congregacao_local_nome")
        or dados_igreja.get("nome", "")
    )
    local_convencao = " - ".join(
        parte
        for parte in (local_igreja, dados_igreja.get("convencao", ""))
        if parte
    )

    return {
        "setor_campo": dados_igreja.get("setor") or dados_igreja["ministerio"],
        "congregacao": dados_igreja["nome"],
        "dirigente": dados_igreja.get("dirigente", ""),
        "nome_membro": valor_membro(membro, 1),
        "rg": valor_membro(membro, 2),
        "orgao_emissor": valor_membro(membro, 3),
        "cpf": valor_membro(membro, 4),
        "data_nascimento_dia": nascimento_dia,
        "data_nascimento_mes": nascimento_mes,
        "data_nascimento_ano": nascimento_ano,
        "estado_civil": valor_membro(membro, 6),
        "profissao": valor_membro(membro, 7),
        "pai": valor_membro(membro, 21),
        "mae": valor_membro(membro, 22),
        "nome_pai": valor_membro(membro, 21),
        "nome_mae": valor_membro(membro, 22),
        "cidade_nascimento": cidade_nascimento,
        "estado_nascimento": estado_nascimento,
        "cidade_estado_nascimento": cidade_estado_nascimento,
        "conjuge": valor_membro(membro, 25),
        "nome_conjuge": valor_membro(membro, 25),
        "data_nascimento_conjuge": valor_membro(membro, 26),
        "data_nascimento_conjuge_dia": conjuge_dia,
        "data_nascimento_conjuge_mes": conjuge_mes,
        "data_nascimento_conjuge_ano": conjuge_ano,
        "residencial": valor_membro(membro, 8),
        "telefone": valor_membro(membro, 8),
        "celular": valor_membro(membro, 9),
        "email": valor_membro(membro, 10),
        "rua": valor_membro(membro, 11),
        "endereco": valor_membro(membro, 11),
        "numero": valor_membro(membro, 12),
        "bairro": valor_membro(membro, 13),
        "cidade": cidade,
        "uf": estado,
        "estado": estado,
        "cep": valor_membro(membro, 30),
        "batismo_aguas_dia": batismo_dia,
        "batismo_aguas_mes": batismo_mes,
        "batismo_aguas_ano": batismo_ano,
        "igreja_local_batismo_aguas": local_igreja,
        "batismo_espirito_santo": batismo_espirito,
        "data_batismo_espirito_santo": batismo_espirito,
        "batismo_espirito_santo_dia": batismo_espirito_dia,
        "batismo_espirito_santo_mes": batismo_espirito_mes,
        "batismo_espirito_santo_ano": batismo_espirito_ano,
        "igreja_local_batismo_espirito_santo": local_igreja,
        "igreja_local_convencao_evangelista": local_convencao,
        "igreja_local_convencao_pastor": local_convencao,
        "ministerio": valor_membro(membro, 17),
        "cargo": valor_membro(membro, 18),
        "status": valor_membro(membro, 19),
        "observacoes": valor_membro(membro, 20),
        "nome_titular_lgpd": valor_membro(membro, 1),
        "local_cidade": dados_igreja["cidade"] or cidade,
        "local_dia": str(hoje.day).zfill(2),
        "local_mes": MESES[hoje.month - 1],
        "local_ano": str(hoje.year),
    }


def preencher_widget(widget, valor):
    if valor in (None, ""):
        return

    widget.field_value = str(valor)
    widget.update()


def montar_dados_por_tipo(tipo, id_membro):
    dados = montar_dados_documento(id_membro)

    if tipo != TIPO_FICHA_CADASTRAL:
        dados["numero"] = dados.get("numero_congregacao", "")
        if dados.get("local_mes"):
            dados["local_mes"] = f"e {dados['local_mes']}"

    return dados


def preencher_copia_pdf_editavel_com_membro(tipo, id_membro):
    if tipo not in MODELOS_EDITAVEIS:
        raise ValueError(f"Documento oficial editavel desconhecido: {tipo}")

    caminho_modelo = MODELOS_EDITAVEIS[tipo]
    if not caminho_modelo.exists():
        raise FileNotFoundError(f"Modelo editavel nao encontrado: {caminho_modelo}")

    criar_pasta_editaveis()

    dados = montar_dados_por_tipo(tipo, id_membro)
    caminho_saida = PASTA_SAIDA_EDITAVEIS / nome_arquivo_unico(
        tipo,
        dados["nome_membro"],
    )

    documento = fitz.open(str(caminho_modelo))
    try:
        for pagina in documento:
            for widget in pagina.widgets() or []:
                preencher_widget(widget, dados.get(widget.field_name))

        documento.save(str(caminho_saida), deflate=True, garbage=4)
    finally:
        documento.close()

    return str(caminho_saida)


def gerar_pdf_final(caminho_editavel):
    caminho_editavel = Path(caminho_editavel)
    caminho_final = caminho_editavel.with_name(
        f"{caminho_editavel.stem}_FINAL.pdf"
    )

    documento = fitz.open(str(caminho_editavel))
    try:
        for pagina in documento:
            for widget in pagina.widgets() or []:
                widget.fill_color = (1, 1, 1)
                widget.border_color = None
                widget.border_width = 0
                widget.update()

        documento.bake(annots=True, widgets=True)
        documento.save(str(caminho_final), deflate=True, garbage=4)
    finally:
        documento.close()

    return str(caminho_final)


def gerar_e_abrir_documento_oficial_editavel(tipo, id_membro):
    caminho = preencher_copia_pdf_editavel_com_membro(tipo, id_membro)
    os.startfile(caminho)
    return caminho


def inserir_foto_ficha_cadastral(caminho_pdf, id_membro):
    """
    Coloca a foto cadastrada do membro na caixa FOTO da Ficha Cadastral
    FINAL. O PDF editavel so possui campos de texto, entao a foto nunca
    entrava por este caminho (so pelo Editor da Ficha).

    Reaproveita exatamente o mesmo desenho de imagem do Editor
    (renderizador_pdf + mapeamento da Ficha): mesma caixa, mesmo tamanho,
    mesma centralizacao. Retorna True se a foto foi inserida; False se o
    membro nao tem foto utilizavel (o PDF fica exatamente como estava).
    """
    caminho_foto = buscar_caminho_foto_membro(id_membro)
    if not caminho_foto or not Path(caminho_foto).is_file():
        return False

    # Foto corrompida/ilegivel: nao mexe no PDF.
    try:
        renderizador_pdf.carregar_imagem(Path(caminho_foto))
    except Exception:
        return False

    campos_foto = [
        campo
        for campo in MAPEAMENTO_FICHA_CADASTRAL.get("campos", [])
        if campo.get("tipo") == "imagem"
    ]
    if not campos_foto:
        return False

    mapeamento_foto = dict(MAPEAMENTO_FICHA_CADASTRAL)
    mapeamento_foto["campos"] = campos_foto
    dados_foto = {
        "foto": caminho_foto,
        "foto_membro": caminho_foto,
        "caminho_foto": caminho_foto,
        "foto_path": caminho_foto,
    }

    caminho_pdf = Path(caminho_pdf)
    caminho_temporario = caminho_pdf.with_name(f"{caminho_pdf.stem}_foto_tmp.pdf")

    try:
        documento = fitz.open(str(caminho_pdf))
        try:
            overlay_bytes = renderizador_pdf.criar_overlay_pdf(
                documento,
                dados_foto,
                mapeamento_foto,
            )
            documento_overlay = fitz.open("pdf", overlay_bytes)
            try:
                for indice, pagina in enumerate(documento):
                    if indice < len(documento_overlay):
                        pagina.show_pdf_page(pagina.rect, documento_overlay, indice)

                documento.save(str(caminho_temporario), deflate=True, garbage=4)
            finally:
                documento_overlay.close()
        finally:
            documento.close()

        os.replace(str(caminho_temporario), str(caminho_pdf))
    except Exception:
        try:
            if caminho_temporario.exists():
                caminho_temporario.unlink()
        except Exception:
            pass
        raise

    return True


def gerar_e_abrir_documento_oficial_final(tipo, id_membro):
    caminho_editavel = preencher_copia_pdf_editavel_com_membro(tipo, id_membro)
    caminho_final = gerar_pdf_final(caminho_editavel)

    if tipo == TIPO_FICHA_CADASTRAL:
        try:
            inserir_foto_ficha_cadastral(caminho_final, id_membro)
        except Exception:
            # Se a foto falhar por qualquer motivo, o PDF segue exatamente como
            # era antes (sem foto) - nada mais do documento e afetado.
            pass

    os.startfile(caminho_final)
    return caminho_final


def gerar_e_abrir_carta_recomendacao(id_membro, apresentar_em="", dados_override=None):
    """
    Gera a Carta de Recomendacao para o membro informado e abre no
    leitor de PDF padrao do Windows. 'apresentar_em' preenche o campo
    "Apresentamos a Assembleia de Deus em:" e 'dados_override' permite
    substituir qualquer campo auto-preenchido (Nome, Cargo, Setor,
    Congregacao, Sexo) pelo texto digitado no Editor da Carta de
    Recomendacao, antes de gerar.
    """
    dados = montar_dados_documento(id_membro)
    if dados_override:
        dados.update({chave: valor for chave, valor in dados_override.items() if valor})
    caminho = gerar_pdf_documento(TIPO_CARTA_RECOMENDACAO, dados, apresentar_em=apresentar_em)
    os.startfile(caminho)
    return str(caminho)


def desenhar_logo(pdf, dados_igreja, altura):
    if dados_igreja["logo"] and os.path.exists(dados_igreja["logo"]):
        try:
            pdf.drawImage(
                dados_igreja["logo"],
                60,
                altura - 88,
                width=45,
                height=45,
                preserveAspectRatio=True,
                mask="auto"
            )
        except Exception:
            pass


def gerar_pdf_documento(tipo, dados, igreja=None, apresentar_em=""):
    criar_pasta()

    caminho = PASTA_SAIDA_EDITAVEIS / nome_arquivo_unico(tipo, dados.get("nome_membro", ""))

    dados_igreja = montar_dados_igreja(igreja)

    if tipo == "Ficha Cadastral":
        from documentos.ficha_cadastral_pdf import gerar_ficha_cadastral_pdf

        return gerar_ficha_cadastral_pdf(dados, caminho)

    if tipo == TIPO_CARTA_RECOMENDACAO:
        from documentos.carta_recomendacao_pdf import gerar_carta_recomendacao_pdf

        return gerar_carta_recomendacao_pdf(
            dados, caminho, dados_igreja=dados_igreja, apresentar_em=apresentar_em,
        )

    pdf = canvas.Canvas(caminho, pagesize=A4)
    largura, altura = A4

    desenhar_logo(pdf, dados_igreja, altura)

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawCentredString(largura / 2, altura - 50, dados_igreja["nome"])

    pdf.setFont("Helvetica", 11)
    dados_cabecalho = [
        dados_igreja["ministerio"],
        dados_igreja["endereco"],
        dados_igreja["telefone"],
        dados_igreja["email"]
    ]
    texto_cabecalho = " - ".join(dado for dado in dados_cabecalho if dado)
    pdf.drawCentredString(largura / 2, altura - 70, texto_cabecalho)

    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawCentredString(largura / 2, altura - 105, tipo)

    y = altura - 150
    pdf.setFont("Helvetica", 11)

    campos = [
        ("Congregação", dados.get("congregacao", "")),
        ("Nº", dados.get("numero", "")),
        ("Dirigente", dados.get("dirigente", "")),
        ("Irmão(ã)", dados.get("nome_membro", "")),
        ("RG", dados.get("rg", "")),
        ("CPF", dados.get("cpf", "")),
        ("Cidade", dados.get("cidade", "")),
        ("Estado", dados.get("estado", "")),
        ("Cargo", dados.get("cargo", "")),
        ("Ministério", dados.get("ministerio", "")),
    ]

    if "Membramento" in tipo:
        campos.extend([
            ("Igreja de origem", dados.get("igreja_origem", "")),
            ("Cidade origem", dados.get("cidade_origem", "")),
            ("Estado origem", dados.get("estado_origem", "")),
            ("Trouxe carta?", dados.get("trouxe_carta", "")),
            ("Trouxe família?", dados.get("trouxe_familia", "")),
        ])

    for campo, valor in campos:
        pdf.drawString(60, y, f"{campo}: {valor}")
        y -= 24

    y -= 15
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(60, y, "Observações:")
    y -= 22

    pdf.setFont("Helvetica", 10)
    observacoes = dados.get("observacoes", "")

    for linha in observacoes.split("\n"):
        pdf.drawString(60, y, linha[:90])
        y -= 16

    y -= 50
    pdf.line(70, y, 270, y)
    pdf.line(330, y, 530, y)

    y -= 15
    pdf.setFont("Helvetica", 9)
    pdf.drawCentredString(170, y, "Carimbo e Assinatura do Dirigente")
    pdf.drawCentredString(430, y, "Visto do Pastor Setorial")

    hoje = date.today()
    y -= 45
    pdf.setFont("Helvetica", 11)
    pdf.drawString(60, y, f"Guarulhos, {hoje.day}/{hoje.month}/{hoje.year}")

    pdf.save()
    return caminho
