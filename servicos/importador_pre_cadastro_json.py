import json
import unicodedata
import uuid
from pathlib import Path

from banco.database import (
    CAMPOS_CADASTRAIS_PRE_CADASTRO,
    registrar_sincronizacao_pre_cadastro,
    salvar_pre_cadastro,
)


CHAVES_RAIZ_LISTA = ("pre_cadastros", "cadastros", "dados")
CAMPOS_CAMINHO_ARQUIVO = {"caminho_foto", "foto", "foto_membro", "foto_path"}

ALIASES_CAMPOS = {
    "nome_completo": "nome",
    "nome_membro": "nome",
    "data_de_nascimento": "data_nascimento",
    "nascimento": "data_nascimento",
    "telefone_celular": "celular",
    "whatsapp": "celular",
    "e_mail": "email",
    "email": "email",
    "orgao": "orgao_emissor",
    "orgao_emissor": "orgao_emissor",
    "cidade_natal": "cidade_nascimento",
    "naturalidade": "cidade_nascimento",
    "uf_nascimento": "estado_nascimento",
    "estado_natal": "estado_nascimento",
    "uf": "estado",
    "rua": "endereco",
    "residencial": "telefone",
    "ministerio_membro": "ministerio",
    "funcao": "cargo",
    "funcao_atual": "cargo",
    "data_da_funcao": "data_funcao",
    "status": "status_membro",
    "status_cadastral": "status_membro",
}


class ImportacaoPreCadastroErro(ValueError):
    pass


def normalizar_chave(chave):
    texto = str(chave or "").strip().lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(
        caractere
        for caractere in texto
        if unicodedata.category(caractere) != "Mn"
    )
    texto = texto.replace("-", "_").replace(" ", "_")
    while "__" in texto:
        texto = texto.replace("__", "_")
    return texto.strip("_")


def carregar_json(caminho_arquivo):
    caminho = Path(caminho_arquivo)
    try:
        with caminho.open("r", encoding="utf-8-sig") as arquivo:
            return json.load(arquivo)
    except json.JSONDecodeError as erro:
        raise ImportacaoPreCadastroErro(f"JSON invalido: {erro}") from erro
    except OSError as erro:
        raise ImportacaoPreCadastroErro(f"Nao foi possivel ler o arquivo: {erro}") from erro


def extrair_itens_json(conteudo):
    if isinstance(conteudo, list):
        return conteudo

    if not isinstance(conteudo, dict):
        raise ImportacaoPreCadastroErro("Estrutura JSON incompativel.")

    for chave in CHAVES_RAIZ_LISTA:
        valor = conteudo.get(chave)
        if isinstance(valor, list):
            return valor

    return [conteudo]


def valor_texto(valor):
    if valor is None:
        return ""
    if isinstance(valor, (dict, list)):
        return json.dumps(valor, ensure_ascii=False, sort_keys=True)
    return str(valor).strip()


def payload_json_original(item):
    return json.dumps(item, ensure_ascii=False, sort_keys=True)


def gerar_remote_id_local(item):
    payload = payload_json_original(item)
    return f"local-json-{uuid.uuid5(uuid.NAMESPACE_URL, payload)}"


def normalizar_item(item):
    dados = {
        "payload_json": payload_json_original(item),
        "origem": "importacao_json",
    }

    campos_cadastrais = set(CAMPOS_CADASTRAIS_PRE_CADASTRO)
    for chave, valor in item.items():
        chave_normalizada = normalizar_chave(chave)
        campo = ALIASES_CAMPOS.get(chave_normalizada, chave_normalizada)

        if campo in CAMPOS_CAMINHO_ARQUIVO:
            continue
        if campo in campos_cadastrais:
            dados[campo] = valor_texto(valor)
            continue
        if campo in {
            "remote_id",
            "identificador_publico_igreja",
            "status",
        }:
            dados[campo] = valor_texto(valor)

    if not str(dados.get("remote_id") or "").strip():
        dados["remote_id"] = gerar_remote_id_local(item)

    if not str(dados.get("status") or "").strip():
        dados["status"] = "pendente"

    return dados


def relatorio_vazio():
    return {
        "total_lido": 0,
        "inseridos": 0,
        "ignorados": 0,
        "invalidos": 0,
        "erros": [],
    }


def status_relatorio(relatorio):
    if relatorio["total_lido"] == 0 or relatorio["invalidos"] == relatorio["total_lido"]:
        return "erro"
    if relatorio["invalidos"] or relatorio["erros"]:
        return "parcial"
    return "sucesso"


def detalhes_relatorio(relatorio):
    return (
        "origem=importacao_json; "
        f"lidos={relatorio['total_lido']}; "
        f"novos={relatorio['inseridos']}; "
        f"ignorados={relatorio['ignorados']}; "
        f"invalidos={relatorio['invalidos']}"
    )


def registrar_historico_importacao(relatorio, erro=None):
    registrar_sincronizacao_pre_cadastro(
        status=status_relatorio(relatorio) if erro is None else "erro",
        quantidade_recebida=relatorio.get("total_lido", 0),
        quantidade_nova=relatorio.get("inseridos", 0),
        quantidade_ignorada=relatorio.get("ignorados", 0),
        erro=erro,
        detalhes=detalhes_relatorio(relatorio),
    )


def importar_pre_cadastros_json(caminho_arquivo):
    relatorio = relatorio_vazio()

    try:
        conteudo = carregar_json(caminho_arquivo)
        itens = extrair_itens_json(conteudo)
    except ImportacaoPreCadastroErro as erro:
        relatorio["erros"].append(str(erro))
        registrar_historico_importacao(relatorio, erro=str(erro))
        raise

    relatorio["total_lido"] = len(itens)
    if not itens:
        erro = "Nenhum pre-cadastro encontrado no arquivo."
        relatorio["erros"].append(erro)
        registrar_historico_importacao(relatorio, erro=erro)
        raise ImportacaoPreCadastroErro(erro)

    for indice, item in enumerate(itens, start=1):
        if not isinstance(item, dict):
            relatorio["invalidos"] += 1
            relatorio["erros"].append(f"Item {indice}: registro nao e um objeto.")
            continue

        try:
            dados = normalizar_item(item)
            resultado = salvar_pre_cadastro(dados)
        except Exception as erro:
            relatorio["invalidos"] += 1
            relatorio["erros"].append(f"Item {indice}: {erro}")
            continue

        if resultado.get("inserido"):
            relatorio["inseridos"] += 1
        else:
            relatorio["ignorados"] += 1

    registrar_historico_importacao(relatorio)
    return relatorio
