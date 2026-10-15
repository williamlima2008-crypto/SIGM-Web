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
