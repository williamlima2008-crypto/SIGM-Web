"""Dados da igreja para os documentos (mesmos nomes de campo do SIGM Desktop)."""

from __future__ import annotations

# (titulo, ((campo, rotulo), ...))
GRUPOS = (
    ("Igreja", (
        ("nome_igreja", "Nome da igreja"), ("ministerio", "Ministério"),
        ("convencao", "Convenção"), ("setor", "Setor"),
        ("congregacao_sede", "Congregação sede"), ("cidade", "Cidade"), ("estado", "UF"),
        ("pastor_presidente", "Pastor presidente"), ("pastor_setorial", "Pastor setorial"),
    )),
    ("Contato da igreja", (
        ("telefone", "Telefone"), ("whatsapp", "WhatsApp"), ("email", "E-mail"), ("site", "Site"),
        ("rua", "Rua"), ("numero", "Número"), ("complemento", "Complemento"),
        ("bairro", "Bairro"), ("cep", "CEP"),
        ("cidade_endereco", "Cidade (endereço)"), ("estado_endereco", "UF (endereço)"),
    )),
    ("Congregação local", (
        ("congregacao_local_nome", "Nome da congregação"),
        ("congregacao_local_dirigente", "Dirigente"),
        ("congregacao_local_numero", "Número da congregação"),
        ("congregacao_local_campo_setor", "Campo/Setor"),
        ("congregacao_local_cidade", "Cidade"), ("congregacao_local_estado", "UF"),
        ("congregacao_local_rua", "Rua"), ("congregacao_local_numero_endereco", "Número"),
        ("congregacao_local_bairro", "Bairro"), ("congregacao_local_cep", "CEP"),
        ("congregacao_local_telefone", "Telefone"), ("congregacao_local_whatsapp", "WhatsApp"),
        ("congregacao_local_email", "E-mail"),
    )),
)

CAMPOS = tuple(campo for _t, campos in GRUPOS for campo, _r in campos)
ROTULOS = {campo: rotulo for _t, campos in GRUPOS for campo, rotulo in campos}


def padrao_da_igreja(igreja):
    """Valores iniciais a partir do cadastro da igreja no Render."""
    base = {campo: "" for campo in CAMPOS}
    base.update({
        "nome_igreja": igreja.nome_igreja or "",
        "ministerio": igreja.ministerio or "",
        "cidade": igreja.cidade or "",
        "estado": igreja.estado or "",
        "congregacao_local_nome": igreja.congregacao or "",
    })
    return base


def limpar(form):
    """Texto simples, sem quebras, no maximo 160 caracteres."""
    dados = {}
    for campo in CAMPOS:
        valor = " ".join(str(form.get(campo, "") or "").split())[:160]
        if campo in ("estado", "estado_endereco", "congregacao_local_estado"):
            valor = valor.upper()[:2]
        dados[campo] = valor
    return dados
