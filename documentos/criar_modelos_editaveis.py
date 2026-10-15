import sys
from pathlib import Path

try:
    import fitz
except ImportError as erro:
    raise SystemExit(
        "PyMuPDF nao esta instalado. Instale com: pip install PyMuPDF"
    ) from erro

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from documentos.campos_documentos import DOCUMENTOS_EDITAVEIS


PASTA_MODELOS = BASE_DIR / "documentos" / "modelos"
PASTA_MODELOS_EDITAVEIS = BASE_DIR / "documentos" / "modelos_editaveis"

MODELOS_DOCUMENTOS = {
    "ficha_cadastral": {
        "entrada": PASTA_MODELOS / "ficha_cadastral.pdf",
        "saida": PASTA_MODELOS_EDITAVEIS / "ficha_cadastral_editavel.pdf",
    },
    "pedido_membramento": {
        "entrada": PASTA_MODELOS / "pedido_membramento.pdf",
        "saida": PASTA_MODELOS_EDITAVEIS / "pedido_membramento_editavel.pdf",
    },
    "pedido_reconciliacao": {
        "entrada": PASTA_MODELOS / "pedido_reconciliacao.pdf",
        "saida": PASTA_MODELOS_EDITAVEIS / "pedido_reconciliacao_editavel.pdf",
    },
}


def criar_retangulo_campo(configuracao):
    return fitz.Rect(
        configuracao["x"],
        configuracao["y"],
        configuracao["x"] + configuracao["largura"],
        configuracao["y"] + configuracao["altura"],
    )


def criar_widget_texto(pagina, configuracao):
    nome = configuracao["nome"]

    widget = fitz.Widget()
    widget.field_name = nome
    widget.field_label = nome
    widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
    widget.field_value = ""
    widget.rect = criar_retangulo_campo(configuracao)
    widget.text_font = "Helv"
    widget.text_fontsize = configuracao.get("fonte", 9)
    widget.text_color = (0, 0, 0)
    widget.fill_color = (1, 1, 0.85)
    widget.border_color = (1, 0, 0)
    widget.border_width = 1

    if configuracao.get("multilinha"):
        widget.field_flags = fitz.PDF_TX_FIELD_IS_MULTILINE

    pagina.add_widget(widget)


def criar_widget_checkbox(pagina, configuracao):
    nome = configuracao["nome"]

    widget = fitz.Widget()
    widget.field_name = nome
    widget.field_label = nome
    widget.field_type = fitz.PDF_WIDGET_TYPE_CHECKBOX
    widget.field_value = False
    widget.rect = criar_retangulo_campo(configuracao)
    widget.fill_color = (1, 1, 0.85)
    widget.border_color = (1, 0, 0)
    widget.border_width = 1

    pagina.add_widget(widget)


def criar_widget(pagina, configuracao):
    tipo = configuracao.get("tipo", "texto")

    if tipo == "checkbox":
        criar_widget_checkbox(pagina, configuracao)
        return

    criar_widget_texto(pagina, configuracao)


def criar_documento_editavel(nome_documento):
    configuracao_documento = MODELOS_DOCUMENTOS[nome_documento]
    caminho_modelo = configuracao_documento["entrada"]
    caminho_saida = configuracao_documento["saida"]

    if not caminho_modelo.exists():
        raise FileNotFoundError(f"Modelo nao encontrado: {caminho_modelo}")

    PASTA_MODELOS_EDITAVEIS.mkdir(parents=True, exist_ok=True)

    documento = fitz.open(str(caminho_modelo))
    try:
        for configuracao_campo in DOCUMENTOS_EDITAVEIS[nome_documento]:
            pagina = documento[configuracao_campo["pagina"]]
            criar_widget(pagina, configuracao_campo)

        documento.save(str(caminho_saida), deflate=True, garbage=4)
    finally:
        documento.close()

    return caminho_saida


def criar_todos_modelos_editaveis():
    return [
        criar_documento_editavel(nome_documento)
        for nome_documento in MODELOS_DOCUMENTOS
    ]


def criar_ficha_cadastral_editavel():
    return criar_documento_editavel("ficha_cadastral")


def criar_pedido_membramento_editavel():
    return criar_documento_editavel("pedido_membramento")


def criar_pedido_reconciliacao_editavel():
    return criar_documento_editavel("pedido_reconciliacao")


if __name__ == "__main__":
    for caminho in criar_todos_modelos_editaveis():
        print(f"PDF editavel criado: {caminho}")
