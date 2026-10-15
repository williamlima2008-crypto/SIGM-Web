import re
import unicodedata
from difflib import SequenceMatcher

from banco.database import conectar


CAMPOS_MEMBRO_DUPLICIDADE = (
    "id",
    "nome",
    "rg",
    "orgao_emissor",
    "cpf",
    "data_nascimento",
    "telefone",
    "celular",
    "email",
    "endereco",
    "cidade",
    "nome_mae",
)


def remover_acentos(valor):
    texto = unicodedata.normalize("NFD", str(valor or ""))
    return "".join(
        caractere
        for caractere in texto
        if unicodedata.category(caractere) != "Mn"
    )


def normalizar_texto(valor):
    texto = remover_acentos(valor).lower()
    texto = re.sub(r"[^\w\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def somente_digitos(valor):
    return re.sub(r"\D", "", str(valor or ""))


def valor_util(valor):
    texto = str(valor or "").strip()
    if not texto:
        return ""
    digitos = somente_digitos(texto)
    if digitos and set(digitos) == {"0"}:
        return ""
    if not digitos and set(texto) == {"0"}:
        return ""
    return texto


def normalizar_cpf(valor):
    digitos = somente_digitos(valor_util(valor))
    if len(digitos) != 11:
        return ""
    if set(digitos) == {"0"}:
        return ""
    if len(set(digitos)) == 1:
        return ""

    soma = sum(int(digitos[indice]) * (10 - indice) for indice in range(9))
    primeiro = (soma * 10) % 11
    if primeiro == 10:
        primeiro = 0
    soma = sum(int(digitos[indice]) * (11 - indice) for indice in range(10))
    segundo = (soma * 10) % 11
    if segundo == 10:
        segundo = 0
    if primeiro != int(digitos[9]) or segundo != int(digitos[10]):
        return ""
    return digitos


def normalizar_rg(valor):
    texto = remover_acentos(valor_util(valor)).upper()
    texto = re.sub(r"[^A-Z0-9]", "", texto)
    if len(texto) < 5:
        return ""
    if len(set(texto)) == 1:
        return ""
    if set(texto) == {"0"}:
        return ""
    return texto


def normalizar_telefone(valor):
    digitos = somente_digitos(valor_util(valor))
    if len(digitos) < 8:
        return ""
    if set(digitos) == {"0"}:
        return ""
    return digitos


def normalizar_email(valor):
    email = str(valor_util(valor)).strip().lower()
    if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        return ""
    return email


def normalizar_data(valor):
    digitos = somente_digitos(valor)
    if len(digitos) == 8:
        if str(valor).strip().startswith(digitos[:4]):
            return f"{digitos[:4]}-{digitos[4:6]}-{digitos[6:]}"
        return f"{digitos[4:]}-{digitos[2:4]}-{digitos[:2]}"
    return normalizar_texto(valor)


def similaridade_nome(nome_a, nome_b):
    if not nome_a or not nome_b:
        return 0
    return SequenceMatcher(None, nome_a, nome_b).ratio()


def sobrenomes(nome):
    partes = [
        parte
        for parte in normalizar_texto(nome).split()
        if len(parte) > 2
    ]
    if len(partes) < 2:
        return set()
    return set(partes[1:])


def rg_compativel(pre_cadastro_norm, membro_norm):
    rg_pre = pre_cadastro_norm["rg"]
    rg_membro = membro_norm["rg"]
    if not rg_pre or rg_pre != rg_membro:
        return False

    orgao_pre = pre_cadastro_norm["orgao_emissor"]
    orgao_membro = membro_norm["orgao_emissor"]
    if orgao_pre and orgao_membro:
        return orgao_pre == orgao_membro
    return True


def descricao_risco(nivel):
    if nivel == "alto":
        return "Bloqueio por documento igual"
    if nivel == "medio":
        return "Possivel coincidencia familiar ou de contato"
    return "Informativo"


def buscar_membros_para_comparacao():
    conexao = conectar()
    try:
        cursor = conexao.cursor()
        cursor.execute("""
            SELECT
                id,
                nome,
                rg,
                orgao_emissor,
                cpf,
                data_nascimento,
                telefone,
                celular,
                email,
                endereco,
                cidade,
                nome_mae
            FROM membros
        """)
        return [
            {
                campo: resultado[indice] if indice < len(resultado) else ""
                for indice, campo in enumerate(CAMPOS_MEMBRO_DUPLICIDADE)
            }
            for resultado in cursor.fetchall()
        ]
    finally:
        conexao.close()


def dados_normalizados(registro):
    return {
        "nome": normalizar_texto(registro.get("nome")),
        "rg": normalizar_rg(registro.get("rg")),
        "orgao_emissor": normalizar_texto(registro.get("orgao_emissor")),
        "cpf": normalizar_cpf(registro.get("cpf")),
        "data_nascimento": normalizar_data(registro.get("data_nascimento")),
        "telefone": normalizar_telefone(registro.get("telefone")),
        "celular": normalizar_telefone(registro.get("celular")),
        "email": normalizar_email(registro.get("email")),
        "endereco": normalizar_texto(registro.get("endereco")),
        "cidade": normalizar_texto(registro.get("cidade")),
        "nome_mae": normalizar_texto(registro.get("nome_mae")),
    }


def adicionar_motivo(motivos, texto):
    if texto not in motivos:
        motivos.append(texto)


def pontuar_candidato(pre_cadastro_norm, membro_norm):
    motivos_altos = []
    motivos_medios = []
    motivos_baixos = []

    if pre_cadastro_norm["cpf"] and pre_cadastro_norm["cpf"] == membro_norm["cpf"]:
        adicionar_motivo(motivos_altos, "CPF valido igual")

    if rg_compativel(pre_cadastro_norm, membro_norm):
        if pre_cadastro_norm["orgao_emissor"] and membro_norm["orgao_emissor"]:
            adicionar_motivo(motivos_altos, "RG valido igual com orgao emissor igual")
        else:
            adicionar_motivo(motivos_altos, "RG valido igual")

    nome_igual = (
        pre_cadastro_norm["nome"]
        and pre_cadastro_norm["nome"] == membro_norm["nome"]
    )
    if nome_igual and pre_cadastro_norm["data_nascimento"] and pre_cadastro_norm["data_nascimento"] == membro_norm["data_nascimento"]:
        adicionar_motivo(motivos_medios, "nome e data de nascimento iguais")
    if nome_igual and pre_cadastro_norm["nome_mae"] and pre_cadastro_norm["nome_mae"] == membro_norm["nome_mae"]:
        adicionar_motivo(motivos_medios, "nome e nome da mae iguais")

    for campo, motivo in (
        ("email", "e-mail igual"),
        ("celular", "celular igual"),
        ("telefone", "telefone igual"),
    ):
        if pre_cadastro_norm[campo] and pre_cadastro_norm[campo] == membro_norm[campo]:
            adicionar_motivo(motivos_medios, motivo)

    similaridade = similaridade_nome(pre_cadastro_norm["nome"], membro_norm["nome"])
    nome_muito_parecido = similaridade >= 0.92
    nome_parecido = similaridade >= 0.82

    if nome_muito_parecido and not nome_igual:
        adicionar_motivo(motivos_baixos, "nome muito parecido")
    elif nome_parecido and not nome_igual:
        adicionar_motivo(motivos_baixos, "nome parecido")

    if nome_igual and not (
        pre_cadastro_norm["data_nascimento"]
        and pre_cadastro_norm["data_nascimento"] == membro_norm["data_nascimento"]
    ) and not (
        pre_cadastro_norm["nome_mae"]
        and pre_cadastro_norm["nome_mae"] == membro_norm["nome_mae"]
    ):
        adicionar_motivo(motivos_baixos, "nome igual")

    if nome_parecido and pre_cadastro_norm["data_nascimento"] and pre_cadastro_norm["data_nascimento"] == membro_norm["data_nascimento"]:
        adicionar_motivo(motivos_baixos, "nome parecido e mesma data de nascimento")
    if nome_parecido and pre_cadastro_norm["nome_mae"] and pre_cadastro_norm["nome_mae"] == membro_norm["nome_mae"]:
        adicionar_motivo(motivos_baixos, "nome parecido e mesmo nome da mae")
    if pre_cadastro_norm["cidade"] and pre_cadastro_norm["cidade"] == membro_norm["cidade"]:
        adicionar_motivo(motivos_baixos, "mesma cidade")
    if pre_cadastro_norm["endereco"] and pre_cadastro_norm["endereco"] == membro_norm["endereco"]:
        adicionar_motivo(motivos_baixos, "mesmo endereco")

    sobrenomes_pre = sobrenomes(pre_cadastro_norm["nome"])
    sobrenomes_membro = sobrenomes(membro_norm["nome"])
    if sobrenomes_pre and sobrenomes_pre.intersection(sobrenomes_membro):
        adicionar_motivo(motivos_baixos, "mesmo sobrenome")

    if motivos_altos:
        pontuacao = 100
        nivel = "alto"
        motivos = motivos_altos + motivos_medios + motivos_baixos
    elif motivos_medios:
        pontuacao = min(79, 55 + (len(motivos_medios) * 8) + min(len(motivos_baixos), 2) * 3)
        nivel = "medio"
        motivos = motivos_medios + motivos_baixos
    elif motivos_baixos:
        pontuacao = min(45, 15 + (len(motivos_baixos) * 5))
        nivel = "baixo"
        motivos = motivos_baixos
    else:
        pontuacao = 0
        nivel = ""
        motivos = []

    return pontuacao, nivel, motivos


def montar_candidato(membro, pontuacao, nivel, motivos):
    return {
        "membro_id": membro.get("id"),
        "nome": membro.get("nome") or "",
        "rg": membro.get("rg") or "",
        "orgao_emissor": membro.get("orgao_emissor") or "",
        "cpf": membro.get("cpf") or "",
        "celular": membro.get("celular") or "",
        "email": membro.get("email") or "",
        "data_nascimento": membro.get("data_nascimento") or "",
        "pontuacao": pontuacao,
        "nivel": nivel,
        "descricao_risco": descricao_risco(nivel),
        "motivos": motivos,
    }


def detectar_duplicidades_pre_cadastro(pre_cadastro):
    pre_cadastro = pre_cadastro or {}
    pre_cadastro_norm = dados_normalizados(pre_cadastro)
    candidatos = []

    for membro in buscar_membros_para_comparacao():
        membro_norm = dados_normalizados(membro)
        pontuacao, nivel, motivos = pontuar_candidato(pre_cadastro_norm, membro_norm)
        if not motivos:
            continue

        candidatos.append(montar_candidato(membro, pontuacao, nivel, motivos))

    candidatos.sort(
        key=lambda candidato: (
            candidato["pontuacao"],
            candidato["nivel"] == "alto",
            candidato["membro_id"] or 0,
        ),
        reverse=True,
    )
    return candidatos


def encontrar_membro_correspondente_exato(pre_cadastro):
    """
    Retorna o id do membro cujo CPF, RG e Nome (todos normalizados)
    batem exatamente com o pre-cadastro informado, ou None se algum
    desses tres dados estiver ausente/invalido no pre-cadastro, ou se
    nao houver uma correspondencia unica e inequivoca.

    Usado para decidir quando um pre-cadastro deve ATUALIZAR um
    membro ja existente em vez de criar um novo (e sem exigir revisao
    manual na tela de duplicidades) - a regra e deliberadamente
    rigorosa (exige os tres dados batendo) para nunca mesclar por
    engano os cadastros de duas pessoas diferentes.
    """
    pre_cadastro = pre_cadastro or {}
    pre_norm = dados_normalizados(pre_cadastro)

    if not (pre_norm["cpf"] and pre_norm["rg"] and pre_norm["nome"]):
        return None

    correspondencias = []
    for membro in buscar_membros_para_comparacao():
        membro_norm = dados_normalizados(membro)
        if (
            membro_norm["cpf"] == pre_norm["cpf"]
            and membro_norm["rg"] == pre_norm["rg"]
            and membro_norm["nome"] == pre_norm["nome"]
        ):
            correspondencias.append(membro.get("id"))

    if len(correspondencias) == 1:
        return correspondencias[0]
    return None
