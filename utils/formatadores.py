import re
import unicodedata
from datetime import datetime


def formatar_data_hora(valor):
    """Formata datas salvas pelo SIGM para exibicao curta."""
    texto = str(valor or "").strip()
    if not texto:
        return "-"

    for formato in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(texto, formato).strftime("%d/%m/%Y %H:%M")
        except ValueError:
            pass

    return texto


def normalizar_texto_busca(valor):
    """Normaliza texto para buscas simples sem diferenciar acentos."""
    texto = str(valor or "").strip().lower()
    texto = unicodedata.normalize("NFD", texto)
    return "".join(
        caractere
        for caractere in texto
        if unicodedata.category(caractere) != "Mn"
    )


def formatar_cpf(valor, parcial=False):
    """Coloca pontos e traco no CPF: 12345678909 -> 123.456.789-09.

    parcial=True formata enquanto a pessoa digita (campos do formulario).
    Com parcial=False so formata se houver exatamente 11 digitos; qualquer
    outro texto e devolvido como foi digitado.
    """
    texto = str(valor or "").strip()
    digitos = re.sub(r"\D", "", texto)
    if parcial:
        digitos = digitos[:11]
        if len(digitos) <= 3:
            return digitos
        if len(digitos) <= 6:
            return f"{digitos[:3]}.{digitos[3:]}"
        if len(digitos) <= 9:
            return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:]}"
        return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"
    if len(digitos) != 11 or re.search(r"[A-Za-z]", texto):
        return texto
    return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"


def formatar_rg(valor):
    """Coloca pontos e traco no RG de 9 caracteres: 426526458 -> 42.652.645-8.

    O ultimo caractere pode ser digito ou X. RGs em outros formatos (outros
    estados, tamanhos diferentes) sao devolvidos exatamente como digitados.
    """
    texto = str(valor or "").strip()
    limpo = re.sub(r"[.\-\s]", "", texto).upper()
    if not re.fullmatch(r"\d{8}[0-9X]", limpo):
        return texto
    return f"{limpo[:2]}.{limpo[2:5]}.{limpo[5:8]}-{limpo[8]}"
