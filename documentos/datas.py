import re
from datetime import datetime


FORMATOS_DATA_DOCUMENTO = (
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d %m %Y",
    "%Y-%m-%d",
)


def separar_data_documento(valor):
    """Separa datas usadas nos documentos em dia, mes e ano."""
    texto = str(valor or "").strip()
    if not texto:
        return "", "", ""

    for formato in FORMATOS_DATA_DOCUMENTO:
        try:
            data = datetime.strptime(texto, formato)
            return data.strftime("%d"), data.strftime("%m"), data.strftime("%Y")
        except ValueError:
            pass

    partes = re.findall(r"\d+", texto)
    if len(partes) != 3:
        return "", "", ""

    if len(partes[0]) == 4:
        candidato = f"{partes[0]}-{partes[1].zfill(2)}-{partes[2].zfill(2)}"
        formato = "%Y-%m-%d"
    else:
        candidato = f"{partes[0].zfill(2)}/{partes[1].zfill(2)}/{partes[2]}"
        formato = "%d/%m/%Y"

    try:
        data = datetime.strptime(candidato, formato)
    except ValueError:
        return "", "", ""

    return data.strftime("%d"), data.strftime("%m"), data.strftime("%Y")


CAMPOS_DATA_BR = (
    "data_nascimento", "data_nascimento_conjuge", "data_funcao",
    "batismo_aguas", "data_batismo_espirito_santo",
)
CAMPOS_BATISMO = ("batismo_aguas", "data_batismo_espirito_santo")


def data_para_br(valor):
    """2023-09-16 (ou 2023-09-16T10:00:00) -> 16/09/2023. Outros textos ficam como estao."""
    texto = str(valor or "").strip()
    achou = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})(?:[T ].*)?", texto)
    if achou:
        return f"{achou.group(3)}/{achou.group(2)}/{achou.group(1)}"
    return texto


def valor_sim_nao(valor):
    """True/'true'/1 -> 'Sim'; False/'false'/0 -> 'Nao' (com acento); senao None."""
    if valor is True:
        return "Sim"
    if valor is False:
        return "Não"
    texto = str(valor or "").strip().lower()
    if texto in ("true", "sim", "s", "1"):
        return "Sim"
    if texto in ("false", "nao", "não", "n", "0"):
        return "Não"
    return None


def normalizar_campo_data(campo, valor):
    """Campo de data no padrao brasileiro; nos batismos tambem troca True/False por Sim/Nao."""
    if campo in CAMPOS_BATISMO:
        sim_nao = valor_sim_nao(valor)
        if sim_nao and not re.search(r"\d{2}", str(valor)):
            return sim_nao
    return data_para_br(valor)
