from dataclasses import dataclass
from pathlib import Path

from documentos.mapeamentos.ficha_cadastral import MAPEAMENTO_FICHA_CADASTRAL
from utils.caminhos import caminho_recurso


PASTA_MODELOS = caminho_recurso("documentos", "modelos")

DOCUMENTO_FICHA_CADASTRAL = "ficha_cadastral"
DOCUMENTO_PEDIDO_MEMBRAMENTO = "pedido_membramento"
DOCUMENTO_PEDIDO_RECONCILIACAO = "pedido_reconciliacao"


@dataclass(frozen=True)
class DocumentoOficial:
    codigo: str
    titulo: str
    modelo_pdf: Path
    editor_classe: str
    mapeamento: dict | None = None


DOCUMENTOS_OFICIAIS = {
    DOCUMENTO_FICHA_CADASTRAL: DocumentoOficial(
        codigo=DOCUMENTO_FICHA_CADASTRAL,
        titulo="Ficha Cadastral",
        modelo_pdf=PASTA_MODELOS / "ficha_cadastral.pdf",
        editor_classe="EditorFichaCadastral",
        mapeamento=MAPEAMENTO_FICHA_CADASTRAL,
    ),
    DOCUMENTO_PEDIDO_MEMBRAMENTO: DocumentoOficial(
        codigo=DOCUMENTO_PEDIDO_MEMBRAMENTO,
        titulo="Pedido de Membramento",
        modelo_pdf=PASTA_MODELOS / "pedido_membramento.pdf",
        editor_classe="EditorMembramento",
    ),
    DOCUMENTO_PEDIDO_RECONCILIACAO: DocumentoOficial(
        codigo=DOCUMENTO_PEDIDO_RECONCILIACAO,
        titulo="Pedido de Reconciliacao",
        modelo_pdf=PASTA_MODELOS / "pedido_reconciliacao.pdf",
        editor_classe="EditorReconciliacao",
    ),
}


def listar_documentos_oficiais():
    return list(DOCUMENTOS_OFICIAIS.values())


def obter_documento_oficial(codigo):
    try:
        return DOCUMENTOS_OFICIAIS[codigo]
    except KeyError as erro:
        raise ValueError(f"Documento oficial desconhecido: {codigo}") from erro
