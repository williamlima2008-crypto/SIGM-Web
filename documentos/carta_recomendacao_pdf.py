"""
Geracao da Carta de Recomendacao em PDF.

Usa como fundo da pagina uma digitalizacao real do formulario em
branco (documentos/modelos/carta_recomendacao_fundo.jpg), e sobrepoe
o texto nas posicoes corretas - a mesma tecnica ja usada em
documentos/ficha_cadastral_pdf.py para os outros documentos oficiais.

Campos preenchidos automaticamente:
- Nome, Cargo, Setor n. e Congregacao: vem do cadastro do membro;
- Cidade, data: cidade das configuracoes da igreja + data de hoje,
  por extenso (ex: "Guarulhos, 22 de setembro de 2026").

Campos deixados em branco por padrao, exatamente como no formulario
fisico (preenchidos a mao/assinados depois de impresso): Sexo (o
cadastro do membro ainda nao guarda esse dado). O campo "Apresentamos
a Assembleia de Deus em" pode ser preenchido opcionalmente atraves do
parametro 'apresentar_em' (ver telas/documentos/
editor_apresentacao_carta_recomendacao.py).

Campos com texto livre (Congregacao e Apresentar em) reduzem o
tamanho da fonte automaticamente se o texto for longo demais para
caber no espaco da caixa, para nunca "estourar" para fora da folha.
"""
from datetime import date
from pathlib import Path

from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

CAMINHO_FUNDO = Path(__file__).parent / "modelos" / "carta_recomendacao_fundo.jpg"

LARGURA_PAGINA = 16 * cm
ALTURA_PAGINA = 21 * cm

COR_TEXTO = (0, 0, 0)
FONTE = "Helvetica"
TAMANHO_FONTE_PADRAO = 10.5
TAMANHO_FONTE_MINIMO = 6.5

MESES_EXTENSO = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)

# Posicoes de cada campo: (fracao_x, fracao_y, largura_maxima_fracao).
# fracao_x/fracao_y sao relativas a pagina (0,0 = canto superior
# esquerdo). largura_maxima_fracao e o espaco disponivel para o texto
# (em fracao da largura da pagina) antes de a fonte comecar a
# encolher automaticamente. Calibradas visualmente sobre o fundo
# digitalizado - se o fundo for trocado por outro, reajustar aqui
# (gerar com uma grade de referencia sobreposta e comparar).
POSICOES = {
    "apresentar_em": (0.33, 0.388, 0.60),
    "nome_membro": (0.41, 0.531, 0.52),
    "cargo": (0.41, 0.569, 0.25),
    "sexo": (0.815, 0.569, 0.14),
    "setor_campo": (0.43, 0.606, 0.06),
    "congregacao": (0.66, 0.606, 0.32),
    "cidade_data": (0.32, 0.762, 0.60),
}


def _valor(dados, campo):
    return str((dados or {}).get(campo) or "").strip()


def _posicao_absoluta(frac_x, frac_y):
    return frac_x * LARGURA_PAGINA, ALTURA_PAGINA - frac_y * ALTURA_PAGINA


def _formatar_cidade_data(cidade):
    hoje = date.today()
    mes_nome = MESES_EXTENSO[hoje.month - 1]
    data_extenso = f"{hoje.day:02d} de {mes_nome} de {hoje.year}"
    cidade = (cidade or "").strip()
    if cidade:
        return f"{cidade}, {data_extenso}"
    return data_extenso


def _desenhar_texto_ajustavel(pdf, texto, frac_x, frac_y, largura_maxima_frac):
    """
    Desenha o texto na posição indicada, reduzindo a fonte se
    necessário para caber na largura disponível. Se mesmo no tamanho
    mínimo o texto ainda for largo demais (nomes muito longos), corta
    o final do texto e acrescenta reticências - para NUNCA desenhar
    texto para fora da página.
    """
    if not texto:
        return

    x, y = _posicao_absoluta(frac_x, frac_y)
    largura_maxima_pts = largura_maxima_frac * LARGURA_PAGINA

    tamanho = TAMANHO_FONTE_PADRAO
    while tamanho > TAMANHO_FONTE_MINIMO and pdf.stringWidth(texto, FONTE, tamanho) > largura_maxima_pts:
        tamanho -= 0.5
    tamanho = max(tamanho, TAMANHO_FONTE_MINIMO)

    texto_final = texto
    if pdf.stringWidth(texto_final, FONTE, tamanho) > largura_maxima_pts:
        while texto_final and pdf.stringWidth(texto_final + "...", FONTE, tamanho) > largura_maxima_pts:
            texto_final = texto_final[:-1]
        texto_final = texto_final.rstrip() + "..."

    pdf.setFont(FONTE, tamanho)
    pdf.drawString(x, y, texto_final)


def gerar_carta_recomendacao_pdf(dados, caminho_saida, dados_igreja=None, apresentar_em=""):
    """
    Gera a Carta de Recomendação em PDF, com o texto sobreposto à
    digitalização real do formulário.

    'dados' é o dicionário de dados do documento (mesmo formato usado
    pelos outros geradores: nome_membro, cargo, setor_campo,
    congregacao, ...). 'dados_igreja' fornece a cidade da igreja, para
    preencher "Cidade, data" automaticamente. 'apresentar_em' é o
    texto opcional da linha "Apresentamos à Assembléia de Deus em:".
    """
    caminho_saida = Path(caminho_saida)
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)

    if not CAMINHO_FUNDO.exists():
        raise FileNotFoundError(
            f"Imagem de fundo da Carta de Recomendação não encontrada: {CAMINHO_FUNDO}"
        )

    valores = dict(dados or {})
    if apresentar_em:
        valores["apresentar_em"] = apresentar_em
    valores["cidade_data"] = _formatar_cidade_data((dados_igreja or {}).get("cidade"))

    pdf = canvas.Canvas(str(caminho_saida), pagesize=(LARGURA_PAGINA, ALTURA_PAGINA))
    pdf.drawImage(
        str(CAMINHO_FUNDO), 0, 0,
        width=LARGURA_PAGINA, height=ALTURA_PAGINA,
        preserveAspectRatio=False,
    )

    pdf.setFillColorRGB(*COR_TEXTO)

    for campo, (frac_x, frac_y, largura_maxima) in POSICOES.items():
        texto = _valor(valores, campo)
        _desenhar_texto_ajustavel(pdf, texto, frac_x, frac_y, largura_maxima)

    pdf.save()
    return str(caminho_saida)
