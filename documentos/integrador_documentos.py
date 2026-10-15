from datetime import date
from pathlib import Path
import unicodedata

from banco.database import (
    buscar_configuracoes_igreja,
    buscar_data_funcao_membro,
    buscar_membro_por_id,
    conectar,
)
from documentos.datas import separar_data_documento
from utils.caminhos import base_dados, caminho_dados


CAMPOS_MEMBRO = [
    "id",
    "nome",
    "rg",
    "orgao_emissor",
    "cpf",
    "data_nascimento",
    "estado_civil",
    "profissao",
    "telefone",
    "celular",
    "email",
    "endereco",
    "numero",
    "bairro",
    "cidade",
    "estado",
    "batismo_aguas",
    "ministerio",
    "cargo",
    "status",
    "observacoes",
    "nome_pai",
    "nome_mae",
    "cidade_nascimento",
    "estado_nascimento",
    "nome_conjuge",
    "data_nascimento_conjuge",
    "grau_instrucao",
    "curso_teologico",
    "data_batismo_espirito_santo",
    "cep",
]

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

CAMPOS_FOTO_MEMBRO = (
    "foto",
    "foto_membro",
    "caminho_foto",
    "foto_path",
    "imagem",
    "imagem_membro",
)
EXTENSOES_FOTO_MEMBRO = (".jpg", ".jpeg", ".png", ".webp", ".bmp")
PASTA_FOTOS_MEMBROS = caminho_dados("fotos_membros", criar_pai=False)
FUNCOES_MINISTERIAIS_PDF = {
    "cooperador": "cooperador",
    "diacono": "diacono",
    "presbitero": "presbitero",
    "evangelista": "evangelista",
    "pastor": "pastor",
}
CAMPOS_DATA_CONSAGRACAO_FUNCAO = {
    "cooperador": "data_consagracao_cooperador",
    "diacono": "data_consagracao_diacono",
    "presbitero": "data_consagracao_presbitero",
    "evangelista": "data_consagracao_evangelista",
    "pastor": "data_consagracao_pastor",
}
CAMPOS_LOCAL_FUNCAO = {
    "cooperador": "igreja_local_cooperador",
    "diacono": "igreja_local_diacono",
    "presbitero": "igreja_local_presbitero",
    "evangelista": "igreja_local_convencao_evangelista",
    "pastor": "igreja_local_convencao_pastor",
}


def valor_texto(dados, chave):
    if not dados:
        return ""

    valor = dados.get(chave, "")
    if valor is None:
        return ""

    return str(valor)


def citar_identificador_sqlite(nome):
    return '"' + str(nome).replace('"', '""') + '"'


def normalizar_caminho_foto(caminho):
    texto = str(caminho or "").strip()
    if not texto:
        return ""

    caminho_foto = Path(texto)
    candidatos = [caminho_foto]
    if not caminho_foto.is_absolute():
        candidatos.extend((Path.cwd() / caminho_foto, base_dados() / caminho_foto))

    for candidato in candidatos:
        if candidato.exists() and candidato.is_file():
            return str(candidato.resolve())

    return texto


def buscar_foto_membro_por_coluna(id_membro):
    conexao = conectar()
    try:
        cursor = conexao.cursor()
        cursor.execute("PRAGMA table_info(membros)")
        colunas = {
            str(coluna[1]).lower(): str(coluna[1])
            for coluna in cursor.fetchall()
        }

        for campo in CAMPOS_FOTO_MEMBRO:
            coluna = colunas.get(campo)
            if not coluna:
                continue

            cursor.execute(
                f"""
                SELECT {citar_identificador_sqlite(coluna)}
                FROM membros
                WHERE id = ?
                """,
                (id_membro,),
            )
            resultado = cursor.fetchone()
            if resultado and resultado[0]:
                return normalizar_caminho_foto(resultado[0])
    finally:
        conexao.close()

    return ""


def buscar_foto_membro_por_arquivo(id_membro):
    if not PASTA_FOTOS_MEMBROS.exists():
        return ""

    prefixos = (
        str(id_membro),
        f"membro_{id_membro}",
        f"foto_{id_membro}",
    )

    for arquivo in PASTA_FOTOS_MEMBROS.iterdir():
        if not arquivo.is_file():
            continue

        nome = arquivo.name.lower()
        if arquivo.suffix.lower() not in EXTENSOES_FOTO_MEMBRO:
            continue

        if any(nome.startswith(prefixo.lower()) for prefixo in prefixos):
            return str(arquivo.resolve())

    return ""


def buscar_caminho_foto_membro(id_membro):
    caminho_coluna = buscar_foto_membro_por_coluna(id_membro)

    # Caminho gravado no banco existe: comportamento de sempre.
    if caminho_coluna and Path(caminho_coluna).is_file():
        return caminho_coluna

    # O caminho gravado no banco aponta para um arquivo que NAO existe neste
    # computador (banco levado de outro PC, pasta movida ou apagada...).
    # Antes, esse caminho "morto" impedia de achar a foto - aqui tentamos o
    # mesmo nome de arquivo dentro da pasta de fotos deste computador e, em
    # seguida, a convencao foto_<id>.
    if caminho_coluna:
        nome_arquivo = Path(str(caminho_coluna).replace("\\", "/")).name
        if nome_arquivo:
            candidato = PASTA_FOTOS_MEMBROS / nome_arquivo
            if candidato.is_file():
                return str(candidato.resolve())

    caminho_arquivo = buscar_foto_membro_por_arquivo(id_membro)
    if caminho_arquivo:
        return caminho_arquivo

    # Nada encontrado: devolve o mesmo valor de antes.
    return caminho_coluna


def converter_tupla_para_dicionario(tupla, campos):
    if not tupla:
        return {campo: "" for campo in campos}

    return {
        campo: str(tupla[indice] or "") if indice < len(tupla) else ""
        for indice, campo in enumerate(campos)
    }


def converter_membro_para_dicionario(membro):
    return converter_tupla_para_dicionario(membro, CAMPOS_MEMBRO)


def buscar_campos_opcionais_membro(id_membro, campos):
    conexao = conectar()
    try:
        cursor = conexao.cursor()
        cursor.execute("PRAGMA table_info(membros)")
        colunas = {
            str(coluna[1]).lower(): str(coluna[1])
            for coluna in cursor.fetchall()
        }
        campos_existentes = [
            (campo, colunas[campo])
            for campo in campos
            if campo in colunas
        ]
        if not campos_existentes:
            return {}

        selecao = ", ".join(
            citar_identificador_sqlite(coluna)
            for _campo, coluna in campos_existentes
        )
        cursor.execute(
            f"""
            SELECT {selecao}
            FROM membros
            WHERE id = ?
            """,
            (id_membro,),
        )
        resultado = cursor.fetchone()
        if not resultado:
            return {}

        return {
            campo: str(resultado[indice] or "")
            for indice, (campo, _coluna) in enumerate(campos_existentes)
        }
    finally:
        conexao.close()


def separar_data(valor):
    return separar_data_documento(valor)


def formatar_cidade_estado(cidade, estado):
    cidade = str(cidade or "").strip()
    estado = str(estado or "").strip()

    if cidade and estado:
        return f"{cidade} - {estado}"
    return cidade or estado


def local_igreja_configurada(configuracoes):
    return (
        valor_texto(configuracoes, "congregacao_local_nome")
        or valor_texto(configuracoes, "congregacao_sede")
        or valor_texto(configuracoes, "nome_igreja")
    )


def congregacao_convencao(congregacao, configuracoes):
    partes = [
        str(congregacao or "").strip(),
        valor_texto(configuracoes, "convencao"),
    ]
    return " - ".join(parte for parte in partes if parte)


def normalizar_funcao_atual(valor):
    texto = str(valor or "").strip().lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(
        caractere
        for caractere in texto
        if unicodedata.category(caractere) != "Mn"
    )
    return FUNCOES_MINISTERIAIS_PDF.get(texto, "")


def dados_ministeriais_funcao_atual(
    funcao_atual,
    membro,
    local_igreja,
    local_convencao,
    data_funcao_legada,
):
    campos = {}
    for nome_campo in FUNCOES_MINISTERIAIS_PDF.values():
        campos[f"{nome_campo}_dia"] = ""
        campos[f"{nome_campo}_mes"] = ""
        campos[f"{nome_campo}_ano"] = ""
    for nome_campo in CAMPOS_LOCAL_FUNCAO.values():
        campos[nome_campo] = ""

    nome_pdf = normalizar_funcao_atual(funcao_atual)
    if not nome_pdf:
        return campos

    campo_data = CAMPOS_DATA_CONSAGRACAO_FUNCAO[nome_pdf]
    if campo_data in membro:
        data_funcao = valor_texto(membro, campo_data)
    else:
        data_funcao = data_funcao_legada

    dia, mes, ano = separar_data_documento(data_funcao)
    campos[f"{nome_pdf}_dia"] = dia
    campos[f"{nome_pdf}_mes"] = mes
    campos[f"{nome_pdf}_ano"] = ano
    campos[CAMPOS_LOCAL_FUNCAO[nome_pdf]] = (
        local_convencao
        if nome_pdf in {"evangelista", "pastor"}
        else local_igreja
    )
    return campos


def montar_dados_documento(id_membro):
    membro = converter_membro_para_dicionario(buscar_membro_por_id(id_membro))
    membro.update(
        buscar_campos_opcionais_membro(
            id_membro,
            (
                "igreja_local_batismo_aguas",
                "igreja_local_batismo_espirito_santo",
                *CAMPOS_DATA_CONSAGRACAO_FUNCAO.values(),
            ),
        )
    )
    configuracoes = buscar_configuracoes_igreja()
    hoje = date.today()
    caminho_foto = buscar_caminho_foto_membro(id_membro)

    nascimento_dia, nascimento_mes, nascimento_ano = separar_data(
        valor_texto(membro, "data_nascimento")
    )
    batismo_dia, batismo_mes, batismo_ano = separar_data(
        valor_texto(membro, "batismo_aguas")
    )
    batismo_espirito = valor_texto(membro, "data_batismo_espirito_santo")
    batismo_espirito_dia, batismo_espirito_mes, batismo_espirito_ano = separar_data(
        batismo_espirito
    )
    conjuge_dia, conjuge_mes, conjuge_ano = separar_data(
        valor_texto(membro, "data_nascimento_conjuge")
    )
    funcao_atual = valor_texto(membro, "cargo")
    data_funcao = buscar_data_funcao_membro(id_membro)

    dirigente_local = valor_texto(
        configuracoes,
        "congregacao_local_dirigente",
    )
    congregacao = valor_texto(configuracoes, "congregacao_local_nome")
    local_igreja = local_igreja_configurada(configuracoes)
    local_igreja_ministerial = congregacao
    local_convencao_ministerial = congregacao_convencao(congregacao, configuracoes)
    dados_funcao_atual = dados_ministeriais_funcao_atual(
        funcao_atual,
        membro,
        local_igreja_ministerial,
        local_convencao_ministerial,
        data_funcao,
    )
    numero_congregacao = valor_texto(
        configuracoes,
        "congregacao_local_numero",
    )
    campo_setor = valor_texto(
        configuracoes,
        "congregacao_local_campo_setor",
    )
    cidade_congregacao = valor_texto(
        configuracoes,
        "congregacao_local_cidade",
    )
    estado_membro = valor_texto(membro, "estado")
    cidade_estado_nascimento = formatar_cidade_estado(
        valor_texto(membro, "cidade_nascimento"),
        valor_texto(membro, "estado_nascimento"),
    )

    dados = {
        "setor_campo": campo_setor or valor_texto(configuracoes, "setor"),
        "dirigente": dirigente_local,
        "nome_membro": valor_texto(membro, "nome"),
        "rg": valor_texto(membro, "rg"),
        "orgao_emissor": valor_texto(membro, "orgao_emissor"),
        "cpf": valor_texto(membro, "cpf"),
        "data_nascimento": valor_texto(membro, "data_nascimento"),
        "data_nascimento_dia": nascimento_dia,
        "data_nascimento_mes": nascimento_mes,
        "data_nascimento_ano": nascimento_ano,
        "estado_civil": valor_texto(membro, "estado_civil"),
        "profissao": valor_texto(membro, "profissao"),
        "pai": valor_texto(membro, "nome_pai"),
        "mae": valor_texto(membro, "nome_mae"),
        "nome_pai": valor_texto(membro, "nome_pai"),
        "nome_mae": valor_texto(membro, "nome_mae"),
        "cidade_nascimento": valor_texto(membro, "cidade_nascimento"),
        "estado_nascimento": valor_texto(membro, "estado_nascimento"),
        "cidade_estado_nascimento": cidade_estado_nascimento,
        "conjuge": valor_texto(membro, "nome_conjuge"),
        "nome_conjuge": valor_texto(membro, "nome_conjuge"),
        "data_nascimento_conjuge": valor_texto(membro, "data_nascimento_conjuge"),
        "data_nascimento_conjuge_dia": conjuge_dia,
        "data_nascimento_conjuge_mes": conjuge_mes,
        "data_nascimento_conjuge_ano": conjuge_ano,
        "grau_instrucao": valor_texto(membro, "grau_instrucao"),
        "grau_instrucao_secular": valor_texto(membro, "grau_instrucao"),
        "curso_teologico": valor_texto(membro, "curso_teologico"),
        "residencial": valor_texto(membro, "telefone"),
        "telefone": valor_texto(membro, "telefone"),
        "celular": valor_texto(membro, "celular"),
        "email": valor_texto(membro, "email"),
        "rua": valor_texto(membro, "endereco"),
        "endereco": valor_texto(membro, "endereco"),
        "numero": valor_texto(membro, "numero"),
        "bairro": valor_texto(membro, "bairro"),
        "cidade": valor_texto(membro, "cidade"),
        "uf": estado_membro,
        "estado": estado_membro,
        "cep": valor_texto(membro, "cep"),
        "batismo_aguas": valor_texto(membro, "batismo_aguas"),
        "batismo_aguas_dia": batismo_dia,
        "batismo_aguas_mes": batismo_mes,
        "batismo_aguas_ano": batismo_ano,
        "igreja_local_batismo_aguas": (
            valor_texto(membro, "igreja_local_batismo_aguas") or local_igreja
        ),
        "batismo_espirito_santo": batismo_espirito,
        "data_batismo_espirito_santo": batismo_espirito,
        "batismo_espirito_santo_dia": batismo_espirito_dia,
        "batismo_espirito_santo_mes": batismo_espirito_mes,
        "batismo_espirito_santo_ano": batismo_espirito_ano,
        "igreja_local_batismo_espirito_santo": (
            valor_texto(membro, "igreja_local_batismo_espirito_santo") or local_igreja
        ),
        "ministerio_membro": valor_texto(membro, "ministerio"),
        "cargo": funcao_atual,
        "data_funcao": data_funcao,
        "status": valor_texto(membro, "status"),
        "observacoes": valor_texto(membro, "observacoes"),
        "foto": caminho_foto,
        "foto_membro": caminho_foto,
        "caminho_foto": caminho_foto,
        "foto_path": caminho_foto,
        "nome_titular_lgpd": valor_texto(membro, "nome"),
        "local_cidade": (
            cidade_congregacao
            or valor_texto(configuracoes, "cidade")
            or valor_texto(membro, "cidade")
        ),
        "local_dia": str(hoje.day).zfill(2),
        "local_mes": MESES[hoje.month - 1],
        "local_ano": str(hoje.year),
        "pastor_presidente": valor_texto(configuracoes, "pastor_presidente"),
        "pastor_setorial": valor_texto(configuracoes, "pastor_setorial"),
        "dirigente_local": dirigente_local,
        "congregacao": congregacao,
        "numero_congregacao": numero_congregacao,
        "campo_setor": campo_setor,
        "cidade_congregacao": cidade_congregacao,
        "estado_congregacao": valor_texto(
            configuracoes,
            "congregacao_local_estado",
        ),
        "rua_congregacao": valor_texto(configuracoes, "congregacao_local_rua"),
        "numero_endereco_congregacao": valor_texto(
            configuracoes,
            "congregacao_local_numero_endereco",
        ),
        "bairro_congregacao": valor_texto(
            configuracoes,
            "congregacao_local_bairro",
        ),
        "cep_congregacao": valor_texto(configuracoes, "congregacao_local_cep"),
        "telefone_congregacao": valor_texto(
            configuracoes,
            "congregacao_local_telefone",
        ),
        "whatsapp_congregacao": valor_texto(
            configuracoes,
            "congregacao_local_whatsapp",
        ),
        "email_congregacao": valor_texto(
            configuracoes,
            "congregacao_local_email",
        ),
        "ministerio": valor_texto(configuracoes, "ministerio"),
        "convencao": valor_texto(configuracoes, "convencao"),
        "setor": valor_texto(configuracoes, "setor"),
        "congregacao_sede": valor_texto(configuracoes, "congregacao_sede"),
        "cidade_igreja": valor_texto(configuracoes, "cidade"),
        "estado_igreja": valor_texto(configuracoes, "estado"),
        "telefone_igreja": valor_texto(configuracoes, "telefone"),
        "whatsapp_igreja": valor_texto(configuracoes, "whatsapp"),
        "email_igreja": valor_texto(configuracoes, "email"),
        "site_igreja": valor_texto(configuracoes, "site"),
        "rua_igreja": valor_texto(configuracoes, "rua"),
        "numero_igreja": valor_texto(configuracoes, "numero"),
        "bairro_igreja": valor_texto(configuracoes, "bairro"),
        "cep_igreja": valor_texto(configuracoes, "cep"),
        "cidade_endereco_igreja": valor_texto(
            configuracoes,
            "cidade_endereco",
        ),
        "estado_endereco_igreja": valor_texto(
            configuracoes,
            "estado_endereco",
        ),
        "logo_igreja": valor_texto(configuracoes, "logotipo"),
        "carimbo": valor_texto(configuracoes, "carimbo"),
        "assinatura_pastor": valor_texto(configuracoes, "assinatura_pastor"),
    }
    dados.update(dados_funcao_atual)
    return dados
