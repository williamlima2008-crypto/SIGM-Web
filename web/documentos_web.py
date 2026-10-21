"""
SIGM Web - documentos oficiais (ficha cadastral, membramento, reconciliacao
e carta de recomendacao).

Nao reimplementa o desenho dos PDFs: usa os mesmos geradores, modelos e
mapeamentos da versao desktop (documentos/gerar_documentos.py,
documentos/renderizador_pdf.py e documentos/editores_dados.py). A diferenca
e que aqui o PDF nao e aberto numa janela do computador: ele e registrado no
historico e enviado ao navegador.
"""

import re
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

from documentos import editores_dados
from utils.caminhos import caminho_dados

TIPO_FICHA = "ficha-cadastral"
TIPO_MEMBRAMENTO = "membramento"
TIPO_RECONCILIACAO = "reconciliacao"
TIPO_CARTA = "carta-recomendacao"

CATALOGO = (
    {
        "slug": TIPO_FICHA, "titulo": "Ficha Cadastral",
        "descricao": "Gera a ficha final com os dados e a foto do cadastro.",
        "formulario": False,
    },
    {
        "slug": TIPO_MEMBRAMENTO, "titulo": "Pedido para Apresentação / Membramento",
        "descricao": "Preencha igreja de origem, carta, família e observações.",
        "formulario": True,
    },
    {
        "slug": TIPO_RECONCILIACAO, "titulo": "Pedido para Reconciliação",
        "descricao": "Confira a data e escreva as observações.",
        "formulario": True,
    },
    {
        "slug": TIPO_CARTA, "titulo": "Carta de Recomendação",
        "descricao": "Confira os dados e informe onde o membro será apresentado.",
        "formulario": True,
    },
)
TITULOS = {item["slug"]: item["titulo"] for item in CATALOGO}

CAMPOS_CARTA = (
    ("nome_membro", "Nome do membro"),
    ("cargo", "Cargo"),
    ("sexo", "Sexo"),
    ("setor_campo", "Setor n."),
    ("congregacao", "Congregação"),
)


# O desktop grava alguns titulos e rotulos sem acento. Na web mostramos com
# acento, sem mexer no que ja esta gravado no banco.
ACENTOS = (
    ("Numero da Congregacao", "Número da Congregação"),
    ("Congregacao", "Congregação"),
    ("Apresentacao", "Apresentação"),
    ("Reconciliacao", "Reconciliação"),
    ("Observacoes", "Observações"),
    ("Funcao", "Função"),
    ("Recomendacao", "Recomendação"),
    ("Assembleia", "Assembleia"),
    ("Numero", "Número"),
)


def acentuar(texto):
    texto = str(texto or "")
    for sem, com in ACENTOS:
        texto = texto.replace(sem, com)
    return texto


class DocumentoErro(Exception):
    """Erro com mensagem pronta para mostrar ao usuario."""


# --------------------------------------------------------------- utilidades
def pasta_saida():
    pasta = caminho_dados("documentos_gerados", criar_pai=False)
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def limpar_nome_arquivo(valor):
    texto = str(valor or "").strip()
    texto = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", texto)
    texto = re.sub(r"\s+", "_", texto)
    texto = texto.strip("._")
    return texto or "documento"


def _editor(slug):
    """Constantes e dados iniciais dos pedidos (sem depender das telas do desktop)."""
    if slug not in (TIPO_MEMBRAMENTO, TIPO_RECONCILIACAO):
        raise KeyError(slug)
    return editores_dados


def _classe_editor(slug):
    modulo = _editor(slug)
    return modulo, getattr(
        modulo, "EditorMembramento" if slug == TIPO_MEMBRAMENTO else "EditorReconciliacao"
    )


def _dados_iniciais(slug, id_membro):
    _, classe = _classe_editor(slug)
    # montar_dados_iniciais nao usa nada da janela: so busca o membro e a igreja.
    return classe.montar_dados_iniciais(None, id_membro)


def _data_do_formulario(valores):
    """Data do documento: hoje ou a informada (DD/MM/AAAA)."""
    if valores.get("usar_data_atual", True):
        return date.today()
    texto = str(valores.get("data_documento") or "").strip()
    try:
        return datetime.strptime(texto, "%d/%m/%Y").date()
    except ValueError:
        raise DocumentoErro("Data do documento inválida. Use DD/MM/AAAA.")


def _texto_opcao(valor):
    return {"sim": "Sim", "nao": "Nao"}.get(valor, "")


# --------------------------------------------------------------- formulario
def descrever_formulario(slug, id_membro):
    """Campos que a tela mostra antes de gerar o documento."""
    if slug not in TITULOS:
        raise DocumentoErro("Documento desconhecido.")

    if slug == TIPO_CARTA:
        from documentos.integrador_documentos import montar_dados_documento

        dados = montar_dados_documento(id_membro)
        return {
            "titulo": TITULOS[slug], "automaticos": [], "data": None,
            "campos": [
                {"nome": chave, "rotulo": rotulo, "tipo": "texto",
                 "valor": str(dados.get(chave) or "")}
                for chave, rotulo in CAMPOS_CARTA
            ] + [{
                "nome": "apresentar_em", "rotulo": "Apresentamos à Assembleia de Deus em:",
                "tipo": "area", "valor": "",
                "ajuda": "Sexo e o destino da apresentação não vêm do cadastro: "
                         "preencha se quiser que apareçam no PDF.",
            }],
        }

    if slug == TIPO_FICHA:
        return {"titulo": TITULOS[slug], "automaticos": [], "data": None, "campos": []}

    modulo, _ = _classe_editor(slug)
    dados = _dados_iniciais(slug, id_membro)
    campos = []
    if slug == TIPO_MEMBRAMENTO:
        campos += [
            {"nome": "igreja_origem", "rotulo": "Igreja de origem", "tipo": "texto",
             "valor": dados.get("igreja_origem", "")},
            {"nome": "cidade_origem", "rotulo": "Cidade de origem", "tipo": "texto",
             "valor": dados.get("cidade_origem", "")},
            {"nome": "estado_origem", "rotulo": "Estado de origem", "tipo": "texto",
             "valor": dados.get("estado_origem", "")},
            {"nome": "trouxe_carta", "rotulo": "Trouxe carta?", "tipo": "simnao",
             "valor": ""},
            {"nome": "trouxe_familia", "rotulo": "Veio com família?", "tipo": "simnao",
             "valor": ""},
        ]
    campos.append({"nome": "observacoes", "rotulo": "Observações", "tipo": "area",
                   "valor": dados.get("observacoes", "")})
    return {
        "titulo": TITULOS[slug],
        "automaticos": [
            {"rotulo": acentuar(rotulo), "valor": str(dados.get(chave) or "")}
            for chave, rotulo in modulo.CAMPOS_AUTOMATICOS
            if chave != "data_documento_visual"
        ],
        "data": {"usar_atual": True, "valor": date.today().strftime("%d/%m/%Y")},
        "campos": campos,
    }


# ------------------------------------------------------------------ geracao
def _nome_saida(codigo, nome_membro):
    agora = datetime.now().strftime("%Y%m%d_%H%M%S")
    return pasta_saida() / f"{codigo}_{limpar_nome_arquivo(nome_membro)}_{agora}.pdf"


def _gerar_ficha(id_membro):
    from documentos import gerar_documentos as gd

    caminho_editavel = gd.preencher_copia_pdf_editavel_com_membro(
        gd.TIPO_FICHA_CADASTRAL, id_membro
    )
    caminho_final = gd.gerar_pdf_final(caminho_editavel)
    try:
        gd.inserir_foto_ficha_cadastral(caminho_final, id_membro)
    except Exception:
        # Igual ao desktop: se a foto falhar, a ficha segue sem ela.
        pass
    return str(caminho_final), gd.TIPO_FICHA_CADASTRAL, gd.TIPO_FICHA_CADASTRAL, "PDF final gerado"


def _gerar_pedido(slug, id_membro, valores):
    from documentos.catalogo_documentos import (
        DOCUMENTO_PEDIDO_MEMBRAMENTO,
        DOCUMENTO_PEDIDO_RECONCILIACAO,
        obter_documento_oficial,
    )
    from documentos.renderizador_pdf import gerar_pdf_final

    modulo, _ = _classe_editor(slug)
    dados = _dados_iniciais(slug, id_membro)
    if not str(dados.get("nome_membro") or "").strip():
        raise DocumentoErro("Informe o nome do membro.")

    data_documento = _data_do_formulario(valores)
    if slug == TIPO_MEMBRAMENTO:
        codigo = DOCUMENTO_PEDIDO_MEMBRAMENTO
        mapeamento = modulo.MAPEAMENTO_PEDIDO_MEMBRAMENTO
        titulo = "Pedido para Apresentacao / Membramento"
        for campo in ("igreja_origem", "cidade_origem", "estado_origem"):
            dados[campo] = str(valores.get(campo) or "").strip()
        carta = valores.get("trouxe_carta") if valores.get("trouxe_carta") in ("sim", "nao") else ""
        familia = valores.get("trouxe_familia") if valores.get("trouxe_familia") in ("sim", "nao") else ""
        dados["trouxe_carta"] = _texto_opcao(carta)
        dados["trouxe_carta_sim"] = carta == "sim"
        dados["trouxe_carta_nao"] = carta == "nao"
        dados["trouxe_familia"] = _texto_opcao(familia)
        dados["trouxe_familia_sim"] = familia == "sim"
        dados["trouxe_familia_nao"] = familia == "nao"
    else:
        codigo = DOCUMENTO_PEDIDO_RECONCILIACAO
        mapeamento = modulo.MAPEAMENTO_PEDIDO_RECONCILIACAO
        titulo = "Pedido para Reconciliacao"

    dados["observacoes"] = str(valores.get("observacoes") or "").strip()

    cidade = dados.get("local_cidade") or dados.get("cidade_documento") or "Guarulhos"
    dados["numero"] = dados.get("numero_congregacao", "")
    dados["dirigente"] = dados.get("dirigente_local") or dados.get("dirigente", "")
    dados["local_dia"] = data_documento.strftime("%d")
    dados["local_mes"] = modulo.MESES[data_documento.month - 1]
    dados["local_ano"] = data_documento.strftime("%Y")
    dados["data_documento"] = data_documento.strftime("%d/%m/%Y")
    dados["data_documento_extenso"] = (
        f"{cidade}, {dados['local_dia']} de {dados['local_mes']} de {dados['local_ano']}"
    )

    documento = replace(obter_documento_oficial(codigo), titulo=titulo, mapeamento=mapeamento)
    saida = _nome_saida(codigo, dados.get("nome_membro"))
    gerar_pdf_final(documento.modelo_pdf, saida, dados, documento.mapeamento)
    return str(saida), documento.codigo, documento.titulo, "PDF salvo"


def _gerar_carta(id_membro, valores):
    from documentos import gerar_documentos as gd
    from documentos.integrador_documentos import montar_dados_documento

    dados = montar_dados_documento(id_membro)
    for chave, _rotulo in CAMPOS_CARTA:
        texto = str(valores.get(chave) or "").strip()
        if texto:
            dados[chave] = texto
    apresentar_em = str(valores.get("apresentar_em") or "").strip()
    caminho = gd.gerar_pdf_documento(gd.TIPO_CARTA_RECOMENDACAO, dados, apresentar_em=apresentar_em)
    return str(caminho), gd.TIPO_CARTA_RECOMENDACAO, gd.TIPO_CARTA_RECOMENDACAO, "PDF gerado"


def gerar_documento(slug, id_membro, valores=None):
    """Gera o PDF. Devolve (caminho, tipo, titulo, observacao)."""
    valores = valores or {}
    if slug == TIPO_FICHA:
        return _gerar_ficha(id_membro)
    if slug in (TIPO_MEMBRAMENTO, TIPO_RECONCILIACAO):
        return _gerar_pedido(slug, id_membro, valores)
    if slug == TIPO_CARTA:
        return _gerar_carta(id_membro, valores)
    raise DocumentoErro("Documento desconhecido.")


def caminho_pdf_seguro(caminho):
    """Arquivo PDF existente (ou None). Os caminhos vem do historico do SIGM."""
    texto = str(caminho or "").strip()
    if not texto or "\x00" in texto:
        return None
    arquivo = Path(texto)
    if arquivo.suffix.lower() != ".pdf" or not arquivo.is_file():
        return None
    return arquivo
