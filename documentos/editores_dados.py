"""Dados dos pedidos de Membramento e Reconciliacao, sem nenhuma tela.

Copia fiel das constantes e da montagem de dados de telas/documentos/
editor_membramento.py e editor_reconciliacao.py. Existe para o SIGM Web (que
nao inclui tkinter/customtkinter no instalador) nao depender dos editores do
desktop. Os arquivos do desktop continuam como estao.
"""

from datetime import date

from documentos.integrador_documentos import montar_dados_documento

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

MAPEAMENTO_PEDIDO_MEMBRAMENTO = {
    "codigo": "pedido_membramento",
    "titulo": "Pedido para Apresentacao / Membramento",
    "modelo": "pedido_membramento.pdf",
    "campos": [
        {"nome": "congregacao", "pagina": 0, "x": 80, "y": 640, "tamanho": 10},
        {"nome": "numero", "pagina": 0, "x": 354, "y": 640, "tamanho": 10},
        {"nome": "dirigente", "pagina": 0, "x": 80, "y": 622, "tamanho": 10},
        {"nome": "nome_membro", "pagina": 0, "x": 80, "y": 601, "tamanho": 10},
        {"nome": "igreja_origem", "pagina": 0, "x": 112, "y": 581, "tamanho": 10},
        {"nome": "cidade_origem", "pagina": 0, "x": 66, "y": 562, "tamanho": 10},
        {"nome": "estado_origem", "pagina": 0, "x": 372, "y": 562, "tamanho": 10},
        {
            "nome": "trouxe_carta_sim",
            "tipo": "checkbox",
            "pagina": 0,
            "x": 185,
            "y": 543,
            "largura": 11,
            "altura": 11,
        },
        {
            "nome": "trouxe_carta_nao",
            "tipo": "checkbox",
            "pagina": 0,
            "x": 250,
            "y": 543,
            "largura": 11,
            "altura": 11,
        },
        {
            "nome": "trouxe_familia_sim",
            "tipo": "checkbox",
            "pagina": 0,
            "x": 144,
            "y": 520,
            "largura": 11,
            "altura": 11,
        },
        {
            "nome": "trouxe_familia_nao",
            "tipo": "checkbox",
            "pagina": 0,
            "x": 208,
            "y": 520,
            "largura": 11,
            "altura": 11,
        },
        {
            "nome": "observacoes",
            "pagina": 0,
            "x": 20,
            "y": 421,
            "tamanho": 9,
            "multilinha": True,
            "altura_linha": 24,
            "max_linhas": 5,
            "max_caracteres": 86,
        },
        {"nome": "dirigente_local", "pagina": 0, "x": 35, "y": 289, "tamanho": 8},
        {"nome": "pastor_setorial", "pagina": 0, "x": 230, "y": 289, "tamanho": 8},
        {
            "nome": "data_documento_extenso",
            "pagina": 0,
            "x": 78,
            "y": 212,
            "tamanho": 11,
            "limpar": True,
            "limpar_x": 76,
            "limpar_y": 207,
            "limpar_largura": 340,
            "limpar_altura": 19,
        },
    ],
}

MAPEAMENTO_PEDIDO_RECONCILIACAO = {
    "codigo": "pedido_reconciliacao",
    "titulo": "Pedido para Reconciliacao",
    "modelo": "pedido_reconciliacao.pdf",
    "campos": [
        {"nome": "congregacao", "pagina": 0, "x": 80, "y": 640, "tamanho": 10},
        {"nome": "numero", "pagina": 0, "x": 354, "y": 640, "tamanho": 10},
        {"nome": "dirigente", "pagina": 0, "x": 80, "y": 622, "tamanho": 10},
        {"nome": "nome_membro", "pagina": 0, "x": 80, "y": 601, "tamanho": 10},
        {
            "nome": "observacoes",
            "pagina": 0,
            "x": 18,
            "y": 549,
            "tamanho": 9,
            "multilinha": True,
            "altura_linha": 24,
            "max_linhas": 7,
            "max_caracteres": 86,
        },
        {"nome": "dirigente_local", "pagina": 0, "x": 17, "y": 366, "tamanho": 8},
        {"nome": "pastor_setorial", "pagina": 0, "x": 218, "y": 366, "tamanho": 8},
        {"nome": "data_documento_extenso", "pagina": 0, "x": 72, "y": 289, "tamanho": 11},
    ],
}

CAMPOS_AUTOMATICOS = [
    ("nome_membro", "Nome do membro"),
    ("congregacao", "Congregacao"),
    ("numero_congregacao", "Numero da Congregacao"),
    ("campo_setor", "Campo / Setor"),
    ("dirigente_local", "Dirigente Local"),
    ("cidade_documento", "Cidade"),
    ("estado_documento", "Estado"),
    ("data_documento_visual", "Data do documento"),
    ("pastor_presidente", "Pastor Presidente"),
    ("pastor_setorial", "Pastor Setorial"),
]


def dados_membramento(id_membro):
    dados = montar_dados_documento(id_membro)
    hoje = date.today()

    dados["numero"] = dados.get("numero_congregacao", "")
    dados["dirigente"] = dados.get("dirigente_local") or dados.get("dirigente", "")
    dados["cidade_documento"] = (
        dados.get("local_cidade")
        or dados.get("cidade_congregacao")
        or dados.get("cidade_igreja")
        or dados.get("cidade")
        or "Guarulhos"
    )
    dados["estado_documento"] = (
        dados.get("estado_congregacao")
        or dados.get("estado_igreja")
        or dados.get("estado")
        or ""
    )
    dados["local_cidade"] = dados["cidade_documento"]
    dados["local_estado"] = dados["estado_documento"]
    dados["data_documento_visual"] = hoje.strftime("%d/%m/%Y")

    dados.setdefault("igreja_origem", "")
    dados.setdefault("cidade_origem", "")
    dados.setdefault("estado_origem", "")
    dados.setdefault("trouxe_carta", "")
    dados.setdefault("trouxe_familia", "")
    dados.setdefault("observacoes", "")

    return dados


def dados_reconciliacao(id_membro):
    dados = montar_dados_documento(id_membro)
    hoje = date.today()

    dados["numero"] = dados.get("numero_congregacao", "")
    dados["dirigente"] = dados.get("dirigente_local") or dados.get("dirigente", "")
    dados["cidade_documento"] = (
        dados.get("local_cidade")
        or dados.get("cidade_congregacao")
        or dados.get("cidade_igreja")
        or dados.get("cidade")
        or "Guarulhos"
    )
    dados["estado_documento"] = (
        dados.get("estado_congregacao")
        or dados.get("estado_igreja")
        or dados.get("estado")
        or ""
    )
    dados["local_cidade"] = dados["cidade_documento"]
    dados["local_estado"] = dados["estado_documento"]
    dados["data_documento_visual"] = hoje.strftime("%d/%m/%Y")
    dados.setdefault("observacoes", "")

    return dados


class EditorMembramento:
    """Mesma interface usada pelo SIGM Web: montar_dados_iniciais(None, id)."""

    @staticmethod
    def montar_dados_iniciais(_self, id_membro):
        return dados_membramento(id_membro)


class EditorReconciliacao:
    @staticmethod
    def montar_dados_iniciais(_self, id_membro):
        return dados_reconciliacao(id_membro)
