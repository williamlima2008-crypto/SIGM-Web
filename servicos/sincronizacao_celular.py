"""Sincronizacao do SIGM Desktop com o SIGM Celular (o desktop manda).

- ENVIAR: o desktop envia ao Celular os membros novos ou alterados (comparando
  um "hash" de cada membro), as fotos, os dados da igreja usados nos documentos
  e, no fim, a lista de ids para o Celular remover quem foi apagado aqui.
- ALTERACOES: pessoas autorizadas no Celular enviam SUGESTOES de alteracao.
  O desktop busca, o usuario confere e APLICA ou REJEITA; o resultado volta
  para o Celular.

Usa a mesma identidade online da igreja (endereco, identificador e chave) ja
configurada para os pre-cadastros. Para o Celular ficar em outro endereco, defina
a variavel de ambiente SIGM_CELULAR_API_URL.
"""

import base64
import hashlib
import io
import json
import os
from pathlib import Path

from banco.database import (
    buscar_configuracao_online_igreja,
    buscar_configuracoes_igreja,
    conectar,
    garantir_colunas_complementares_membro,
    obter_coluna_data_funcao_membro,
)
from servicos.cliente_sigm_online import (
    ClienteSIGMOnline,
    SIGMOnlineConfiguracaoErro,
    SIGMOnlineErro,
    SIGMOnlineRespostaErro,
)
from documentos.datas import CAMPOS_DATA_BR, normalizar_campo_data
from utils.auditoria import registrar_acao
from utils.formatadores import formatar_cpf, formatar_rg

TAMANHO_LOTE = 20
MAX_FOTO = (720, 960)

# Campos do membro que viajam para o Celular (mesmos nomes dos dois lados).
CAMPOS_MEMBRO = (
    "nome", "rg", "orgao_emissor", "cpf", "data_nascimento",
    "cidade_nascimento", "estado_nascimento", "estado_civil",
    "nome_conjuge", "data_nascimento_conjuge", "profissao",
    "nome_pai", "nome_mae", "grau_instrucao",
    "telefone", "celular", "email",
    "endereco", "numero", "bairro", "cidade", "estado", "cep",
    "batismo_aguas", "igreja_local_batismo_aguas",
    "data_batismo_espirito_santo", "igreja_local_batismo_espirito_santo",
    "ministerio", "cargo", "data_funcao", "curso_teologico", "status",
    "congregacao", "dirigente", "setor_campo", "recados_outros", "observacoes",
)
CAMPOS_CONFIGURACAO = (
    "nome_igreja", "ministerio", "convencao", "setor", "congregacao_sede", "cidade", "estado",
    "pastor_presidente", "pastor_setorial", "telefone", "whatsapp", "email", "site", "rua", "numero",
    "complemento", "bairro", "cep", "cidade_endereco", "estado_endereco",
    "congregacao_local_nome", "congregacao_local_dirigente", "congregacao_local_numero",
    "congregacao_local_campo_setor", "congregacao_local_cidade", "congregacao_local_estado",
    "congregacao_local_rua", "congregacao_local_numero_endereco", "congregacao_local_bairro",
    "congregacao_local_cep", "congregacao_local_telefone", "congregacao_local_whatsapp",
    "congregacao_local_email",
)


class SincronizacaoCelularErro(Exception):
    """Mensagem ja pronta para mostrar ao usuario."""


class ClienteCelular(ClienteSIGMOnline):
    """Mesmo cliente HTTP dos pre-cadastros, com as chamadas da sincronizacao."""

    def estado(self):
        dados = self._request("get", "/api/v1/sincronizacao/estado")
        membros = dados.get("membros")
        if not isinstance(membros, dict):
            raise SIGMOnlineRespostaErro("estado invalido")
        return membros

    def enviar_membros(self, itens):
        dados = self._request("post", "/api/v1/sincronizacao/membros", json={"membros": itens})
        if dados.get("sucesso") is not True:
            raise SIGMOnlineRespostaErro("sucesso falso ao enviar membros")
        return dados

    def finalizar(self, ids_desktop):
        dados = self._request("post", "/api/v1/sincronizacao/finalizar", json={"ids_desktop": ids_desktop})
        if dados.get("sucesso") is not True:
            raise SIGMOnlineRespostaErro("sucesso falso ao finalizar")
        return dados

    def enviar_configuracao(self, configuracao, logotipo_base64=None):
        corpo = {"configuracao": configuracao}
        if logotipo_base64 is not None:  # "" = a igreja nao tem logotipo (remove no Celular)
            corpo["logotipo_base64"] = logotipo_base64
        self._request("post", "/api/v1/sincronizacao/configuracao", json=corpo)

    def listar_alteracoes(self):
        dados = self._request("get", "/api/v1/sincronizacao/alteracoes")
        alteracoes = dados.get("alteracoes")
        if not isinstance(alteracoes, list):
            raise SIGMOnlineRespostaErro("alteracoes invalidas")
        return alteracoes

    def enviar_resultados(self, resultados):
        dados = self._request("post", "/api/v1/sincronizacao/alteracoes/resultado", json={"resultados": resultados})
        return dados


def criar_cliente():
    configuracao = buscar_configuracao_online_igreja()
    if not int(configuracao.get("ativo") or 0):
        raise SincronizacaoCelularErro(
            "Configure e ative a integracao online da igreja antes de sincronizar com o Celular."
        )
    return ClienteCelular(
        api_base_url=os.environ.get("SIGM_CELULAR_API_URL") or configuracao.get("api_base_url") or "",
        identificador_publico=configuracao.get("identificador_publico") or "",
        chave_sincronizacao=configuracao.get("chave_sincronizacao") or "",
    )


def mensagem_erro(erro):
    """Texto amigavel para qualquer falha."""
    if isinstance(erro, SincronizacaoCelularErro):
        return str(erro)
    if isinstance(erro, SIGMOnlineErro):
        if getattr(erro, "status_code", None) == 409:
            return (
                "Esta igreja esta no modo em que o Celular e a fonte dos dados. "
                "Nesse modo o desktop nao envia membros."
            )
        return erro.mensagem_usuario
    return "Nao foi possivel sincronizar com o Celular. Tente novamente."


# ---------------------------------------------------------------- membros
def _texto(valor):
    return "" if valor is None else str(valor).strip()


def listar_membros_locais():
    """[(id, {campo: valor})] com os campos que o Celular conhece."""
    garantir_colunas_complementares_membro()
    coluna_funcao = obter_coluna_data_funcao_membro()
    conexao = conectar()
    try:
        cursor = conexao.cursor()
        cursor.execute("SELECT * FROM membros ORDER BY id")
        nomes = [c[0] for c in cursor.description]
        linhas = cursor.fetchall()
    finally:
        conexao.close()

    membros = []
    for linha in linhas:
        registro = dict(zip(nomes, linha))
        dados = {}
        for campo in CAMPOS_MEMBRO:
            origem = coluna_funcao if (campo == "data_funcao" and coluna_funcao) else campo
            if origem in registro:
                dados[campo] = _texto(registro[origem])
        for campo in CAMPOS_DATA_BR:  # o Celular recebe datas como DD/MM/AAAA e Sim/Nao
            if campo in dados:
                dados[campo] = normalizar_campo_data(campo, dados[campo])
        if "cpf" in dados:
            dados["cpf"] = formatar_cpf(dados["cpf"])
        if "rg" in dados:
            dados["rg"] = formatar_rg(dados["rg"])
        membros.append((int(registro["id"]), dados))
    return membros


def _caminho_foto(id_membro):
    try:
        from documentos.integrador_documentos import buscar_caminho_foto_membro

        caminho = buscar_caminho_foto_membro(id_membro)
    except Exception:
        return None
    if caminho and Path(caminho).is_file():
        return Path(caminho)
    return None


def _assinatura_foto(caminho):
    if caminho is None:
        return "sem-foto"
    estatistica = caminho.stat()
    return f"{caminho.name}:{estatistica.st_size}:{int(estatistica.st_mtime)}"


def calcular_hash(dados, caminho_foto):
    base = json.dumps(dados, sort_keys=True, ensure_ascii=False) + "|" + _assinatura_foto(caminho_foto)
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def foto_em_base64(caminho):
    """Foto reduzida (JPEG) em base64; None se nao for possivel ler."""
    try:
        from PIL import Image, ImageOps

        with Image.open(caminho) as imagem:
            imagem = ImageOps.exif_transpose(imagem)
            imagem.thumbnail(MAX_FOTO)
            saida = io.BytesIO()
            imagem.convert("RGB").save(saida, "JPEG", quality=85, optimize=True)
        return base64.b64encode(saida.getvalue()).decode("ascii")
    except Exception:
        return None


def montar_item(id_membro, dados, estado_remoto):
    """Item a enviar, ou None se o Celular ja tem esta versao."""
    caminho = _caminho_foto(id_membro)
    hash_atual = calcular_hash(dados, caminho)
    if estado_remoto.get(str(id_membro)) == hash_atual:
        return None
    item = {"id_desktop": id_membro, "hash": hash_atual, "dados": dados}
    if caminho is not None:
        foto = foto_em_base64(caminho)
        if foto:
            item["foto_base64"] = foto
    else:
        item["sem_foto"] = True
    return item


def dados_da_igreja():
    configuracao = buscar_configuracoes_igreja()
    return {campo: _texto(configuracao.get(campo)) for campo in CAMPOS_CONFIGURACAO}


def logotipo_em_base64():
    """Logotipo da igreja em PNG/base64; "" se nao ha logotipo; None se nao deu para ler."""
    caminho = _texto(buscar_configuracoes_igreja().get("logotipo"))
    if not caminho:
        return ""
    arquivo = Path(caminho)
    if not arquivo.is_file():
        return None
    try:
        from PIL import Image, ImageOps

        with Image.open(arquivo) as imagem:
            imagem = ImageOps.exif_transpose(imagem).convert("RGBA")
            imagem.thumbnail((480, 480))
            saida = io.BytesIO()
            imagem.save(saida, "PNG", optimize=True)
        return base64.b64encode(saida.getvalue()).decode("ascii")
    except Exception:
        return None


def enviar_dados_para_celular(cliente=None, progresso=None):
    """Envia o que mudou. Devolve um resumo para mostrar ao usuario."""
    aviso = progresso or (lambda _texto: None)
    cliente = cliente or criar_cliente()
    resumo = {
        "total": 0, "enviados": 0, "criados": 0, "atualizados": 0, "removidos": 0, "erros": 0,
        "recebidos": 0, "conflitos": 0,
    }

    aviso("Conferindo a conexao com o Celular...")
    cliente.validar_igreja()
    registrar_acao("SINCRONIZACAO_CELULAR_INICIADA", "Envio de dados ao Celular iniciado.", modulo="Celular")

    # Primeiro traz o que foi editado no Celular; so depois envia, para nao sobrescrever essas edicoes.
    aviso("Recebendo as alteracoes feitas no Celular...")
    recebido = receber_alteracoes_do_celular(cliente)
    resumo["recebidos"] = recebido["membros"]
    resumo["conflitos"] = recebido["conflitos"]

    aviso("Enviando os dados da igreja...")
    logotipo = logotipo_em_base64()
    if logotipo is None:
        cliente.enviar_configuracao(dados_da_igreja())
    else:
        cliente.enviar_configuracao(dados_da_igreja(), logotipo_base64=logotipo)

    aviso("Comparando os membros...")
    estado_remoto = cliente.estado()
    membros = listar_membros_locais()
    resumo["total"] = len(membros)

    pendentes = []
    for id_membro, dados in membros:
        if not dados.get("nome"):
            continue
        item = montar_item(id_membro, dados, estado_remoto)
        if item is not None:
            pendentes.append(item)

    for inicio in range(0, len(pendentes), TAMANHO_LOTE):
        lote = pendentes[inicio:inicio + TAMANHO_LOTE]
        aviso(f"Enviando membros ({min(inicio + TAMANHO_LOTE, len(pendentes))} de {len(pendentes)})...")
        resposta = cliente.enviar_membros(lote)
        resumo["enviados"] += len(lote)
        resumo["criados"] += int(resposta.get("criados") or 0)
        resumo["atualizados"] += int(resposta.get("atualizados") or 0)
        resumo["erros"] += int(resposta.get("erros") or 0)

    aviso("Finalizando...")
    final = cliente.finalizar([id_membro for id_membro, dados in membros if dados.get("nome")])
    resumo["removidos"] = int(final.get("removidos") or 0)

    registrar_acao(
        "SINCRONIZACAO_CELULAR_CONCLUIDA", "Envio de dados ao Celular concluido.", modulo="Celular",
        detalhes=(
            f"total={resumo['total']}; enviados={resumo['enviados']}; criados={resumo['criados']}; "
            f"atualizados={resumo['atualizados']}; removidos={resumo['removidos']}; erros={resumo['erros']}"
        ),
    )
    return resumo


def texto_resumo(resumo):
    recebidos = int(resumo.get("recebidos") or 0)
    conflitos = int(resumo.get("conflitos") or 0)
    extra = ""
    if recebidos:
        extra += f" {recebidos} membro(s) atualizado(s) com edicoes feitas no Celular."
    if conflitos:
        extra += f" {conflitos} campo(s) alterado(s) nos dois lados: valeu o do desktop."
    if resumo["enviados"] == 0 and resumo["removidos"] == 0:
        return f"O Celular ja esta atualizado ({resumo['total']} membros)." + extra
    partes = [f"{resumo['enviados']} enviado(s)"]
    if resumo["criados"]:
        partes.append(f"{resumo['criados']} novo(s)")
    if resumo["atualizados"]:
        partes.append(f"{resumo['atualizados']} atualizado(s)")
    if resumo["removidos"]:
        partes.append(f"{resumo['removidos']} removido(s) do Celular")
    if resumo["erros"]:
        partes.append(f"{resumo['erros']} com erro")
    return "Envio concluido: " + ", ".join(partes) + "." + extra


# ------------------------------------------------- sugestoes do Celular
def buscar_alteracoes(cliente=None):
    cliente = cliente or criar_cliente()
    cliente.validar_igreja()
    alteracoes = cliente.listar_alteracoes()
    return [dict(a, situacao=situacao_atual(a)) for a in alteracoes]


def _mesmo_valor(campo, a, b):
    a, b = _texto(a), _texto(b)
    if campo == "cpf":
        a, b = formatar_cpf(a), formatar_cpf(b)
    elif campo == "rg":
        a, b = formatar_rg(a), formatar_rg(b)
    return " ".join(a.split()) == " ".join(b.split())


def classificar_alteracao(alteracao, atual):
    """Separa os campos da edicao do Celular.

    Devolve (aplicar, conflitos): `aplicar` = {campo: {"depois": ...}} dos campos que
    ainda estao como estavam quando o Celular editou; `conflitos` = lista de campos que
    mudaram nos dois lados (nesses vale o do desktop).
    """
    aplicar, conflitos = {}, []
    for campo, mudanca in (alteracao.get("campos") or {}).items():
        if campo not in CAMPOS_MEMBRO or not isinstance(mudanca, dict):
            continue
        antes, depois = mudanca.get("antes"), mudanca.get("depois")
        valor_atual = atual.get(campo, "")
        if _mesmo_valor(campo, valor_atual, depois):
            continue  # ja esta igual
        if _mesmo_valor(campo, valor_atual, antes):
            aplicar[campo] = {"depois": _texto(depois)}
        else:
            conflitos.append(campo)
    return aplicar, conflitos


def receber_alteracoes_do_celular(cliente=None):
    """Aplica sozinho as edicoes feitas no Celular e avisa o resultado.

    Regra: campo que so o Celular mudou -> o desktop recebe o valor novo. Campo que
    os dois lados mudaram de forma diferente -> vale o do desktop (e o Celular
    recebe esse valor no envio logo em seguida). Devolve {"membros", "campos", "conflitos"}.
    """
    cliente = cliente or criar_cliente()
    resumo = {"membros": 0, "campos": 0, "conflitos": 0}
    resultados = []
    for alteracao in cliente.listar_alteracoes():
        try:
            atual = _membro_local(int(alteracao.get("id_desktop")))
        except (TypeError, ValueError):
            atual = None
        if atual is None:
            resultados.append({"id": alteracao.get("id"), "status": "rejeitada",
                               "motivo": "Membro nao existe mais no desktop"})
            continue
        aplicar, conflitos = classificar_alteracao(alteracao, atual)
        if aplicar:
            quantidade = aplicar_alteracao(dict(alteracao, campos=aplicar))
            resumo["membros"] += 1
            resumo["campos"] += quantidade
        resumo["conflitos"] += len(conflitos)
        motivo = ""
        if conflitos:
            motivo = ("Alterado nos dois lados (" + ", ".join(conflitos) + "): valeu o do desktop")[:180]
            registrar_acao(
                "ALTERACAO_DO_CELULAR_CONFLITO", "Campo alterado no desktop e no Celular: valeu o do desktop.",
                modulo="Celular", registro_id=alteracao.get("id_desktop"), detalhes="campos=" + ", ".join(conflitos),
            )
        resultados.append({
            "id": alteracao.get("id"),
            "status": "aplicada" if (aplicar or not conflitos) else "rejeitada",
            "motivo": motivo,
        })
    if resultados:
        cliente.enviar_resultados(resultados)
    return resumo


def _membro_local(id_membro):
    for ident, dados in listar_membros_locais():
        if ident == id_membro:
            return dados
    return None


def situacao_atual(alteracao):
    """Mostra o valor de hoje no desktop ao lado do valor proposto."""
    try:
        atual = _membro_local(int(alteracao.get("id_desktop")))
    except (TypeError, ValueError):
        atual = None
    if atual is None:
        return {"existe": False, "campos": {}}
    campos = {}
    for campo, mudanca in (alteracao.get("campos") or {}).items():
        if campo in CAMPOS_MEMBRO:
            campos[campo] = {
                "atual": atual.get(campo, ""),
                "antes": _texto((mudanca or {}).get("antes")),
                "depois": _texto((mudanca or {}).get("depois")),
            }
    return {"existe": True, "campos": campos}


def aplicar_alteracao(alteracao):
    """Grava no desktop so os campos conhecidos e existentes. Devolve a quantidade alterada."""
    try:
        id_membro = int(alteracao.get("id_desktop"))
    except (TypeError, ValueError):
        raise SincronizacaoCelularErro("Alteracao sem membro valido.")
    coluna_funcao = obter_coluna_data_funcao_membro()

    conexao = conectar()
    try:
        cursor = conexao.cursor()
        cursor.execute("PRAGMA table_info(membros)")
        colunas = {str(c[1]) for c in cursor.fetchall()}
        cursor.execute("SELECT 1 FROM membros WHERE id = ?", (id_membro,))
        if cursor.fetchone() is None:
            raise SincronizacaoCelularErro("O membro nao existe mais no desktop.")

        atribuicoes, valores, aplicados = [], [], []
        for campo, mudanca in (alteracao.get("campos") or {}).items():
            if campo not in CAMPOS_MEMBRO or (campo == "nome" and not _texto((mudanca or {}).get("depois"))):
                continue
            coluna = coluna_funcao if (campo == "data_funcao" and coluna_funcao) else campo
            if coluna not in colunas:
                continue
            valor = _texto((mudanca or {}).get("depois"))
            if campo == "cpf":
                valor = formatar_cpf(valor)
            elif campo == "rg":
                valor = formatar_rg(valor)
            atribuicoes.append(f'"{coluna}" = ?')
            valores.append(valor)
            aplicados.append(campo)
        if not atribuicoes:
            return 0
        cursor.execute(f"UPDATE membros SET {', '.join(atribuicoes)} WHERE id = ?", (*valores, id_membro))
        conexao.commit()
    finally:
        conexao.close()

    registrar_acao(
        "MEMBRO_ALTERADO_PELO_CELULAR", "Alteracao sugerida no Celular foi aplicada.", modulo="Celular",
        registro_id=id_membro, detalhes="campos=" + ", ".join(aplicados),
    )
    return len(aplicados)


def responder_alteracao(cliente, alteracao, aplicar, motivo=""):
    """Aplica (ou rejeita) e avisa o Celular. Devolve a mensagem para o usuario."""
    if aplicar:
        quantidade = aplicar_alteracao(alteracao)
        resultado = {"id": alteracao.get("id"), "status": "aplicada"}
        mensagem = f"{quantidade} campo(s) atualizado(s)."
    else:
        resultado = {"id": alteracao.get("id"), "status": "rejeitada", "motivo": motivo}
        mensagem = "Sugestao rejeitada."
        registrar_acao(
            "ALTERACAO_DO_CELULAR_REJEITADA", "Alteracao sugerida no Celular foi rejeitada.", modulo="Celular",
            registro_id=alteracao.get("id_desktop"),
        )
    cliente.enviar_resultados([resultado])
    return mensagem
