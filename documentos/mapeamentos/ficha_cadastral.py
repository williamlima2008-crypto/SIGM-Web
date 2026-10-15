from documentos.campos_documentos import FICHA_CADASTRAL as CAMPOS_OFICIAIS_FICHA


FONTE_PADRAO = "Helvetica"
TAMANHO_FONTE_PADRAO = 10
TAMANHO_FONTE_OBSERVACOES = 9
ALTURA_PAGINA_FICHA = 842
AJUSTE_BASE_TEXTO = 13
CAMPOS_DATA_CENTRALIZADOS = {
    "batismo_aguas",
    "batismo_espirito_santo",
    "cooperador",
    "diacono",
    "presbitero",
    "evangelista",
    "pastor",
    "data_nascimento",
    "data_nascimento_conjuge",
}


def converter_y_campo(campo):
    return ALTURA_PAGINA_FICHA - campo["y"] - AJUSTE_BASE_TEXTO


def campo_texto_oficial(campo):
    campo_convertido = campo.copy()
    campo_convertido["y"] = converter_y_campo(campo)

    nome = campo_convertido.get("nome", "")
    if any(
        nome in {f"{base}_dia", f"{base}_mes", f"{base}_ano"}
        for base in CAMPOS_DATA_CENTRALIZADOS
    ):
        campo_convertido["alinhamento"] = "centro"

    return campo_convertido


def montar_campos_ficha():
    campos = [
        {
            "nome": "foto_membro",
            "tipo": "imagem",
            "pagina": 0,
            "x": 489,
            "y": 734,
            "largura": 74,
            "altura": 82,
            "chaves_dados": ("foto", "foto_membro", "caminho_foto", "foto_path"),
        },
    ]
    campos.extend(campo_texto_oficial(campo) for campo in CAMPOS_OFICIAIS_FICHA)
    campos.append(
        {
            "nome": "observacoes",
            "pagina": 0,
            "x": 35,
            "y": 418,
            "tamanho": TAMANHO_FONTE_OBSERVACOES,
            "multilinha": True,
            "altura_linha": 24,
            "max_linhas": 5,
            "max_caracteres": 85,
        }
    )
    return campos


CAMPOS_FICHA_CADASTRAL = montar_campos_ficha()

MAPEAMENTO_FICHA_CADASTRAL = {
    "codigo": "ficha_cadastral",
    "titulo": "Ficha Cadastral",
    "modelo": "ficha_cadastral.pdf",
    "fonte": FONTE_PADRAO,
    "tamanho": TAMANHO_FONTE_PADRAO,
    "campos": CAMPOS_FICHA_CADASTRAL,
}
